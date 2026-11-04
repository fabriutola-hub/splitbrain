"""M5 Arbiter: the exclusive `arbiter` lease holder that convenes people.

Only the lease holder acts on `sb:candidate`; a standby Arbiter retries
`assume_role` every 5 s and takes over when the holder's heartbeat lapses. The
Arbiter never reads team rooms and never picks a winner: it verifies, convenes,
records what the two authors decided, and asks the Sentinel to correct the
original threads.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .. import bootstrap
from ..config import Settings, SplitbrainError
from ..core.decision import DecisionMachine, DecisionOutcome, DecisionState
from ..core.models import Decision, Evidence
from ..core.packets import encode
from ..core.protocol import (
    CandidatePacket,
    ConsentPacket,
    ConsentRequestPacket,
    CorrectedPacket,
    DecidedPacket,
    EvidenceClaim,
    EvidenceRequestPacket,
    LinkedPacket,
    LinkRequestPacket,
    LinkTarget,
    OriginRef,
    PacketClaim,
    VerdictPacket,
    read_packet,
)
from ..switch.client import SwitchAgent, SwitchOpError
from ..switch.events import (
    ConnectionStateFrame,
    MessageFrame,
    RoomJoinFrame,
    SubscriptionChangedFrame,
    SwitchFrame,
)
from .base import (
    AgentRuntime,
    configure_logging,
    print_service_banner,
    reply_thread,
)
from .coverage import OPS_ROOM, RoomCoverage

logger = logging.getLogger(__name__)

AGENT_NAME = "splitbrain-arbiter"
SENTINEL_NAME = "splitbrain-sentinel"
ARBITER_ROLE = "arbiter"
CONFIDENCE_THRESHOLD = 0.7
ROLE_RETRY_S = 5.0
TICK_S = 1.0
LINK_TIMEOUT_S = 60.0


def _env_timeout(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise SplitbrainError(f"{name} must be a number of seconds, got {raw!r}") from exc
    if value <= 0:
        raise SplitbrainError(f"{name} must be positive, got {value}")
    return value


def _stamp(ts: int) -> str:
    moment = datetime.fromtimestamp(ts / 1000, UTC) if ts > 0 else datetime.now(UTC)
    return f"{moment.strftime('%b')} {moment.day} {moment.strftime('%H:%M')}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "subject"


def verdict_for(confidence: float, evidence_status: str) -> str:
    """SPEC 4.5: confirmed only with enough confidence and independent evidence."""
    if confidence >= CONFIDENCE_THRESHOLD and evidence_status != "none":
        return "confirmed"
    return "discarded"


def _quote(claim: PacketClaim, consents: dict[str, ConsentPacket]) -> str:
    if claim.text_withheld:
        consent = consents.get(claim.id)
        if consent is not None and consent.granted and consent.text:
            return f'"{consent.text}"'
        return (
            "(quote withheld at the author's request) "
            f"Subject: {claim.subject or claim.subject_key}."
        )
    return f'"{claim.text or "(quote unavailable)"}"'


def _claim_line(claim: PacketClaim, consents: dict[str, ConsentPacket]) -> str:
    private = " (private)" if claim.channel_type == "channel_private" else ""
    return (
        f"#{claim.room_name}{private}, {claim.author}, {_stamp(claim.ts)}: "
        f"{_quote(claim, consents)}"
    )


@dataclass
class Verification:
    candidate: CandidatePacket
    thread_id: str
    requested_at: float
    evidence: Evidence | None = None
    verdict: str | None = None
    consents: dict[str, ConsentPacket] = field(default_factory=dict)
    withheld_ids: set[str] = field(default_factory=set)
    consent_requested_at: float | None = None
    room_id: str | None = None
    room_name: str = ""
    document_id: str = ""
    record: str = ""
    machine: DecisionMachine | None = None
    origins: list[OriginRef] = field(default_factory=list)
    decided: bool = False
    corrected: bool = False
    link_future: asyncio.Future[LinkedPacket] | None = None
    link_labels: list[str] = field(default_factory=list)
    finished: bool = False

    @property
    def claims(self) -> tuple[PacketClaim, PacketClaim]:
        return self.candidate.claims


class Arbiter:
    def __init__(
        self,
        *,
        agent: SwitchAgent,
        state: bootstrap.BootstrapState,
        name: str,
        consent_timeout_s: float,
        evidence_timeout_s: float,
    ) -> None:
        ops = state.rooms.get(OPS_ROOM)
        if ops is None:
            raise SplitbrainError("splitbrain-ops is missing from .splitbrain/state.json")
        self.agent = agent
        self.name = name
        self.ops_room_id = ops.room_id
        self.coverage = RoomCoverage(agent, self.ops_room_id, own_name=name)
        self.consent_timeout_s = consent_timeout_s
        self.evidence_timeout_s = evidence_timeout_s
        self.is_holder = False
        self.stop = asyncio.Event()
        self._role_lock = asyncio.Lock()
        self.verifications: dict[str, Verification] = {}
        self.by_room: dict[str, str] = {}
        self.seen_candidates: set[str] = set()
        self.deferred: list[tuple[MessageFrame, CandidatePacket]] = []
        self.tasks: set[asyncio.Task[None]] = set()
        self.loops: list[asyncio.Task[None]] = []

    # ── Runtime ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self.loops = [
            asyncio.create_task(self._role_loop(), name=f"{self.name}-role"),
            asyncio.create_task(self._tick_loop(), name=f"{self.name}-tick"),
        ]
        logger.info("Arbiter %s ready; ops room %s", self.name, self.ops_room_id[:8])

    async def aclose(self) -> None:
        self.stop.set()
        for task in (*self.loops, *self.tasks):
            task.cancel()
        await asyncio.gather(*self.loops, *self.tasks, return_exceptions=True)
        for verification in self.verifications.values():
            if verification.link_future is not None and not verification.link_future.done():
                verification.link_future.cancel()
        logger.info(
            "Arbiter %s stopped; %d candidate(s) handled", self.name, len(self.seen_candidates)
        )

    def _spawn(self, coroutine: Any, label: str) -> None:
        task = asyncio.create_task(coroutine, name=label)
        self.tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("Arbiter task %s failed: %s", task.get_name(), error, exc_info=error)

    async def _role_loop(self) -> None:
        while not self.stop.is_set():
            if self.coverage.connected:
                try:
                    await self._ensure_role()
                except Exception:
                    logger.exception("Role check failed; retrying in %.0fs", ROLE_RETRY_S)
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=ROLE_RETRY_S)
            except TimeoutError:
                pass

    async def _ensure_role(self) -> None:
        async with self._role_lock:
            detail = await self.agent.op(
                "get_room_detail", room_id=self.ops_room_id, connection=False
            )
            holders: list[str] = []
            for role in detail.get("roles", []):
                if role.get("name") != ARBITER_ROLE:
                    continue
                for holder in role.get("held_by") or []:
                    holders.append(str(holder.get("name") if isinstance(holder, dict) else holder))
            if self.name in holders:
                if not self.is_holder:
                    logger.info("%s now holds the exclusive arbiter lease", self.name)
                self.is_holder = True
                await self._drain_deferred()
                return
            self.is_holder = False
            try:
                async with self.agent.act_in(self.ops_room_id):
                    await self.agent.op("assume_role", role=ARBITER_ROLE)
            except SwitchOpError as exc:
                if "exclusive" not in exc.body.casefold():
                    raise
                logger.info(
                    "Standby: arbiter lease held by another agent (HTTP %s); retrying in %.0fs",
                    exc.status,
                    ROLE_RETRY_S,
                )
                return
            self.is_holder = True
            logger.info("%s assumed the exclusive arbiter lease", self.name)
            await self._drain_deferred()

    async def _drain_deferred(self) -> None:
        if not self.deferred:
            return
        queued, self.deferred = self.deferred, []
        logger.info("Processing %d candidate(s) deferred while on standby", len(queued))
        for frame, candidate in queued:
            if candidate.id in self.seen_candidates:
                continue
            self.seen_candidates.add(candidate.id)
            self._spawn(self._begin(frame, candidate), f"verify-{candidate.id}")

    async def _tick_loop(self) -> None:
        while not self.stop.is_set():
            now = asyncio.get_running_loop().time()
            for verification in list(self.verifications.values()):
                if verification.finished or verification.room_id is not None:
                    continue
                if (
                    verification.evidence is None
                    and now - verification.requested_at > self.evidence_timeout_s
                ):
                    await self._discard(verification, "no evidence arrived before the deadline")
                elif (
                    verification.verdict == "confirmed"
                    and verification.consent_requested_at is not None
                    and now - verification.consent_requested_at > self.consent_timeout_s
                ):
                    logger.warning(
                        "Consent for %s timed out after %.0fs; quotes stay withheld",
                        verification.candidate.id,
                        self.consent_timeout_s,
                    )
                    self._fill_missing_consents(verification)
                    self._spawn(
                        self._open_conflict(verification),
                        f"conflict-{verification.candidate.id}",
                    )
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=TICK_S)
            except TimeoutError:
                pass

    @staticmethod
    def _fill_missing_consents(verification: Verification) -> None:
        for claim in verification.claims:
            if claim.id in verification.withheld_ids and claim.id not in verification.consents:
                verification.consents[claim.id] = ConsentPacket(
                    candidate_id=verification.candidate.id,
                    claim_id=claim.id,
                    author=claim.author,
                    granted=False,
                    text=None,
                )

    # ── Frames ─────────────────────────────────────────────────────────────

    async def on_frame(self, frame: SwitchFrame) -> None:
        if isinstance(frame, ConnectionStateFrame):
            await self.coverage.on_connection_state(frame)
            await self._ensure_role()
        elif isinstance(frame, SubscriptionChangedFrame):
            await self.coverage.on_subscription(frame)
        elif isinstance(frame, RoomJoinFrame):
            await self.coverage.on_room_join(frame)
        elif isinstance(frame, MessageFrame):
            await self._on_message(frame)

    async def _on_message(self, frame: MessageFrame) -> None:
        if frame.room_id not in self.coverage.rooms:
            await self.coverage.ensure_known(frame.room_id)
        candidate_id = self.by_room.get(frame.room_id)
        if candidate_id is not None:
            await self._on_conflict_message(frame, candidate_id)
            return
        packet = read_packet(frame.payload.body, frame.payload.sender_name)
        if packet is None:
            return
        kind, payload = packet
        if kind == "candidate" and isinstance(payload, CandidatePacket):
            await self._on_candidate(frame, payload)
        elif kind == "evidence" and isinstance(payload, Evidence):
            await self._on_evidence(frame, payload)
        elif kind == "consent" and isinstance(payload, ConsentPacket):
            await self._on_consent(payload)
        elif kind == "linked" and isinstance(payload, LinkedPacket):
            self._on_linked(payload)
        elif kind == "corrected" and isinstance(payload, CorrectedPacket):
            # M6 closes the loop; the M5 Arbiter only records that it arrived.
            logger.debug("sb:corrected for %s (handled from M6)", payload.candidate_id)

    async def _on_candidate(self, frame: MessageFrame, candidate: CandidatePacket) -> None:
        if frame.room_id != self.ops_room_id:
            return
        if frame.payload.sender_name != SENTINEL_NAME:
            logger.warning("Ignoring a candidate from %s", frame.payload.sender_name)
            return
        if candidate.id in self.seen_candidates:
            logger.info("Candidate %s already handled; ignoring", candidate.id)
            return
        if not self.is_holder:
            logger.info("Standby: deferring candidate %s (not the lease holder)", candidate.id)
            self.deferred.append((frame, candidate))
            return
        self.seen_candidates.add(candidate.id)
        self._spawn(self._begin(frame, candidate), f"verify-{candidate.id}")

    async def _begin(self, frame: MessageFrame, candidate: CandidatePacket) -> None:
        verification = Verification(
            candidate=candidate,
            thread_id=reply_thread(frame),
            requested_at=asyncio.get_running_loop().time(),
        )
        self.verifications[candidate.id] = verification
        a, b = candidate.claims
        request = EvidenceRequestPacket(
            candidate_id=candidate.id,
            subject=a.subject or a.subject_key,
            subject_key=a.subject_key,
            scope=a.scope,
            claim_a=EvidenceClaim(room=a.room_name, value=a.value, date=a.effective_date),
            claim_b=EvidenceClaim(room=b.room_name, value=b.value, date=b.effective_date),
        )
        body = (
            f"Verifying {candidate.id.upper()} about {request.subject} (confidence "
            f"{candidate.confidence:.2f}). Asking the verifier for independent evidence.\n"
            + encode("evidence_request", request)
        )
        await self.agent.targeted(
            self.ops_room_id,
            body,
            target_roles=["verifier"],
            thread_id=verification.thread_id,
        )
        logger.info("Candidate %s: evidence requested from the verifier", candidate.id)

    async def _on_evidence(self, frame: MessageFrame, evidence: Evidence) -> None:
        if frame.payload.sender_name != "splitbrain-verifier":
            logger.warning("Ignoring evidence from %s", frame.payload.sender_name)
            return
        verification = self.verifications.get(evidence.candidate_id)
        if verification is None or verification.finished or verification.evidence is not None:
            return
        verification.evidence = evidence
        verdict_value = verdict_for(verification.candidate.confidence, evidence.status)
        confirmed = verdict_value == "confirmed"
        verification.verdict = verdict_value
        reason = (
            f"classifier confidence {verification.candidate.confidence:.2f}, "
            f"evidence status {evidence.status}"
        )
        verdict = VerdictPacket(
            candidate_id=evidence.candidate_id,
            verdict=verification.verdict,
            confidence=verification.candidate.confidence,
            evidence_status=evidence.status,
            reason=reason,
        )
        readable = (
            f"Verdict for {evidence.candidate_id.upper()}: {verification.verdict.upper()}. "
            f"{reason}. "
            + (
                "Convening the two authors."
                if confirmed
                else "No evidence, no interruption: nobody is contacted."
            )
        )
        await self.agent.post(
            self.ops_room_id,
            readable + "\n" + encode("verdict", verdict),
            thread_id=verification.thread_id,
        )
        logger.info("Verdict for %s: %s (%s)", evidence.candidate_id, verification.verdict, reason)
        if not confirmed:
            verification.finished = True
            return
        withheld = [claim for claim in verification.claims if claim.text_withheld]
        if not withheld:
            self._spawn(self._open_conflict(verification), f"conflict-{verification.candidate.id}")
            return
        verification.withheld_ids = {claim.id for claim in withheld}
        a, b = verification.claims
        for claim in withheld:
            other = b if claim is a else a
            request = ConsentRequestPacket(
                candidate_id=verification.candidate.id,
                claim_id=claim.id,
                author=claim.author,
                other_author=other.author,
                room_id=claim.room_id,
                thread_id=claim.thread_root,
            )
            body = (
                f"Consent needed for {verification.candidate.id.upper()}: the quote from "
                f"#{claim.room_name} is private. Asking @{claim.author} there.\n"
                + encode("consent_request", request)
            )
            await self.agent.targeted(
                self.ops_room_id,
                body,
                target_names=[SENTINEL_NAME],
                thread_id=verification.thread_id,
            )
        verification.consent_requested_at = asyncio.get_running_loop().time()
        logger.info(
            "Candidate %s: waiting up to %.0fs for %d consent answer(s)",
            verification.candidate.id,
            self.consent_timeout_s,
            len(withheld),
        )

    async def _discard(self, verification: Verification, reason: str) -> None:
        verification.finished = True
        verdict = VerdictPacket(
            candidate_id=verification.candidate.id,
            verdict="discarded",
            confidence=verification.candidate.confidence,
            evidence_status="none",
            reason=reason,
        )
        await self.agent.post(
            self.ops_room_id,
            f"Verdict for {verification.candidate.id.upper()}: DISCARDED. {reason}. "
            "Nobody is contacted.\n" + encode("verdict", verdict),
            thread_id=verification.thread_id,
        )
        logger.warning("Candidate %s discarded: %s", verification.candidate.id, reason)

    async def _on_consent(self, consent: ConsentPacket) -> None:
        verification = self.verifications.get(consent.candidate_id)
        if verification is None or verification.finished or verification.room_id is not None:
            return
        if consent.claim_id not in verification.withheld_ids:
            return
        verification.consents[consent.claim_id] = consent
        logger.info(
            "Consent for %s/%s: %s",
            consent.candidate_id,
            consent.author,
            "granted" if consent.granted else "denied",
        )
        if verification.withheld_ids <= set(verification.consents):
            self._spawn(self._open_conflict(verification), f"conflict-{verification.candidate.id}")

    # ── Conflict room ──────────────────────────────────────────────────────

    async def _open_conflict(self, verification: Verification) -> None:
        if verification.room_id is not None or verification.finished:
            return
        candidate = verification.candidate
        a, b = candidate.claims
        room_name = f"conflict-{candidate.id}-{_slug(a.subject_key)}"
        verification.room_name = room_name
        created = await self.agent.op(
            "create_room",
            name=room_name,
            description=f"Conflict {candidate.id}: {a.subject} for {a.scope}",
            agent_names=[AGENT_NAME, SENTINEL_NAME],
            user_names=[a.author, b.author],
            channel_type="channel_public",
            instructions=(
                "Only the two claim authors may close this conflict. One writes "
                "'decision: <text>' and the other replies 'confirm'. The Arbiter "
                "records their words verbatim and never picks a winner."
            ),
        )
        room_id = str(created.get("id") or created.get("room_id") or "")
        if not room_id:
            raise SplitbrainError(f"create_room for {room_name} returned no room id: {created}")
        verification.room_id = room_id
        self.coverage.rooms[room_id] = room_name
        self.by_room[room_id] = candidate.id
        verification.origins = [
            OriginRef(
                room_id=claim.room_id,
                room_name=claim.room_name,
                thread_id=claim.thread_root,
                message_id=claim.message_id,
                author=claim.author,
                claim_id=claim.id,
            )
            for claim in candidate.claims
        ]
        verification.link_labels = await self._link_origins(verification)
        verification.record = self._open_record(verification)
        # Claim the room: new rooms are not covered by the stream on their own.
        async with self.agent.act_in(room_id):
            document = await self.agent.op(
                "create_room_document",
                name=f"{candidate.id.upper()} decision record",
                description=f"Decision record for {candidate.id}",
                instructions="Only the Arbiter edits this record; people decide its content.",
                content=verification.record,
            )
        verification.document_id = str(document["document_id"])
        verification.machine = DecisionMachine(a.author, b.author)
        await self.agent.post(room_id, self._brief(verification))
        logger.info(
            "Conflict room #%s created for %s (document %s, links %s)",
            room_name,
            candidate.id,
            verification.document_id[:8],
            verification.link_labels,
        )

    async def _link_origins(self, verification: Verification) -> list[str]:
        room_id = verification.room_id or ""
        targets = [
            LinkTarget(room_id=claim.room_id, label=claim.origin_label)
            for claim in verification.claims
        ]
        labels: list[str] = []
        for target in targets:
            try:
                await self.agent.op(
                    "link_rooms",
                    source_room_id=room_id,
                    target_room_id=target.room_id,
                    label=target.label,
                )
                labels.append(target.label)
            except SwitchOpError as exc:
                logger.warning(
                    "link_rooms refused for %s (HTTP %s: %s); asking the Sentinel",
                    target.label,
                    exc.status,
                    exc.body,
                )
                return await self._link_via_sentinel(verification, targets)
        return labels

    async def _link_via_sentinel(
        self, verification: Verification, targets: list[LinkTarget]
    ) -> list[str]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[LinkedPacket] = loop.create_future()
        verification.link_future = future
        request = LinkRequestPacket(
            candidate_id=verification.candidate.id,
            conflict_room_id=verification.room_id or "",
            origins=targets,
        )
        await self.agent.targeted(
            self.ops_room_id,
            f"Link request for {verification.candidate.id.upper()}: the Arbiter is not a "
            "member of an origin room; the Sentinel should create the links.\n"
            + encode("link_request", request),
            target_names=[SENTINEL_NAME],
            thread_id=verification.thread_id,
        )
        try:
            answer = await asyncio.wait_for(future, timeout=LINK_TIMEOUT_S)
        except TimeoutError as exc:
            raise SplitbrainError(
                f"Timed out after {LINK_TIMEOUT_S:.0f}s waiting for sb:linked for "
                f"{verification.candidate.id}; the Sentinel did not answer the link request."
            ) from exc
        finally:
            verification.link_future = None
        return answer.labels

    def _on_linked(self, packet: LinkedPacket) -> None:
        verification = self.verifications.get(packet.candidate_id)
        if verification is None or verification.link_future is None:
            return
        if not verification.link_future.done():
            verification.link_future.set_result(packet)

    def _open_record(self, verification: Verification) -> str:
        candidate = verification.candidate
        a, b = candidate.claims
        evidence = verification.evidence
        lines = [
            f"{candidate.id.upper()} decision record",
            "",
            "Status: OPEN",
            f"Subject: {a.subject} (scope: {a.scope})",
            f"Classifier confidence: {candidate.confidence:.2f}",
            "",
            f"Claim A - #{a.room_name}, {a.author}, {_stamp(a.ts)}",
            f"  {_quote(a, verification.consents)}",
            f"  Origin message: {a.message_id} / thread {a.thread_root}",
            "",
            f"Claim B - #{b.room_name}"
            + (" (private)" if b.channel_type == "channel_private" else "")
            + f", {b.author}, {_stamp(b.ts)}",
            f"  {_quote(b, verification.consents)}",
            f"  Subject: {b.subject}. Extracted value: {b.value}.",
            f"  Origin message: {b.message_id} / thread {b.thread_root}",
            "",
            f"Evidence ({evidence.source if evidence else 'none'}): "
            f"{evidence.summary if evidence else 'no independent evidence'}",
            f"Links: {', '.join(verification.link_labels) or 'none'}",
            "",
            f"Decision protocol: only @{a.author} and @{b.author} can close this conflict.",
        ]
        return "\n".join(lines)

    def _brief(self, verification: Verification) -> str:
        candidate = verification.candidate
        a, b = candidate.claims
        evidence = verification.evidence
        summary = evidence.summary if evidence else "No independent evidence was found."
        return "\n".join(
            [
                f"@{a.author} @{b.author} - "
                "Splitbrain found two statements that can't both be true.",
                "",
                _claim_line(a, verification.consents),
                _claim_line(b, verification.consents),
                "",
                f"Evidence (GitHub, {self._repo_label(evidence)}): {summary}",
                "",
                "You two decide. When you agree, one of you writes:  decision: <what you agreed>",
                "and the other replies:  confirm",
                "I'll record it and correct both original threads.",
            ]
        )

    @staticmethod
    def _repo_label(evidence: Evidence | None) -> str:
        if evidence is None or not evidence.items:
            return "Acme roadmap"
        url = evidence.items[0].url
        return "/".join(url.split("/")[3:5]) if "github.com" in url else "Acme roadmap"

    # ── Decision protocol ──────────────────────────────────────────────────

    async def _on_conflict_message(self, frame: MessageFrame, candidate_id: str) -> None:
        verification = self.verifications.get(candidate_id)
        if verification is None or verification.machine is None or verification.room_id is None:
            return
        author = frame.payload.sender_name
        if author.startswith("splitbrain-") or (frame.payload.sender_kind or "") == "platform":
            return
        outcome = verification.machine.handle(author, frame.payload.body)
        if outcome.reply:
            await self.agent.post(
                verification.room_id, outcome.reply, thread_id=reply_thread(frame)
            )
        if outcome.state == DecisionState.DECIDED and not verification.decided:
            await self._on_decided(verification, outcome)

    async def _on_decided(self, verification: Verification, outcome: DecisionOutcome) -> None:
        verification.decided = True
        decision = Decision(
            candidate_id=verification.candidate.id,
            room_id=verification.room_id or "",
            text=outcome.decision or "",
            proposed_by=outcome.proposed_by or "",
            confirmed_by=outcome.confirmed_by or "",
            decided_at=outcome.decided_at or "",
        )
        verification.record = verification.record.replace("Status: OPEN", "Status: DECIDED")
        verification.record += "\n".join(
            [
                "",
                "",
                f'Decision: "{decision.text}"',
                f"Proposed by: @{decision.proposed_by}",
                f"Confirmed by: @{decision.confirmed_by}",
                f"Decided at: {decision.decided_at}",
            ]
        )
        async with self.agent.act_in(verification.room_id or ""):
            await self.agent.op(
                "update_room_document",
                document_id=verification.document_id,
                content=verification.record,
            )
        await self.agent.post(
            verification.room_id or "", "Recorded. Correcting the original threads now."
        )
        packet = DecidedPacket(
            candidate_id=verification.candidate.id,
            decision=decision,
            conflict_room=verification.room_id or "",
            conflict_room_name=verification.room_name,
            origins=verification.origins,
            subject=verification.candidate.claim_a.subject,
            subject_key=verification.candidate.claim_a.subject_key,
            scope=verification.candidate.claim_a.scope,
            scope_key=verification.candidate.claim_a.scope_key,
            authors=[claim.author for claim in verification.claims],
        )
        await self.agent.targeted(
            self.ops_room_id,
            f'Decision recorded for {verification.candidate.id.upper()}: "{decision.text}" '
            f"(proposed by @{decision.proposed_by}, confirmed by @{decision.confirmed_by}). "
            "Sentinel, please correct both original threads.\n" + encode("decided", packet),
            target_names=[SENTINEL_NAME],
            thread_id=verification.thread_id,
        )
        logger.info(
            "Decision recorded for %s in #%s: %s",
            verification.candidate.id,
            verification.room_name,
            decision.text,
        )


def build_runtime(
    settings: Settings, *, name: str = AGENT_NAME, stop: asyncio.Event | None = None
) -> AgentRuntime:
    state = bootstrap.load_state(settings)
    credentials = state.agents.get(name)
    if credentials is None or not state.rooms:
        raise SplitbrainError("Bootstrap is incomplete; run 'uv run splitbrain bootstrap' first.")
    consent_timeout_s = _env_timeout("SPLITBRAIN_CONSENT_TIMEOUT_S", 600.0)
    evidence_timeout_s = _env_timeout("SPLITBRAIN_EVIDENCE_TIMEOUT_S", 60.0)
    configure_logging()
    print_service_banner(
        name,
        [
            f"Role: {ARBITER_ROLE} in {OPS_ROOM} (exclusive lease; standby retries every "
            f"{ROLE_RETRY_S:.0f}s)",
            f"Consent timeout: {consent_timeout_s:.0f}s (SPLITBRAIN_CONSENT_TIMEOUT_S)",
            f"Evidence timeout: {evidence_timeout_s:.0f}s (SPLITBRAIN_EVIDENCE_TIMEOUT_S)",
            "Silent by default: this agent never posts in team rooms.",
        ],
    )
    agent = SwitchAgent(settings.api_base_url, credentials.agent_id, credentials.api_key)
    processor = Arbiter(
        agent=agent,
        state=state,
        name=name,
        consent_timeout_s=consent_timeout_s,
        evidence_timeout_s=evidence_timeout_s,
    )
    return AgentRuntime(agent=agent, processor=processor, name=name, stop=stop)


async def run_forever(settings: Settings, *, name: str = AGENT_NAME) -> None:
    runtime = build_runtime(settings, name=name)
    await runtime.serve()

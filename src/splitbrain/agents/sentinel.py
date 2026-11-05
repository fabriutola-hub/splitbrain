"""Sentinel: watch every team room, detect contradictions, stay silent.

The detection path is the same `Brain` pipeline that `splitbrain eval` runs:
Extractor, Classifier, prefilter, matcher, threshold and SQLite store. Only the
ingestion is new: frames arrive on a queue, extraction is batched, and the
candidate is published to `splitbrain-ops`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .. import bootstrap
from ..config import LLMSettings, Settings, SplitbrainError
from ..core.decision import quoted_sentence
from ..core.matcher import match_report
from ..core.models import (
    Candidate,
    Claim,
    ClaimKind,
    ClaimStatus,
    Evidence,
    Message,
    Relation,
    make_claim_id,
)
from ..core.packets import encode
from ..core.pipeline import CANDIDATE_THRESHOLD, Brain
from ..core.prefilter import prefilter
from ..core.protocol import (
    ConsentPacket,
    ConsentRequestPacket,
    CorrectedPacket,
    DecidedPacket,
    LinkedPacket,
    LinkRequestPacket,
    read_packet,
)
from ..core.store import ClaimStore, pair_id
from ..llm.cassette import CassetteStore
from ..llm.client import LLMClient
from ..switch.client import SwitchAgent
from ..switch.events import (
    ConnectionStateFrame,
    MessageFrame,
    RoomJoinFrame,
    SubscriptionChangedFrame,
    SwitchFrame,
)
from ..tui import CandidateLink, ClaimView, SentinelTui, evidence_step_text
from .base import (
    LOG_FORMAT,
    TUI_LOG_FORMAT,
    AgentRuntime,
    configure_logging,
    print_banner,
    reply_thread,
)

logger = logging.getLogger(__name__)

AGENT_NAME = "splitbrain-sentinel"
OPS_ROOM = "splitbrain-ops"
OWN_AGENT_PREFIX = "splitbrain-"
SILENT_ROOMS = frozenset({OPS_ROOM})
BATCH_SIZE = 8
BATCH_WINDOW_S = 2.0
DB_FILENAME = "sentinel.db"
ARBITER_NAMES = frozenset({"splitbrain-arbiter", "splitbrain-arbiter-b"})
GRANT_WORDS = frozenset({"yes", "y", "sí", "si", "s", "ok", "okay", "agree", "de acuerdo"})
DENY_WORDS = frozenset({"no", "n", "nope", "nah"})


@dataclass(frozen=True, slots=True)
class ConsentPending:
    candidate_id: str
    claim_id: str
    author: str
    room_id: str
    thread_root: str
    ops_thread_id: str
    text: str | None


def ignored_source(message: Message) -> str | None:
    """Our agents, platform traffic and internal rooms are never data."""
    author = message.author.strip().casefold()
    if author.startswith(OWN_AGENT_PREFIX):
        return "message from one of our own agents"
    if (message.sender_kind or "").casefold() == "platform":
        return "platform message"
    room = message.room_name.strip().casefold()
    if room in SILENT_ROOMS or room.startswith("conflict-"):
        return "internal Splitbrain room"
    return None


def _one_line(text: str, limit: int = 220) -> str:
    return " ".join(text.split())[:limit]


def _short(text: str, limit: int = 90) -> str:
    flat = _one_line(text, limit + 3)
    return flat if len(flat) <= limit else flat[:limit] + "..."


class Sentinel:
    """Frame processor for the Sentinel. All heavy work runs outside the SSE loop."""

    def __init__(
        self,
        *,
        agent: SwitchAgent,
        llm: LLMClient,
        store: ClaimStore,
        state: bootstrap.BootstrapState,
        tui: SentinelTui | None = None,
        batch_size: int = BATCH_SIZE,
        batch_window_s: float = BATCH_WINDOW_S,
    ) -> None:
        if OPS_ROOM not in state.rooms:
            raise SplitbrainError("splitbrain-ops is missing from .splitbrain/state.json")
        self.agent = agent
        self.llm = llm
        self.brain = Brain(llm)
        self.store = store
        self.state = state
        self.tui = tui
        self.ops_room_id = state.rooms[OPS_ROOM].room_id
        self.rooms: dict[str, str] = {room.room_id: name for name, room in state.rooms.items()}
        self.channel_types: dict[str, str] = {
            room.room_id: room.channel_type for room in state.rooms.values()
        }
        self.claimed: set[str] = set()
        self.pending: asyncio.Queue[Message] = asyncio.Queue()
        self.stop = asyncio.Event()
        self.worker: asyncio.Task[None] | None = None
        self.batch_size = batch_size
        self.batch_window_s = batch_window_s
        self.messages_processed = 0
        self.candidates_sent = 0
        self.consent_pending: dict[tuple[str, str], ConsentPending] = {}
        self.corrected: set[str] = set()
        self._noted_conflict_rooms: set[str] = set()

    async def start(self) -> None:
        self.worker = asyncio.create_task(self._extraction_loop(), name="sentinel-extraction")
        logger.info("Sentinel ready; ops room %s", self.ops_room_id[:8])

    async def aclose(self) -> None:
        self.stop.set()
        if self.worker is not None:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
            self.worker = None
        await self.store.close()
        await self.llm.aclose()
        if self.tui is not None:
            self.tui.stop()
        logger.info(
            "Sentinel stopped: %d messages processed, %d candidates sent",
            self.messages_processed,
            self.candidates_sent,
        )

    async def on_frame(self, frame: SwitchFrame) -> None:
        if isinstance(frame, ConnectionStateFrame):
            await self._on_connection_state(frame)
        elif isinstance(frame, SubscriptionChangedFrame):
            await self._on_subscription(frame)
        elif isinstance(frame, RoomJoinFrame):
            await self._on_room_join(frame)
        elif isinstance(frame, MessageFrame):
            await self._on_message(frame)

    # ── Room coverage ────────────────────────────────────────────

    async def _refresh_rooms(self) -> None:
        """Resolve room_id -> name for rooms created or joined after the stream."""
        try:
            rooms = await self.agent.op("list_rooms", connection=False)
        except Exception:
            logger.exception("Could not list the Sentinel's rooms")
            return
        entries = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
        for item in entries:
            if not isinstance(item, dict):
                continue
            room_id = str(item.get("room_id") or "")
            name = str(item.get("name") or "")
            if room_id and name:
                self.rooms[room_id] = name
                if item.get("channel_type"):
                    self.channel_types[room_id] = str(item["channel_type"])

    def _note_conflict_room(self, room_id: str) -> None:
        """Stamp the room step when the room appears, not when people decide."""
        if self.tui is None:
            return
        name = self.rooms.get(room_id, "")
        if not name.startswith("conflict-") or name in self._noted_conflict_rooms:
            return
        candidate_id = self.tui.active_candidate
        if not candidate_id or not name.startswith(f"conflict-{candidate_id}"):
            return
        self._noted_conflict_rooms.add(name)
        self.tui.add_step(candidate_id, "room", f"room #{name}")

    async def _claim_room(self, room_id: str) -> None:
        if not room_id or room_id in self.claimed:
            return
        # Mark before awaiting: connect_to_room itself emits subscription_changed.
        self.claimed.add(room_id)
        name = self.rooms.get(room_id, room_id)
        try:
            # act_in holds the per-connection lock while it claims the room.
            async with self.agent.act_in(room_id):
                pass
            logger.info("Claimed room #%s for the event stream", name)
        except Exception:
            logger.exception("Could not claim room #%s; messages there may be missed", name)

    async def _on_connection_state(self, frame: ConnectionStateFrame) -> None:
        logger.info(
            "Switch stream attached: server=%s protocol=%s covered_rooms=%d",
            frame.server.version,
            frame.protocol,
            len(frame.rooms),
        )
        await self._refresh_rooms()
        # Claim the demo rooms up front; rooms created later arrive as
        # subscription_changed / room_join / an unknown room on a message.
        for room in self.state.rooms.values():
            await self._claim_room(room.room_id)
        for room_id in frame.rooms:
            self._note_conflict_room(room_id)
            await self._claim_room(room_id)

    async def _on_subscription(self, frame: SubscriptionChangedFrame) -> None:
        logger.debug("Rooms changed (%s): %d covered", frame.reason or "n/a", len(frame.rooms))
        if any(isinstance(rid, str) and rid not in self.rooms for rid in frame.rooms):
            await self._refresh_rooms()
        for room_id in frame.rooms:
            if isinstance(room_id, str):
                self._note_conflict_room(room_id)
                await self._claim_room(room_id)

    async def _on_room_join(self, frame: RoomJoinFrame) -> None:
        member = frame.payload.member_name or ""
        own = (
            member.casefold() == AGENT_NAME.casefold()
            or frame.payload.member == self.agent.agent_id
        )
        if not own:
            logger.debug("room_join: %s in %s", member, frame.room_id[:8])
            return
        logger.info("Our agent joined a room; claiming it")
        await self._refresh_rooms()
        self._note_conflict_room(frame.room_id)
        await self._claim_room(frame.room_id)

    # ── Ingestion ────────────────────────────────────────────────────────────

    def _note_internal(self) -> None:
        if self.tui is not None:
            self.tui.add_internal()

    def _note_packet(self, kind: str, payload: Any) -> None:
        """Turn ops packets into the lifecycle the viewer can follow."""
        if self.tui is None:
            return
        candidate_id = getattr(payload, "candidate_id", None)
        if not isinstance(candidate_id, str) or not candidate_id:
            return
        step = self.tui.add_step
        if kind == "evidence" and isinstance(payload, Evidence):
            step(candidate_id, "evidence", f"evidence: {evidence_step_text(payload)}")
        elif kind == "verdict":
            step(
                candidate_id,
                "verdict",
                f"verdict {str(getattr(payload, 'verdict', '')).upper()}",
            )
        elif kind == "consent_request":
            step(
                candidate_id,
                "consent_asked",
                f"consent asked @{getattr(payload, 'author', '?')}",
            )
        elif kind == "consent":
            word = "granted" if getattr(payload, "granted", False) else "denied"
            step(
                candidate_id,
                "consent_answer",
                f"consent {word} @{getattr(payload, 'author', '?')}",
            )
        elif kind == "link_request":
            name = self.rooms.get(getattr(payload, "conflict_room_id", ""), "")
            if name.startswith("conflict-"):
                step(candidate_id, "room", f"room #{name}")

    async def _on_message(self, frame: MessageFrame) -> None:
        # Inter-agent packets are control traffic, never detection input.
        packet = read_packet(frame.payload.body, frame.payload.sender_name)
        if packet is not None:
            self._note_internal()
            self._note_packet(*packet)
            await self._handle_packet(frame, packet)
            return
        if await self._consent_reply(frame):
            # A person's consent answer is still worth showing in the demo.
            if self.tui is not None:
                self.tui.add_message(
                    self.rooms.get(frame.room_id, frame.room_id),
                    frame.payload.sender_name,
                    frame.payload.body,
                    True,
                    "consent answer",
                )
            return
        payload = frame.payload
        room_id = frame.room_id
        if room_id not in self.rooms:
            # A room created or joined after the stream opened: claim it before
            # its history moves past the cursor, and keep this message anyway.
            await self._refresh_rooms()
            self._note_conflict_room(room_id)
            await self._claim_room(room_id)
            if room_id not in self.rooms:
                logger.warning("Unknown room %s; using its id as the room name", room_id[:8])
        room_name = self.rooms.get(room_id, room_id)
        message = Message(
            message_id=payload.message_id,
            room_id=room_id,
            room_name=room_name,
            channel_type=frame.channel_type or self.channel_types.get(room_id, "channel_public"),
            thread_id=payload.thread_id,
            author=payload.sender_name,
            sender_kind=payload.sender_kind,
            ts=payload.timestamp,
            text=payload.body,
        )

        source = ignored_source(message)
        if source is not None:
            self._note_internal()
            logger.debug("Ignored #%s %s: %s", room_name, message.author, source)
            return
        decision = prefilter(message)
        if self.tui is not None:
            self.tui.add_message(
                room_name, message.author, message.text, decision.keep, decision.reason
            )
        if not decision.keep:
            logger.debug("Ignored #%s %s: %s", room_name, message.author, decision.reason)
            return
        if await self.store.is_processed(message.message_id):
            logger.info("Message %s already processed; skipping (idempotency)", message.message_id)
            return
        await self.pending.put(message)
        logger.info("Queued #%s %s: %s", room_name, message.author, _short(message.text))

    async def _extraction_loop(self) -> None:
        """Batch up to 8 messages or 2 s, then call the model."""
        loop = asyncio.get_running_loop()
        while not self.stop.is_set():
            try:
                first = await asyncio.wait_for(self.pending.get(), timeout=0.2)
            except TimeoutError:
                continue
            batch = [first]
            deadline = loop.time() + self.batch_window_s
            while len(batch) < self.batch_size:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self.pending.get(), timeout=remaining))
                except TimeoutError:
                    break
            try:
                await self.analyze_messages(batch)
            except Exception:
                logger.exception("Extraction batch of %d message(s) failed", len(batch))

    async def analyze_messages(self, messages: list[Message]) -> None:
        """The eval pipeline, unchanged: prefilter, extract, match, classify, candidate."""
        fresh: list[Message] = []
        for message in messages:
            if await self.store.is_processed(message.message_id):
                logger.info("Already processed message %s (idempotency)", message.message_id)
                continue
            fresh.append(message)
        if not fresh:
            return

        claims_by_message = await self.brain.extractor.extract_batch(fresh)
        for message in fresh:
            claims = claims_by_message[message.message_id]
            for claim in claims:
                if self.tui is not None:
                    self.tui.add_claim(self._claim_view(claim))
            logger.info(
                "Extracted %d claim(s) from #%s: %s",
                len(claims),
                message.room_name,
                ", ".join(f"{c.subject_key}/{c.scope_key}={c.value}" for c in claims) or "none",
            )
            stored = await self.store.active_claims()
            for new_claim in claims:
                # Same "first match" rule as Brain._analyze, so eval describes this.
                report = match_report(new_claim, stored)
                if not report.matches:
                    continue
                other = report.matches[0]
                identifier = pair_id(other, new_claim)
                if await self.store.has_pair(identifier):
                    logger.debug("Pair already seen; not re-surfacing it")
                    continue
                await self.store.mark_pair(identifier)
                classification = await self.brain.classifier.classify(other, new_claim)
                if not (
                    classification.relation == Relation.CONTRADICTION
                    and classification.confidence >= CANDIDATE_THRESHOLD
                ):
                    # Silence: no team room post, no ops post, just a log line.
                    logger.info(
                        "No alert: %s (confidence %.2f): %s",
                        classification.relation,
                        classification.confidence,
                        classification.reason,
                    )
                    continue
                candidate = Candidate(
                    id=self._candidate_id(other, new_claim),
                    claim_a=other,
                    claim_b=new_claim,
                    confidence=classification.confidence,
                    reason=classification.reason,
                    created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                )
                await self.store.add_candidate(candidate)
                await self._publish(candidate)
            for claim in claims:
                await self.store.add_claim(claim)
            await self.store.mark_processed(message.message_id)
            self.messages_processed += 1

    # ── Consent, corrections and the link fallback ──────────────────────

    async def _handle_packet(self, frame: MessageFrame, packet: tuple[str, Any]) -> None:
        kind, payload = packet
        if frame.payload.sender_name not in ARBITER_NAMES:
            return
        if kind == "consent_request" and isinstance(payload, ConsentRequestPacket):
            await self._ask_consent(frame, payload)
        elif kind == "decided" and isinstance(payload, DecidedPacket):
            await self._apply_corrections(frame, payload)
        elif kind == "link_request" and isinstance(payload, LinkRequestPacket):
            await self._answer_link_request(frame, payload)

    async def _ask_consent(self, frame: MessageFrame, request: ConsentRequestPacket) -> None:
        claim = await self.store.claim_by_id(request.claim_id)
        room_id = claim.room_id if claim is not None else request.room_id
        thread_root = (
            (claim.thread_id or claim.message_id) if claim is not None else request.thread_id
        )
        if not room_id or not thread_root:
            raise SplitbrainError(
                f"Consent request for unknown claim {request.claim_id}: "
                "the Sentinel cannot find the original thread."
            )
        other = request.other_author or "the other person"
        question = (
            f"@{request.author} Splitbrain found that this message conflicts with a "
            f"statement from another team. May I quote it in a private resolution "
            f'room with @{other}? Reply "yes" or "no" here.'
        )
        await self.agent.post(room_id, question, thread_id=thread_root)
        if self.tui is not None:
            self.tui.add_step(
                request.candidate_id,
                "consent_asked",
                f"consent asked @{request.author}",
            )
        self.consent_pending[(room_id, thread_root)] = ConsentPending(
            candidate_id=request.candidate_id,
            claim_id=request.claim_id,
            author=request.author,
            room_id=room_id,
            thread_root=thread_root,
            ops_thread_id=reply_thread(frame),
            text=claim.text if claim is not None else None,
        )
        logger.info(
            "Asked @%s for consent in #%s thread %s (%s)",
            request.author,
            self.rooms.get(room_id, room_id[:8]),
            thread_root[:12],
            request.candidate_id,
        )

    async def _consent_reply(self, frame: MessageFrame) -> bool:
        payload = frame.payload
        key = (frame.room_id, payload.thread_id or "")
        pending = self.consent_pending.get(key)
        if pending is None or payload.sender_name != pending.author:
            return False
        if payload.sender_name.startswith(OWN_AGENT_PREFIX):
            return False
        if (payload.sender_kind or "").casefold() == "platform":
            return False
        if payload.message_id == pending.thread_root:
            return False
        answer = payload.body.strip().casefold().strip(" \t\r\n.!¿?¡")
        granted = answer in GRANT_WORDS
        if not granted and answer not in DENY_WORDS:
            # No private quote is ever revealed without an explicit yes.
            logger.warning(
                "Consent answer %r from @%s is not yes/no; treating it as denied",
                payload.body,
                payload.sender_name,
            )
        del self.consent_pending[key]
        consent = ConsentPacket(
            candidate_id=pending.candidate_id,
            claim_id=pending.claim_id,
            author=pending.author,
            granted=granted,
            text=pending.text if granted else None,
        )
        word = "granted" if granted else "denied"
        readable = (
            f"Consent {word} by @{pending.author} for claim {pending.claim_id} "
            f"of {pending.candidate_id.upper()}. "
            + (
                "The verbatim quote is attached in the packet for the Arbiter only."
                if granted
                else "The quote stays withheld."
            )
        )
        await self.agent.targeted(
            self.ops_room_id,
            readable + "\n" + encode("consent", consent),
            target_roles=["arbiter"],
            thread_id=pending.ops_thread_id,
        )
        if self.tui is not None:
            self.tui.add_step(
                pending.candidate_id,
                "consent_answer",
                f"consent {word} @{pending.author}",
            )
        logger.info("Consent %s for %s by @%s", word, pending.candidate_id, pending.author)
        return True

    async def _apply_corrections(self, frame: MessageFrame, decided: DecidedPacket) -> None:
        if decided.candidate_id in self.corrected:
            return
        self.corrected.add(decided.candidate_id)
        if self.tui is not None:
            self.tui.add_step(decided.candidate_id, "room", f"room #{decided.conflict_room_name}")
            self.tui.add_step(
                decided.candidate_id,
                "decided",
                f'DECIDED "{decided.decision.text}"',
            )
        authors = " and ".join(f"@{name}" for name in decided.authors)
        topic = decided.subject
        if decided.scope and decided.scope != "*":
            topic = f"{topic} for {decided.scope}"
        body = (
            f"Update: {authors} resolved a conflict about {topic} in "
            f"#{decided.conflict_room_name}. Decision: {quoted_sentence(decided.decision.text)} "
            "Please use this from now on."
        )
        for origin in decided.origins:
            await self.agent.post(origin.room_id, body, thread_id=origin.thread_id)
            await self.store.set_status(origin.claim_id, ClaimStatus.RESOLVED)
        decision = decided.decision
        await self.store.add_claim(
            Claim(
                kind=ClaimKind.DECISION,
                subject=decided.subject,
                subject_key=decided.subject_key,
                scope=decided.scope,
                scope_key=decided.scope_key,
                value=decision.text,
                polarity="affirm",
                effective_date=None,
                confidence=1.0,
                id=make_claim_id(f"decision:{decided.candidate_id}", 0),
                room_id=decided.conflict_room,
                room_name=decided.conflict_room_name,
                channel_type="channel_public",
                message_id=f"decision:{decided.candidate_id}",
                thread_id=None,
                author=decision.proposed_by,
                ts=int(time.time() * 1000),
                text=decision.text,
                status=ClaimStatus.ACTIVE,
            )
        )
        rooms = [f"#{origin.room_name}" for origin in decided.origins]
        packet = CorrectedPacket(
            candidate_id=decided.candidate_id,
            conflict_room=decided.conflict_room,
            conflict_room_name=decided.conflict_room_name,
            rooms=[origin.room_name for origin in decided.origins],
        )
        await self.agent.targeted(
            self.ops_room_id,
            f"Corrections posted in {', '.join(rooms)} for {decided.candidate_id.upper()}.\n"
            + encode("corrected", packet),
            target_roles=["arbiter"],
            thread_id=reply_thread(frame),
        )
        if self.tui is not None:
            self.tui.add_step(
                decided.candidate_id,
                "corrections",
                f"corrections posted in {', '.join(rooms)}",
            )
        logger.info("Corrections posted in %s for %s", ", ".join(rooms), decided.candidate_id)

    async def _answer_link_request(self, frame: MessageFrame, request: LinkRequestPacket) -> None:
        labels: list[str] = []
        if self.tui is not None:
            name = self.rooms.get(request.conflict_room_id, "")
            if name.startswith("conflict-"):
                self.tui.add_step(request.candidate_id, "room", f"room #{name}")
        for target in request.origins:
            await self.agent.op(
                "link_rooms",
                source_room_id=request.conflict_room_id,
                target_room_id=target.room_id,
                label=target.label,
            )
            labels.append(target.label)
        packet = LinkedPacket(
            candidate_id=request.candidate_id,
            conflict_room_id=request.conflict_room_id,
            labels=labels,
        )
        await self.agent.targeted(
            self.ops_room_id,
            f"Sentinel created the room links for {request.candidate_id.upper()}: "
            f"{', '.join(labels)}.\n" + encode("linked", packet),
            target_roles=["arbiter"],
            thread_id=reply_thread(frame),
        )
        logger.info("Sentinel created %d link(s) for %s", len(labels), request.candidate_id)

    # ── Publishing (silence by default) ──────────────────────────

    async def _publish(self, candidate: Candidate) -> None:
        payload = self._candidate_payload(candidate)
        body = self._candidate_body(payload)
        result = await self.agent.targeted(self.ops_room_id, body, target_roles=["arbiter"])
        event_id = result.get("event_id", "?") if isinstance(result, dict) else "?"
        self.candidates_sent += 1
        logger.info(
            "CANDIDATE %s sent to arbiter in splitbrain-ops (event %s): %s",
            candidate.id,
            event_id,
            candidate.reason,
        )
        if self.tui is not None:
            self.tui.add_candidate(
                CandidateLink(
                    candidate_id=candidate.id,
                    a=self._claim_view(candidate.claim_a),
                    b=self._claim_view(candidate.claim_b),
                    confidence=candidate.confidence,
                    reason=candidate.reason,
                )
            )
            self.tui.add_step(
                candidate.id,
                "candidate",
                f"candidate sent ({candidate.claim_a.subject} for {candidate.claim_a.scope})",
            )

    @staticmethod
    def _candidate_payload(candidate: Candidate) -> dict[str, Any]:
        """A private-room quote never leaves the room, not even in ops.

        The stored Claim keeps its verbatim text (needed for corrections);
        the outbound packet replaces it with a null text and a withheld flag.
        """
        data = candidate.model_dump(mode="json")
        private_texts: list[str] = []
        for side in ("claim_a", "claim_b"):
            claim = data[side]
            if claim.get("channel_type") == "channel_private":
                private_texts.append(claim.get("text") or "")
                claim["text"] = None
                claim["text_withheld"] = True
            else:
                claim["text_withheld"] = False
        # A classifier reason may echo the message; scrub exact quotes from it too.
        reason = data["reason"]
        for text in private_texts:
            if text and text in reason:
                reason = reason.replace(text, "quote withheld until the author consents")
        data["reason"] = reason
        return data

    @staticmethod
    def _readable_claim(claim: dict[str, Any]) -> str:
        if claim["text_withheld"]:
            return (
                f"#{claim['room_name']} (private), {claim['author']}: quote withheld until "
                f"the author consents. Subject: {_one_line(claim['subject'], 80)}. "
                f"Extracted value: {_one_line(claim['value'], 80)}."
            )
        return f'#{claim["room_name"]}, {claim["author"]}: "{_one_line(claim["text"])}"'

    @classmethod
    def _candidate_body(cls, data: dict[str, Any]) -> str:
        a, b = data["claim_a"], data["claim_b"]
        lines = [
            f"Possible contradiction {data['id']}: two teams say different things "
            f"about {a['subject']}.",
            "",
            cls._readable_claim(a),
            cls._readable_claim(b),
            "",
            f"Scope: {a['scope']}. Classifier confidence: {data['confidence']:.2f}.",
            f"Reason: {data['reason']}",
            "Sent to the arbiter role for verification. Nothing was posted in either team room.",
        ]
        # One final packet line, encoded by core/packets.py (no Markdown tables).
        return "\n".join(lines) + "\n" + encode("candidate", data)

    @staticmethod
    def _candidate_id(a: Claim, b: Claim) -> str:
        # Derived from the pair: a restart never renumbers or re-sends it.
        digest = hashlib.sha256(pair_id(a, b).encode("utf-8")).hexdigest()
        return f"sb-{int(digest[:8], 16) % 10_000:04d}"

    @staticmethod
    def _claim_view(claim: Claim) -> ClaimView:
        return ClaimView(
            room=claim.room_name,
            author=claim.author,
            subject=claim.subject,
            scope=claim.scope,
            value=claim.value,
            key=claim.id,
        )


def build_runtime(
    settings: Settings,
    *,
    tui_enabled: bool = False,
    stop: asyncio.Event | None = None,
) -> AgentRuntime:
    """Wire the detection pipeline and the protocol client into one agent."""
    state = bootstrap.load_state(settings)
    credentials = state.agents.get(AGENT_NAME)
    if credentials is None or not state.rooms:
        raise SplitbrainError("Bootstrap is incomplete; run 'uv run splitbrain bootstrap' first.")

    llm_settings = LLMSettings.load()
    cassettes = CassetteStore(
        llm_settings.cassettes_dir, model=llm_settings.model, mode=llm_settings.mode
    )
    llm = LLMClient(llm_settings, cassettes)
    db_path = settings.paths.state_dir / DB_FILENAME
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = ClaimStore(db_path)

    view = SentinelTui(llm_settings) if tui_enabled else None
    configure_logging(
        handler=view.log_handler() if view is not None else None,
        log_format=TUI_LOG_FORMAT if view is not None else LOG_FORMAT,
    )
    print_banner(AGENT_NAME, llm_settings)
    if view is not None:
        view.start()

    agent = SwitchAgent(settings.api_base_url, credentials.agent_id, credentials.api_key)
    sentinel = Sentinel(agent=agent, llm=llm, store=store, state=state, tui=view)
    return AgentRuntime(
        agent=agent, processor=sentinel, name=AGENT_NAME, llm=llm_settings, stop=stop
    )


async def run_forever(settings: Settings, *, tui: bool = False) -> None:
    runtime = build_runtime(settings, tui_enabled=tui)
    await runtime.serve()

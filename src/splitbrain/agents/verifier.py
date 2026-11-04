"""M5 Verifier: answer `sb:evidence_request` from the ops room's GitHub reference.

It holds the (non-exclusive) `verifier` role, reads the repository URL from the
reference attached to `splitbrain-ops`, and posts `sb:evidence` back in the
candidate's thread. Live network failures raise a clear error; they never fall
back silently to the fixture.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .. import bootstrap
from ..config import Settings, SplitbrainError
from ..core.models import Evidence
from ..core.packets import encode
from ..core.protocol import EvidenceRequestPacket, read_packet
from ..evidence.github import (
    EvidenceSettings,
    GitHubEvidence,
    GitHubSnapshot,
    SplitbrainEvidenceError,
    build_evidence,
)
from ..switch.client import SwitchAgent
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

AGENT_NAME = "splitbrain-verifier"
VERIFIER_ROLE = "verifier"
ARBITER_NAMES = frozenset({"splitbrain-arbiter", "splitbrain-arbiter-b"})


class Verifier:
    def __init__(
        self,
        *,
        agent: SwitchAgent,
        state: bootstrap.BootstrapState,
        evidence_settings: EvidenceSettings,
    ) -> None:
        ops = state.rooms.get(OPS_ROOM)
        if ops is None:
            raise SplitbrainError("splitbrain-ops is missing from .splitbrain/state.json")
        self.agent = agent
        self.state = state
        self.ops_room_id = ops.room_id
        self.evidence_settings = evidence_settings
        self.coverage = RoomCoverage(agent, self.ops_room_id, own_name=AGENT_NAME)
        self.provider: GitHubEvidence | None = None
        self.repo_url: str | None = None
        self.answered: set[str] = set()
        self.stop = asyncio.Event()

    async def start(self) -> None:
        logger.info("Verifier ready; ops room %s", self.ops_room_id[:8])

    async def aclose(self) -> None:
        self.stop.set()
        if self.provider is not None:
            await self.provider.aclose()
        logger.info("Verifier stopped; %d evidence answers sent", len(self.answered))

    async def on_frame(self, frame: SwitchFrame) -> None:
        if isinstance(frame, ConnectionStateFrame):
            await self._on_connection_state(frame)
        elif isinstance(frame, SubscriptionChangedFrame):
            await self.coverage.on_subscription(frame)
        elif isinstance(frame, RoomJoinFrame):
            await self.coverage.on_room_join(frame)
        elif isinstance(frame, MessageFrame):
            await self._on_message(frame)

    async def _on_connection_state(self, frame: ConnectionStateFrame) -> None:
        await self.coverage.on_connection_state(frame)
        await self._load_reference()
        await self._assume_role()

    async def _load_reference(self) -> None:
        context = await self.agent.op("connect_to_room", room_id=self.ops_room_id)
        references: list[dict[str, Any]] = context.get("references") or []
        urls: list[str] = []
        for reference in references:
            if reference.get("type") != "github":
                continue
            value = reference.get("value") or {}
            for url in value.get("urls") or []:
                if isinstance(url, str) and url.strip():
                    urls.append(url.strip())
        if not urls:
            raise SplitbrainError(
                "No GitHub reference with a URL is attached to splitbrain-ops; "
                "run 'uv run splitbrain bootstrap' again."
            )
        self.repo_url = urls[0]
        if self.provider is not None:
            await self.provider.aclose()
        self.provider = GitHubEvidence(self.evidence_settings, self.repo_url)
        print(self.evidence_settings.banner(self.repo_url), flush=True)
        logger.info("GitHub evidence repository: %s", self.repo_url)

    async def _assume_role(self) -> None:
        try:
            async with self.agent.act_in(self.ops_room_id):
                await self.agent.op("assume_role", role=VERIFIER_ROLE)
            logger.info("Assumed the %s role in splitbrain-ops", VERIFIER_ROLE)
        except Exception:
            # A shared role can already be held by our own earlier session;
            # the stream still sees every ops message, so we can keep serving.
            logger.exception("Could not assume %s role; serving unaddressed traffic", VERIFIER_ROLE)

    async def _on_message(self, frame: MessageFrame) -> None:
        if frame.room_id not in self.coverage.rooms:
            await self.coverage.ensure_known(frame.room_id)
        packet = read_packet(frame.payload.body, frame.payload.sender_name)
        if packet is None:
            return
        kind, payload = packet
        if kind != "evidence_request" or not isinstance(payload, EvidenceRequestPacket):
            return
        if frame.payload.sender_name not in ARBITER_NAMES:
            logger.warning("Ignoring an evidence request from %s", frame.payload.sender_name)
            return
        if frame.room_id != self.ops_room_id:
            logger.warning("Ignoring an evidence request outside splitbrain-ops")
            return
        if payload.candidate_id in self.answered:
            return
        if self.provider is None:
            raise SplitbrainError("Evidence request arrived before the GitHub reference was loaded")
        subject = payload.subject or payload.subject_key
        try:
            snapshot: GitHubSnapshot = await self.provider.snapshot(subject)
            evidence = build_evidence(
                payload.candidate_id,
                subject,
                snapshot,
                source="fixture" if self.evidence_settings.mode == "fixture" else "github",
            )
        except SplitbrainEvidenceError as exc:
            logger.error("EVIDENCE ERROR for %s: %s", payload.candidate_id, exc)
            await self.agent.post(
                self.ops_room_id,
                f"EVIDENCE ERROR for {payload.candidate_id}: {exc}",
                thread_id=reply_thread(frame),
            )
            raise
        body = self._body(payload, evidence)
        await self.agent.targeted(
            self.ops_room_id,
            body,
            target_roles=["arbiter"],
            thread_id=reply_thread(frame),
        )
        self.answered.add(payload.candidate_id)
        logger.info(
            "Evidence %s for %s: %s", evidence.status, payload.candidate_id, evidence.summary
        )

    @staticmethod
    def _body(request: EvidenceRequestPacket, evidence: Evidence) -> str:
        lines = [
            f"Evidence for {request.candidate_id.upper()} "
            f"({request.subject}, scope {request.scope}):",
            evidence.summary,
            f"Source: {evidence.source}. Status: {evidence.status}.",
        ]
        for item in evidence.items:
            milestone = f", milestone {item.milestone}" if item.milestone else ""
            lines.append(f"- {item.title} [{item.state}{milestone}] {item.url}")
        lines.append("This is independent evidence, not a decision about who is right.")
        return "\n".join(lines) + "\n" + encode("evidence", evidence)


def build_runtime(
    settings: Settings, *, stop: asyncio.Event | None = None, name: str = AGENT_NAME
) -> AgentRuntime:
    state = bootstrap.load_state(settings)
    credentials = state.agents.get(name)
    if credentials is None or not state.rooms:
        raise SplitbrainError("Bootstrap is incomplete; run 'uv run splitbrain bootstrap' first.")
    evidence_settings = EvidenceSettings.load(settings.paths)
    configure_logging()
    print_service_banner(
        name,
        [
            f"Role: {VERIFIER_ROLE} in {OPS_ROOM} (non-exclusive)",
            f"Evidence mode: {evidence_settings.mode} (SPLITBRAIN_EVIDENCE_MODE)",
            "Silent by default: this agent never posts in team rooms.",
        ],
    )
    agent = SwitchAgent(settings.api_base_url, credentials.agent_id, credentials.api_key)
    processor = Verifier(agent=agent, state=state, evidence_settings=evidence_settings)
    return AgentRuntime(agent=agent, processor=processor, name=name, stop=stop)


async def run_forever(settings: Settings, *, name: str = AGENT_NAME) -> None:
    runtime = build_runtime(settings, name=name)
    await runtime.serve()

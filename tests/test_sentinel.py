"""M4 Sentinel: the M3 pipeline, silence, packets and idempotency (no network)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from splitbrain import bootstrap
from splitbrain.agents import sentinel as mod
from splitbrain.config import SplitbrainError
from splitbrain.core.models import Candidate, Claim, Message
from splitbrain.core.packets import decode
from splitbrain.core.store import ClaimStore
from splitbrain.switch.events import MessageFrame, MessagePayload
from splitbrain.tui import SentinelTui

ROOM_IDS = {
    "sales": "r-sales",
    "engineering": "r-engineering",
    "support": "r-support",
    "finance": "r-finance",
    "splitbrain-ops": "r-ops",
}


class FakeAgent:
    agent_id = "fake-agent-id"

    def __init__(self) -> None:
        self.claimed: list[str] = []
        self.targeted_calls: list[dict[str, Any]] = []
        self.ops: list[tuple[str, dict[str, Any]]] = []

    async def op(self, name: str, /, **args: Any) -> Any:
        self.ops.append((name, args))
        if name == "list_rooms":
            return [{"room_id": rid, "name": name} for name, rid in ROOM_IDS.items()]
        return {}

    @asynccontextmanager
    async def act_in(self, room_id: str):
        self.claimed.append(room_id)
        yield self

    async def targeted(
        self,
        room_id: str,
        body: str,
        *,
        target_names: list[str] | None = None,
        target_roles: list[str] | None = None,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        self.targeted_calls.append(
            {
                "room_id": room_id,
                "body": body,
                "target_names": target_names,
                "target_roles": target_roles,
                "thread_id": thread_id,
            }
        )
        return {"event_id": "sw_fake"}

    async def aclose(self) -> None:
        return None


def make_state() -> bootstrap.BootstrapState:
    return bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(
                room_id=rid,
                channel_type="channel_private" if name == "engineering" else "channel_public",
            )
            for name, rid in ROOM_IDS.items()
        }
    )


def messages() -> tuple[Message, Message]:
    return (
        Message(
            message_id="m-a",
            room_id=ROOM_IDS["sales"],
            room_name="sales",
            author="maria",
            text=(
                "Morning! Big one: confirmed with Acme that SSO will be live for them "
                "on December 1."
            ),
        ),
        Message(
            message_id="m-b",
            room_id=ROOM_IDS["engineering"],
            room_name="engineering",
            channel_type="channel_private",
            author="tomas",
            text="Heads up: we're pulling SSO out of Q4. The auth migration has to land first.",
        ),
    )


def extraction_reply(pair: tuple[Message, Message]) -> dict[str, Any]:
    first, second = pair
    return {
        "results": [
            {
                "message_id": first.message_id,
                "claims": [
                    {
                        "kind": "commitment",
                        "subject": "SSO",
                        "subject_key": "sso",
                        "scope": "Acme",
                        "scope_key": "acme",
                        "value": "live on 2026-12-01",
                        "polarity": "affirm",
                        "effective_date": "2026-12-01",
                        "confidence": 0.95,
                    }
                ],
            },
            {
                "message_id": second.message_id,
                "claims": [
                    {
                        "kind": "decision",
                        "subject": "single sign-on",
                        "subject_key": "sso",
                        "scope": "*",
                        "scope_key": "*",
                        "value": "removed from Q4 delivery",
                        "polarity": "negate",
                        "effective_date": None,
                        "confidence": 0.9,
                    }
                ],
            },
        ]
    }


def classification(relation: str, confidence: float = 0.94) -> dict[str, Any]:
    return {
        "relation": relation,
        "confidence": confidence,
        "reason": "Sales promised Acme SSO in December while engineering removed it from Q4.",
    }


def make_sentinel(
    llm: Any, store: ClaimStore, agent: FakeAgent, *, tui: SentinelTui | None = None
) -> mod.Sentinel:
    return mod.Sentinel(
        agent=agent,  # type: ignore[arg-type]
        llm=llm,
        store=store,
        state=make_state(),
        tui=tui,
        batch_window_s=0.0,
    )


async def test_candidate_is_sent_only_to_ops_with_a_packet_last_line(
    llm_factory, tmp_path: Path
) -> None:
    pair = messages()
    llm, transport, _, _ = llm_factory(
        [extraction_reply(pair), classification("contradiction")], mode="live"
    )
    agent = FakeAgent()
    store = ClaimStore(tmp_path / "sentinel.db")
    view = SentinelTui()
    sentinel = make_sentinel(llm, store, agent, tui=view)
    await sentinel.start()
    try:
        await sentinel.analyze_messages(list(pair))
        assert len(agent.targeted_calls) == 1
        call = agent.targeted_calls[0]
        assert call["room_id"] == ROOM_IDS["splitbrain-ops"]
        assert call["target_roles"] == ["arbiter"]
        assert call["target_names"] is None
        assert "|" not in call["body"]  # no Markdown tables
        lines = call["body"].splitlines()
        assert lines[-1].startswith("sb:candidate ")
        kind, data = decode(lines[-1])
        assert kind == "candidate" and data["id"].startswith("sb-")
        assert data["claim_a"]["room_name"] == "sales"
        assert data["claim_b"]["room_name"] == "engineering"
        # SPEC 3.3: the private-room quote never reaches splitbrain-ops.
        assert pair[1].text not in call["body"]
        assert "quote withheld until the author consents" in call["body"]
        assert data["claim_b"]["text"] is None
        assert data["claim_b"]["text_withheld"] is True
        assert data["claim_a"]["text_withheld"] is False
        assert data["claim_a"]["text"] == pair[0].text
        assert view.candidates == 1 and view.link is not None
        assert len(transport.calls) == 2  # one batched extraction + one classification
    finally:
        await sentinel.aclose()


async def test_non_contradiction_is_silent(llm_factory, tmp_path: Path) -> None:
    pair = messages()
    llm, _, _, _ = llm_factory([extraction_reply(pair), classification("compatible")], mode="live")
    agent = FakeAgent()
    sentinel = make_sentinel(llm, ClaimStore(tmp_path / "sentinel.db"), agent)
    await sentinel.start()
    try:
        await sentinel.analyze_messages(list(pair))
        assert agent.targeted_calls == []
        assert sentinel.candidates_sent == 0
    finally:
        await sentinel.aclose()


async def test_restart_does_not_reprocess_or_resend(llm_factory, tmp_path: Path) -> None:
    pair = messages()
    db = tmp_path / "sentinel.db"
    llm, _, _, _ = llm_factory(
        [extraction_reply(pair), classification("contradiction")], mode="live"
    )
    first_agent = FakeAgent()
    first = make_sentinel(llm, ClaimStore(db), first_agent)
    await first.start()
    try:
        await first.analyze_messages(list(pair))
        assert len(first_agent.targeted_calls) == 1
    finally:
        await first.aclose()

    # A fresh process with the same on-disk store: no model calls, no re-send.
    second_llm, transport, _, _ = llm_factory([], mode="live")
    second_agent = FakeAgent()
    second = make_sentinel(second_llm, ClaimStore(db), second_agent)
    await second.start()
    try:
        await second.analyze_messages(list(pair))
        assert transport.calls == []
        assert second_agent.targeted_calls == []
        assert second.messages_processed == 0
    finally:
        await second.aclose()


async def test_ignored_sources_never_reach_the_extraction_queue(
    llm_factory, tmp_path: Path
) -> None:
    llm, transport, _, _ = llm_factory([], mode="live")
    agent = FakeAgent()
    view = SentinelTui()
    sentinel = make_sentinel(llm, ClaimStore(tmp_path / "sentinel.db"), agent, tui=view)

    def frame(
        room: str, author: str, body: str, *, kind: str | None = None, mid: str
    ) -> MessageFrame:
        return MessageFrame(
            kind="message",
            sequence=1,
            room_id=ROOM_IDS[room],
            channel_type="channel_public",
            payload=MessagePayload(message_id=mid, sender_name=author, sender_kind=kind, body=body),
        )

    cases = [
        frame("sales", "splitbrain-arbiter", "SSO ships on December 1 for Acme", mid="sw1"),
        frame("sales", "maria", "SSO ships on December 1 for Acme", kind="platform", mid="sw2"),
        frame("splitbrain-ops", "maria", "SSO ships on December 1 for Acme", mid="sw3"),
        frame("sales", "maria", "happy birthday everyone", mid="sw4"),
    ]
    await sentinel.start()
    try:
        for item in cases:
            await sentinel.on_frame(item)
        assert sentinel.pending.empty()
        assert transport.calls == []
        assert view.filtered == len(cases)
        assert agent.targeted_calls == []
    finally:
        await sentinel.aclose()


async def test_unknown_room_is_claimed_without_losing_the_message(
    llm_factory, tmp_path: Path
) -> None:
    llm, _, _, _ = llm_factory([], mode="live")
    agent = FakeAgent()
    sentinel = make_sentinel(llm, ClaimStore(tmp_path / "sentinel.db"), agent)
    frame = MessageFrame(
        kind="message",
        sequence=2,
        room_id="r-new-room",
        channel_type="channel_public",
        payload=MessagePayload(
            message_id="sw-new",
            sender_name="maria",
            body="We will ship SSO on December 1 for Acme.",
        ),
    )
    await sentinel.start()
    try:
        await sentinel.on_frame(frame)
        assert "r-new-room" in agent.claimed
        assert sentinel.pending.qsize() == 1
    finally:
        await sentinel.aclose()


def _candidate(
    pair: tuple[Message, Message], *, private_b: bool = True, reason: str = "Two dates."
) -> Candidate:
    def claim(message: Message, index: int, channel_type: str) -> Claim:
        return Claim(
            id=f"clm_{index}",
            room_id=message.room_id,
            room_name=message.room_name,
            channel_type=channel_type,
            message_id=message.message_id,
            author=message.author,
            text=message.text,
            kind="commitment",
            subject="SSO",
            subject_key="sso",
            scope="Acme",
            scope_key="acme",
            value="live on December 1",
            polarity="affirm",
            effective_date=None,
            confidence=0.95,
        )

    a, b = pair
    return Candidate(
        id="sb-0001",
        claim_a=claim(a, 1, "channel_public"),
        claim_b=claim(b, 2, "channel_private" if private_b else "channel_public"),
        confidence=0.9,
        reason=reason,
        created_at="2026-11-04T10:00:00+00:00",
    )


def test_public_claims_keep_their_verbatim_text() -> None:
    pair = messages()
    data = mod.Sentinel._candidate_payload(_candidate(pair, private_b=False))
    for side, message in zip(("claim_a", "claim_b"), pair, strict=True):
        assert data[side]["text"] == message.text
        assert data[side]["text_withheld"] is False
    body = mod.Sentinel._candidate_body(data)
    assert pair[0].text in body and pair[1].text in body


def test_reason_echoing_a_private_quote_is_scrubbed() -> None:
    pair = messages()
    reason = f"Sales promised December 1 but {pair[1].text}"
    data = mod.Sentinel._candidate_payload(_candidate(pair, reason=reason))
    assert pair[1].text not in data["reason"]
    assert "quote withheld" in data["reason"]


def test_ops_room_is_required() -> None:
    with pytest.raises(SplitbrainError, match="splitbrain-ops"):
        mod.Sentinel(
            agent=FakeAgent(),  # type: ignore[arg-type]
            llm=object(),  # type: ignore[arg-type]
            store=object(),  # type: ignore[arg-type]
            state=bootstrap.BootstrapState(),
        )

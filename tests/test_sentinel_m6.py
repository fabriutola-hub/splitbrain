"""Sentinel: consent in the author's thread, corrections in the origin threads."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from splitbrain import bootstrap
from splitbrain.agents import sentinel as mod
from splitbrain.core.models import Claim, ClaimStatus, Decision
from splitbrain.core.packets import decode
from splitbrain.core.protocol import (
    ConsentRequestPacket,
    DecidedPacket,
    OriginRef,
)
from splitbrain.core.store import ClaimStore
from splitbrain.switch.events import MessageFrame, MessagePayload

OPS_ROOM = "r-ops"
SALES = "r-sales"
ENGINEERING = "r-engineering"
QUOTE = "We're pulling SSO out of Q4. The auth migration has to land first."


class FakeAgent:
    agent_id = "fake-agent"

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.targeted_calls: list[dict[str, Any]] = []
        self.ops: list[tuple[str, dict[str, Any]]] = []

    async def op(self, name: str, /, **args: Any) -> Any:
        self.ops.append((name, args))
        if name == "list_rooms":
            return [
                {"room_id": OPS_ROOM, "name": "splitbrain-ops"},
                {"room_id": SALES, "name": "sales"},
                {"room_id": ENGINEERING, "name": "engineering"},
            ]
        return {}

    @asynccontextmanager
    async def act_in(self, room_id: str):
        yield self

    async def post(self, room_id: str, body: str, thread_id: str | None = None) -> dict[str, str]:
        self.posts.append({"room_id": room_id, "body": body, "thread_id": thread_id})
        return {"event_id": "sw_fake"}

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


@dataclass
class Fixture:
    sentinel: mod.Sentinel
    agent: FakeAgent
    store: ClaimStore


def claim(*, claim_id: str, room: str, author: str, text: str, private: bool) -> Claim:
    return Claim(
        id=claim_id,
        room_id=room,
        room_name="engineering" if private else "sales",
        channel_type="channel_private" if private else "channel_public",
        message_id=f"sw_{claim_id}",
        author=author,
        text=text,
        ts=1793776781000,
        kind="commitment",
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        value="December 1",
        polarity="affirm",
        effective_date=None,
        confidence=0.95,
    )


async def make_fixture(tmp_path: Path, llm_factory: Any) -> Fixture:
    llm, _, _, _ = llm_factory([], mode="live")
    state = bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(
                room_id=room_id,
                channel_type="channel_private" if name == "engineering" else "channel_public",
            )
            for name, room_id in (
                ("sales", SALES),
                ("engineering", ENGINEERING),
                ("support", "r-support"),
                ("finance", "r-finance"),
                ("splitbrain-ops", OPS_ROOM),
            )
        }
    )
    agent = FakeAgent()
    store = ClaimStore(tmp_path / "sentinel.db")
    await store.add_claim(
        claim(claim_id="clm_tomas", room=ENGINEERING, author="tomas", text=QUOTE, private=True)
    )
    await store.add_claim(
        claim(
            claim_id="clm_maria",
            room=SALES,
            author="maria",
            text="Confirmed with Acme: SSO live on December 1.",
            private=False,
        )
    )
    sentinel = mod.Sentinel(
        agent=agent,  # type: ignore[arg-type]
        llm=llm,
        store=store,
        state=state,
        batch_window_s=0.0,
    )
    await sentinel.start()
    return Fixture(sentinel=sentinel, agent=agent, store=store)


def frame(
    room_id: str,
    author: str,
    body: str,
    *,
    message_id: str = "sw_reply",
    thread_id: str | None = None,
) -> MessageFrame:
    return MessageFrame(
        kind="message",
        sequence=1,
        room_id=room_id,
        payload=MessagePayload(
            message_id=message_id,
            sender_name=author,
            body=body,
            thread_id=thread_id,
        ),
    )


def consent_frame() -> MessageFrame:
    from splitbrain.core.packets import encode

    request = ConsentRequestPacket(
        candidate_id="sb-0001",
        claim_id="clm_tomas",
        author="tomas",
        other_author="maria",
        room_id=ENGINEERING,
        thread_id="sw_clm_tomas",
    )
    return frame(
        OPS_ROOM,
        "splitbrain-arbiter",
        "Consent needed.\n" + encode("consent_request", request),
        message_id="sw_consent_request",
        thread_id="sw_candidate",
    )


async def test_consent_question_is_asked_in_the_private_thread_without_the_quote(
    llm_factory: Any, tmp_path: Path
) -> None:
    fix = await make_fixture(tmp_path, llm_factory)
    try:
        await fix.sentinel.on_frame(consent_frame())
        assert fix.agent.posts == [
            {
                "room_id": ENGINEERING,
                "body": (
                    "@tomas Splitbrain found that this message conflicts with a statement "
                    "from another team. May I quote it in a private resolution room with "
                    '@maria? Reply "yes" or "no" here.'
                ),
                "thread_id": "sw_clm_tomas",
            }
        ]
        assert QUOTE not in fix.agent.posts[0]["body"]
        assert (ENGINEERING, "sw_clm_tomas") in fix.sentinel.consent_pending
    finally:
        await fix.sentinel.aclose()


@pytest.mark.parametrize(
    ("answer", "granted"),
    [("yes", True), ("sí", True), ("ok", True), ("no", False), ("maybe", False)],
)
async def test_only_the_next_reply_by_the_author_in_that_thread_decides(
    llm_factory: Any, tmp_path: Path, answer: str, granted: bool
) -> None:
    fix = await make_fixture(tmp_path, llm_factory)
    try:
        await fix.sentinel.on_frame(consent_frame())
        # A different author in the same thread must not decide anything.
        other = frame(
            ENGINEERING,
            "lucia",
            "yes",
            thread_id="sw_clm_tomas",
            message_id="sw_other",
        )
        assert await fix.sentinel._consent_reply(other) is False
        assert fix.agent.targeted_calls == []

        reply = frame(
            ENGINEERING,
            "tomas",
            answer,
            thread_id="sw_clm_tomas",
            message_id="sw_yes",
        )
        assert await fix.sentinel._consent_reply(reply) is True
        call = fix.agent.targeted_calls[-1]
        assert call["room_id"] == OPS_ROOM
        assert call["target_roles"] == ["arbiter"]
        assert call["thread_id"] == "sw_candidate"
        kind, data = decode(call["body"].splitlines()[-1])
        assert kind == "consent"
        assert data["granted"] is granted
        assert data["text"] == (QUOTE if granted else None)
        if granted:
            assert QUOTE not in call["body"].splitlines()[0]
        # The decision is consumed: no second packet.
        assert await fix.sentinel._consent_reply(reply) is False
        assert len(fix.agent.targeted_calls) == 1
    finally:
        await fix.sentinel.aclose()


def decided_frame() -> MessageFrame:
    from splitbrain.core.packets import encode

    packet = DecidedPacket(
        candidate_id="sb-0001",
        decision=Decision(
            candidate_id="sb-0001",
            room_id="r-conflict",
            text="SSO beta for Acme on December 15, GA in Q1.",
            proposed_by="maria",
            confirmed_by="tomas",
            decided_at="2026-11-04T10:00:00+00:00",
        ),
        conflict_room="r-conflict",
        conflict_room_name="conflict-sb-0001-sso",
        origins=[
            OriginRef(
                room_id=SALES,
                room_name="sales",
                thread_id="sw_clm_maria",
                message_id="sw_clm_maria",
                author="maria",
                claim_id="clm_maria",
            ),
            OriginRef(
                room_id=ENGINEERING,
                room_name="engineering",
                thread_id="sw_clm_tomas",
                message_id="sw_clm_tomas",
                author="tomas",
                claim_id="clm_tomas",
            ),
        ],
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        authors=["maria", "tomas"],
    )
    return frame(
        OPS_ROOM,
        "splitbrain-arbiter",
        "Decision recorded.\n" + encode("decided", packet),
        message_id="sw_decided",
        thread_id="sw_candidate",
    )


async def test_corrections_go_to_both_original_threads_and_close_the_loop(
    llm_factory: Any, tmp_path: Path
) -> None:
    fix = await make_fixture(tmp_path, llm_factory)
    try:
        await fix.sentinel.on_frame(decided_frame())
        assert [post["room_id"] for post in fix.agent.posts] == [SALES, ENGINEERING]
        assert [post["thread_id"] for post in fix.agent.posts] == [
            "sw_clm_maria",
            "sw_clm_tomas",
        ]
        body = fix.agent.posts[0]["body"]
        assert body.startswith("Update: @maria and @tomas resolved a conflict about SSO for Acme")
        assert "#conflict-sb-0001-sso" in body
        assert 'Decision: "SSO beta for Acme on December 15, GA in Q1."' in body
        assert '".' not in body and '"!' not in body and '"?' not in body
        assert await fix.store.claim_by_id("clm_maria") is not None
        assert (await fix.store.claim_by_id("clm_maria")).status == ClaimStatus.RESOLVED
        assert (await fix.store.claim_by_id("clm_tomas")).status == ClaimStatus.RESOLVED
        active = await fix.store.active_claims()
        assert any(item.text == "SSO beta for Acme on December 15, GA in Q1." for item in active)
        call = fix.agent.targeted_calls[-1]
        kind, data = decode(call["body"].splitlines()[-1])
        assert kind == "corrected"
        assert data["rooms"] == ["sales", "engineering"]
        assert call["target_roles"] == ["arbiter"]
        # Idempotency: a redelivered sb:decided does not post corrections twice.
        await fix.sentinel.on_frame(decided_frame())
        assert len(fix.agent.posts) == 2
    finally:
        await fix.sentinel.aclose()


async def test_correction_punctuation_when_decision_has_no_trailing_stop(
    llm_factory: Any, tmp_path: Path
) -> None:
    fix = await make_fixture(tmp_path, llm_factory)
    try:
        unpunctuated = decided_frame()
        unpunctuated.payload.body = unpunctuated.payload.body.replace(
            "SSO beta for Acme on December 15, GA in Q1.", "SSO in Q1"
        )
        await fix.sentinel.on_frame(unpunctuated)
        body = fix.agent.posts[0]["body"]
        assert 'Decision: "SSO in Q1". Please use this from now on.' in body
    finally:
        await fix.sentinel.aclose()

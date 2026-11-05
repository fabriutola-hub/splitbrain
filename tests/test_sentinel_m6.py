"""Sentinel: consent in the author's thread, corrections in the origin threads, reminders."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from splitbrain import bootstrap
from splitbrain.agents import sentinel as mod
from splitbrain.core.models import Claim, ClaimKind, ClaimStatus, Decision, Message
from splitbrain.core.packets import decode
from splitbrain.core.protocol import (
    ConsentRequestPacket,
    DecidedPacket,
    OriginRef,
)
from splitbrain.core.store import ClaimStore
from splitbrain.switch.events import MessageFrame, MessagePayload
from splitbrain.tui import SentinelTui

OPS_ROOM = "r-ops"
SALES = "r-sales"
ENGINEERING = "r-engineering"
SUPPORT = "r-support"
FINANCE = "r-finance"
QUOTE = "We're pulling SSO out of Q4. The auth migration has to land first."


class FakeAgent:
    agent_id = "fake-agent"

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.targeted_calls: list[dict[str, Any]] = []
        self.ops: list[tuple[str, dict[str, Any]]] = []
        self.decision_record: str | None = (
            "SB-0001 decision record\n\n"
            "Status: DECIDED\n"
            "Decision protocol: only @maria and @tomas can close this conflict."
        )
        self.fail_document_read = False

    async def op(self, name: str, /, **args: Any) -> Any:
        self.ops.append((name, args))
        if name == "list_rooms":
            return [
                {"room_id": OPS_ROOM, "name": "splitbrain-ops"},
                {"room_id": SALES, "name": "sales"},
                {"room_id": ENGINEERING, "name": "engineering"},
                {"room_id": SUPPORT, "name": "support"},
                {"room_id": FINANCE, "name": "finance"},
            ]
        if name == "connect_to_room":
            if self.fail_document_read:
                raise RuntimeError("Switch document service unavailable")
            if self.decision_record is None:
                return {"documents": []}
            return {"documents": [{"id": "doc-1", "name": "SB-0001 decision record"}]}
        if name == "load_internal_documents":
            if self.fail_document_read:
                raise RuntimeError("Switch document service unavailable")
            if self.decision_record is None:
                return []
            return [
                {
                    "id": "doc-1",
                    "name": "SB-0001 decision record",
                    "content": self.decision_record,
                }
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


async def make_fixture(
    tmp_path: Path,
    llm_factory: Any,
    responses: list[dict[str, Any]] | None = None,
    *,
    tui: SentinelTui | None = None,
) -> Fixture:
    llm, _, _, _ = llm_factory(list(responses or ()), mode="live")
    state = bootstrap.BootstrapState(
        rooms={
            name: bootstrap.RoomState(
                room_id=room_id,
                channel_type="channel_private" if name == "engineering" else "channel_public",
            )
            for name, room_id in (
                ("sales", SALES),
                ("engineering", ENGINEERING),
                ("support", SUPPORT),
                ("finance", FINANCE),
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
        tui=tui,
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
            text="SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today.",
            proposed_by="maria",
            confirmed_by="tomas",
            decided_at="2026-11-05T15:00:00+00:00",
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
        assert (
            'Decision: "SSO beta for Acme on December 15, GA in Q1. I\'ll tell Acme today."' in body
        )
        assert '".' not in body and '"!' not in body and '"?' not in body
        assert await fix.store.claim_by_id("clm_maria") is not None
        assert (await fix.store.claim_by_id("clm_maria")).status == ClaimStatus.RESOLVED
        assert (await fix.store.claim_by_id("clm_tomas")).status == ClaimStatus.RESOLVED
        active = await fix.store.active_claims()
        assert any(
            item.text == "SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today."
            and item.kind == ClaimKind.DECISION
            for item in active
        )
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
            "SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today.", "SSO in Q1"
        )
        await fix.sentinel.on_frame(unpunctuated)
        body = fix.agent.posts[0]["body"]
        assert 'Decision: "SSO in Q1". Please use this from now on.' in body
    finally:
        await fix.sentinel.aclose()


def _extract_response(message_id: str, value: str, date: str | None = "2026-12-01") -> dict:
    return {
        "results": [
            {
                "message_id": message_id,
                "claims": [
                    {
                        "kind": "commitment",
                        "subject": "SSO",
                        "subject_key": "sso",
                        "scope": "Acme",
                        "scope_key": "acme",
                        "value": value,
                        "polarity": "affirm",
                        "effective_date": date,
                        "confidence": 0.95,
                    }
                ],
            }
        ]
    }


async def test_contradicting_a_recorded_decision_posts_reminder_and_no_candidate(
    llm_factory: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_TZ", "America/Caracas")
    view = SentinelTui(
        SimpleNamespace(mode="replay", model="deepseek-ai/DeepSeek-V4.1-Flash-1017"),  # type: ignore[arg-type]
        width=120,
        height=32,
    )
    responses = [
        _extract_response("sw_lucia_1", "live on 2026-12-01"),
        {
            "relation": "contradiction",
            "confidence": 0.94,
            "reason": "December 1 contradicts the agreed December 15 beta and Q1 GA.",
        },
    ]
    fix = await make_fixture(tmp_path, llm_factory, responses, tui=view)
    caplog.set_level(logging.INFO)
    try:
        await fix.sentinel.on_frame(decided_frame())
        fix.agent.posts.clear()
        fix.agent.targeted_calls.clear()

        followup = Message(
            message_id="sw_lucia_1",
            room_id=SUPPORT,
            room_name="support",
            author="lucia",
            text=(
                "Quick one for the desk: Acme gets SSO on December 1, "
                "so you can confirm it if they ask."
            ),
        )
        await fix.sentinel.analyze_messages([followup])

        assert fix.sentinel.candidates_sent == 0
        assert len(fix.agent.posts) == 1
        post = fix.agent.posts[0]
        assert post == {
            "room_id": SUPPORT,
            "thread_id": "sw_lucia_1",
            "body": (
                "Heads-up: this was already decided. On Nov 5, María Gómez and Tomás Rivera "
                'agreed: "SSO beta for Acme on December 15, GA in Q1. I\'ll tell Acme today." '
                "(decision record in #conflict-sb-0001-sso). Please use that instead."
            ),
        }
        assert QUOTE not in post["body"]
        assert len(fix.agent.targeted_calls) == 1
        call = fix.agent.targeted_calls[0]
        assert call["room_id"] == OPS_ROOM
        assert call["target_roles"] == ["arbiter"]
        assert call["thread_id"] == "sw_candidate"
        kind, data = decode(call["body"].splitlines()[-1])
        assert kind == "reminded"
        assert data == {
            "candidate_id": "sb-0001",
            "conflict_room": "r-conflict",
            "conflict_room_name": "conflict-sb-0001-sso",
            "room_name": "support",
            "author": "lucia",
            "message_id": "sw_lucia_1",
        }
        # The contradicting claim is stored as SUPERSEDED so it never pairs later.
        active = await fix.store.active_claims()
        assert [c.kind for c in active] == [ClaimKind.DECISION]
        stored_followup = await fix.store.claim_by_id("clm_3319df9ca6")
        if stored_followup is not None:
            assert stored_followup.status == ClaimStatus.SUPERSEDED
        steps = [step.text for step in view.steps.get("sb-0001", [])]
        assert "reminder → #support Lucía Pérez" in steps
        assert "Reminder posted in #support for sb-0001" in caplog.text
    finally:
        await fix.sentinel.aclose()


async def test_compatible_with_a_recorded_decision_stays_silent(
    llm_factory: Any,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    responses = [
        _extract_response("sw_pablo_1", "beta on 2026-12-15 and GA in Q1", date="2026-12-15"),
        {
            "relation": "compatible",
            "confidence": 0.93,
            "reason": "Finance repeats the agreed December 15 beta and Q1 GA.",
        },
    ]
    fix = await make_fixture(tmp_path, llm_factory, responses)
    caplog.set_level(logging.INFO)
    try:
        await fix.sentinel.on_frame(decided_frame())
        fix.agent.posts.clear()
        fix.agent.targeted_calls.clear()

        compatible = Message(
            message_id="sw_pablo_1",
            room_id=FINANCE,
            room_name="finance",
            author="pablo",
            text="Noted for billing: Acme's SSO beta starts December 15 and GA is in Q1.",
        )
        await fix.sentinel.analyze_messages([compatible])

        assert fix.sentinel.candidates_sent == 0
        assert fix.agent.posts == []
        assert fix.agent.targeted_calls == []
        assert "No alert: compatible" in caplog.text
    finally:
        await fix.sentinel.aclose()


async def test_same_author_of_the_decision_also_receives_a_reminder(
    llm_factory: Any,
    tmp_path: Path,
) -> None:
    responses = [
        _extract_response("sw_maria_again", "live on 2026-12-01"),
        {
            "relation": "contradiction",
            "confidence": 0.95,
            "reason": "María repeated the earlier December 1 date.",
        },
    ]
    fix = await make_fixture(tmp_path, llm_factory, responses)
    try:
        await fix.sentinel.on_frame(decided_frame())
        fix.agent.posts.clear()
        fix.agent.targeted_calls.clear()

        msg = Message(
            message_id="sw_maria_again",
            room_id=SALES,
            room_name="sales",
            author="maria",
            text="Quick reminder: Acme SSO goes live on December 1.",
        )
        await fix.sentinel.analyze_messages([msg])

        assert fix.sentinel.candidates_sent == 0
        assert len(fix.agent.posts) == 1
        assert fix.agent.posts[0]["room_id"] == SALES
        assert fix.agent.posts[0]["thread_id"] == "sw_maria_again"
        assert "Heads-up: this was already decided." in fix.agent.posts[0]["body"]
    finally:
        await fix.sentinel.aclose()


async def test_reminder_idempotency_at_most_one_per_message_and_one_per_thread(
    llm_factory: Any,
    tmp_path: Path,
) -> None:
    responses = [
        {
            "results": [
                {
                    "message_id": "sw_msg_1",
                    "claims": [
                        {
                            "kind": "commitment",
                            "subject": "SSO",
                            "subject_key": "sso",
                            "scope": "Acme",
                            "scope_key": "acme",
                            "value": "December 1",
                            "polarity": "affirm",
                            "effective_date": "2026-12-01",
                            "confidence": 0.95,
                        },
                        {
                            "kind": "status",
                            "subject": "SSO",
                            "subject_key": "sso",
                            "scope": "Acme",
                            "scope_key": "acme",
                            "value": "shipping Dec 1",
                            "polarity": "affirm",
                            "effective_date": "2026-12-01",
                            "confidence": 0.92,
                        },
                    ],
                }
            ]
        },
        {
            "relation": "contradiction",
            "confidence": 0.94,
            "reason": "Contradicts the decision.",
        },
        {
            "relation": "contradiction",
            "confidence": 0.94,
            "reason": "Also contradicts the decision.",
        },
        _extract_response("sw_msg_2", "still December 1"),
        {
            "relation": "contradiction",
            "confidence": 0.94,
            "reason": "Same thread repeats December 1 again.",
        },
    ]
    fix = await make_fixture(tmp_path, llm_factory, responses)
    try:
        await fix.sentinel.on_frame(decided_frame())
        fix.agent.posts.clear()
        fix.agent.targeted_calls.clear()

        first = Message(
            message_id="sw_msg_1",
            room_id=SUPPORT,
            room_name="support",
            thread_id="sw_thread_root",
            author="lucia",
            text="Acme gets SSO on December 1; shipping Dec 1.",
        )
        second_in_same_thread = Message(
            message_id="sw_msg_2",
            room_id=SUPPORT,
            room_name="support",
            thread_id="sw_thread_root",
            author="pablo",
            text="Confirming in this thread: Acme SSO is still December 1.",
        )
        await fix.sentinel.analyze_messages([first])
        await fix.sentinel.analyze_messages([second_in_same_thread])

        # Two claims in one message + a second message in the same thread -> 1 reminder total.
        assert len(fix.agent.posts) == 1
        assert fix.agent.posts[0]["thread_id"] == "sw_thread_root"
        assert len(fix.agent.targeted_calls) == 1
    finally:
        await fix.sentinel.aclose()


async def test_unreadable_or_undecided_document_logs_loudly_and_posts_nothing(
    llm_factory: Any,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    responses = [
        _extract_response("sw_fail_1", "live on 2026-12-01"),
        {
            "relation": "contradiction",
            "confidence": 0.94,
            "reason": "December 1 contradicts the decision.",
        },
        _extract_response("sw_fail_2", "live on 2026-12-02", date="2026-12-02"),
        {
            "relation": "contradiction",
            "confidence": 0.94,
            "reason": "December 2 contradicts the decision.",
        },
    ]
    fix = await make_fixture(tmp_path, llm_factory, responses)
    caplog.set_level(logging.ERROR)
    try:
        await fix.sentinel.on_frame(decided_frame())
        fix.agent.posts.clear()
        fix.agent.targeted_calls.clear()

        # Case 1: load_internal_documents fails with an exception.
        fix.agent.fail_document_read = True
        msg1 = Message(
            message_id="sw_fail_1",
            room_id=SUPPORT,
            room_name="support",
            author="lucia",
            text="Acme gets SSO on December 1.",
        )
        await fix.sentinel.analyze_messages([msg1])
        assert fix.agent.posts == []
        assert fix.agent.targeted_calls == []
        assert "Failed to read decision record" in caplog.text

        # Case 2: document exists but does not say Status: DECIDED.
        fix.agent.fail_document_read = False
        fix.agent.decision_record = "SB-0001 decision record\n\nStatus: OPEN"
        msg2 = Message(
            message_id="sw_fail_2",
            room_id=FINANCE,
            room_name="finance",
            author="pablo",
            text="Acme gets SSO on December 2.",
        )
        await fix.sentinel.analyze_messages([msg2])
        assert fix.agent.posts == []
        assert fix.agent.targeted_calls == []
        assert "does not have 'Status: DECIDED'" in caplog.text
    finally:
        await fix.sentinel.aclose()

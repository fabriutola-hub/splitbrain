"""Arbiter: verdict rule, consent-aware quotes, brief and decision record."""

from __future__ import annotations

import pytest

from splitbrain import bootstrap
from splitbrain.agents import arbiter as mod
from splitbrain.core.models import Evidence
from splitbrain.core.protocol import CandidatePacket, ConsentPacket, PacketClaim


def packet_claim(*, private: bool, author: str, room: str) -> PacketClaim:
    return PacketClaim(
        id=f"clm_{author}",
        room_id=f"r-{room}",
        room_name=room,
        channel_type="channel_private" if private else "channel_public",
        message_id=f"sw_{author}",
        author=author,
        ts=1793776781000,
        text=None if private else "Confirmed with Acme: SSO live on December 1.",
        text_withheld=private,
        subject="SSO",
        subject_key="sso",
        scope="Acme",
        scope_key="acme",
        value="December 1" if not private else "removed from Q4 delivery",
    )


def verification(*, granted: bool | None = None) -> mod.Verification:
    candidate = CandidatePacket(
        id="sb-0001",
        claim_a=packet_claim(private=False, author="maria", room="sales"),
        claim_b=packet_claim(private=True, author="tomas", room="engineering"),
        confidence=0.93,
        reason="Two dates.",
    )
    item = mod.Verification(candidate=candidate, thread_id="sw-root", requested_at=0.0)
    item.evidence = Evidence(
        candidate_id="sb-0001",
        source="github",
        status="supports_b",
        summary="issue #2 moved from Q4 2026 to Q1 2027 on Nov 4",
        items=[],
    )
    item.link_labels = ["origin: #sales (maria)", "origin: #engineering (tomas)"]
    if granted is not None:
        item.consents["clm_tomas"] = ConsentPacket(
            candidate_id="sb-0001",
            claim_id="clm_tomas",
            author="tomas",
            granted=granted,
            text="We're pulling SSO out of Q4. The auth migration has to land first."
            if granted
            else None,
        )
    return item


def make_arbiter() -> mod.Arbiter:
    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    return mod.Arbiter(
        agent=object(),  # type: ignore[arg-type]
        state=state,
        name=mod.AGENT_NAME,
        consent_timeout_s=600.0,
        evidence_timeout_s=60.0,
    )


@pytest.mark.parametrize(
    ("confidence", "status", "expected"),
    [
        (0.93, "supports_b", "confirmed"),
        (0.70, "conflicting", "confirmed"),
        (0.69, "supports_b", "discarded"),
        (0.95, "inconclusive", "discarded"),
        (0.99, "none", "discarded"),
    ],
)
def test_verdict_rule(confidence: float, status: str, expected: str) -> None:
    assert mod.verdict_for(confidence, status) == expected


def test_slug() -> None:
    assert mod._slug("SSO!") == "sso"
    assert mod._slug("") == "subject"
    long = mod._slug("hackathon-prize-best-core-contribution")
    assert len(long) <= mod.SLUG_LIMIT
    assert long == "hackathon-prize-best-core"[: mod.SLUG_LIMIT].rsplit("-", 1)[0]
    assert not long.endswith("-")
    assert mod._slug("sso") == "sso"


def test_quotes_are_withheld_until_the_author_consents() -> None:
    denied = verification(granted=False)
    assert "(quote withheld at the author's request)" in mod._quote(
        denied.candidate.claim_b, denied.consents
    )
    assert "Subject: SSO" in mod._quote(denied.candidate.claim_b, denied.consents)
    granted = verification(granted=True)
    quote = mod._quote(granted.candidate.claim_b, granted.consents)
    assert "We're pulling SSO out of Q4" in quote
    assert "withheld" not in quote


def test_brief_cites_both_quotes_only_after_consent() -> None:
    arbiter = make_arbiter()
    denied = verification(granted=False)
    brief = arbiter._brief(denied)
    assert "@maria @tomas" in brief
    assert "Confirmed with Acme" in brief
    assert "sales, María Gómez, Nov" in brief
    assert "engineering (private), Tomás Rivera, Nov" in brief
    assert "(@maria)" not in brief and "(@tomas)" not in brief
    assert '".' not in brief and '"!' not in brief and '"?' not in brief
    assert "UTC" in brief
    assert "We're pulling SSO out of Q4" not in brief
    assert "(quote withheld at the author's request)" in brief
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in brief
    assert "decision:" in brief and "confirm" in brief
    granted = verification(granted=True)
    assert "We're pulling SSO out of Q4" in arbiter._brief(granted)


def test_decision_record_is_open_and_contains_evidence_and_origins() -> None:
    arbiter = make_arbiter()
    record = arbiter._open_record(verification(granted=False))
    assert "Status: OPEN" in record
    assert "SB-0001 decision record" in record
    assert "Claim A - #sales, María Gómez," in record
    assert "Tomás Rivera," in record
    assert "(@maria)" not in record
    assert "moved from Q4 2026 to Q1 2027 on Nov 4" in record
    assert "origin: #sales (maria)" in record
    assert "origin: #engineering (tomas)" in record
    assert "only @maria and @tomas" in record


def test_consent_timeout_fills_missing_answers_as_denied() -> None:
    item = verification()
    item.withheld_ids = {"clm_tomas"}
    mod.Arbiter._fill_missing_consents(item)
    assert item.consents["clm_tomas"].granted is False
    assert item.consents["clm_tomas"].text is None


async def test_corrected_appends_the_final_line_and_confirms_in_the_room() -> None:
    from contextlib import asynccontextmanager

    from splitbrain.core.protocol import CorrectedPacket

    class FakeAgent:
        def __init__(self) -> None:
            self.updates: list[dict] = []
            self.posts: list[tuple[str, str]] = []

        @asynccontextmanager
        async def act_in(self, room_id: str):
            yield self

        async def op(self, name: str, /, **args) -> dict:
            self.updates.append({"name": name, **args})
            return {}

        async def post(self, room_id: str, body: str, **kwargs) -> dict:
            self.posts.append((room_id, body))
            return {}

    arbiter = make_arbiter()
    item = verification(granted=True)
    item.room_id = "r-conflict"
    item.room_name = "conflict-sb-0001-sso"
    item.document_id = "doc-1"
    item.record = "Status: DECIDED\nDecision: SSO in Q1"
    item.decided = True
    arbiter.verifications[item.candidate.id] = item
    fake = FakeAgent()
    arbiter.agent = fake  # type: ignore[assignment]

    packet = CorrectedPacket(
        candidate_id="sb-0001",
        conflict_room="r-conflict",
        conflict_room_name="conflict-sb-0001-sso",
        rooms=["sales", "engineering"],
    )
    await arbiter._on_corrected(packet)
    assert item.corrected is True
    assert "Corrections posted in #sales, #engineering" in item.record
    assert fake.updates[-1]["name"] == "update_room_document"
    assert "Corrections posted in #sales, #engineering" in fake.updates[-1]["content"]
    assert fake.posts[-1] == (
        "r-conflict",
        'Corrections posted in #sales, #engineering; "Customer commitments" '
        "updated for Acme in #splitbrain-ops (no follow-up task).",
    )
    # A duplicate packet must not append the line twice.
    await arbiter._on_corrected(packet)
    assert item.record.count("Corrections posted") == 1


async def test_conflict_room_is_private_and_invites_the_standby_arbiter() -> None:
    from contextlib import asynccontextmanager

    class FakeAgent:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []
            self.posts: list[tuple[str, str]] = []

        @asynccontextmanager
        async def act_in(self, room_id: str):
            yield self

        async def op(self, name: str, /, **args) -> dict:
            self.calls.append((name, args))
            if name == "list_all_rooms":
                return {"rooms": []}
            if name == "create_room":
                return {"id": "r-new"}
            if name == "connect_to_room":
                return {"linked_rooms": []}
            if name == "create_room_document":
                return {"document_id": "doc-1"}
            return {}

        async def post(self, room_id: str, body: str, **kwargs) -> dict:
            self.posts.append((room_id, body))
            return {}

    arbiter = make_arbiter()
    item = verification(granted=True)
    item.evidence.status = "supports_b"
    fake = FakeAgent()
    arbiter.agent = fake  # type: ignore[assignment]
    arbiter.is_holder = True
    await arbiter._open_conflict(item)

    create = next(args for name, args in fake.calls if name == "create_room")
    assert create["channel_type"] == "channel_private"
    assert create["agent_names"] == [
        "splitbrain-arbiter",
        "splitbrain-arbiter-b",
        "splitbrain-sentinel",
    ]
    assert set(create["user_names"]) == {"maria", "tomas"}
    assert "Private" in create["instructions"] or "private" in create["instructions"]
    assert any(name == "link_rooms" for name, _ in fake.calls)
    assert any("Splitbrain found two statements" in body for _, body in fake.posts)


async def test_decision_message_shows_the_record_people_can_read() -> None:
    from contextlib import asynccontextmanager

    from splitbrain.core.decision import DecisionMachine, DecisionOutcome, DecisionState

    class FakeAgent:
        def __init__(self) -> None:
            self.posts: list[tuple[str, str]] = []

        @asynccontextmanager
        async def act_in(self, room_id: str):
            yield self

        async def op(self, name: str, /, **args) -> dict:
            return {}

        async def post(self, room_id: str, body: str, **kwargs) -> dict:
            self.posts.append((room_id, body))
            return {}

        async def targeted(self, room_id: str, body: str, **kwargs) -> dict:
            return {}

    arbiter = make_arbiter()
    item = verification(granted=True)
    item.room_id = "r-conflict"
    item.room_name = "conflict-sb-0001-sso"
    item.document_id = "doc-1"
    item.record = "Status: OPEN"
    item.machine = DecisionMachine("maria", "tomas")
    fake = FakeAgent()
    arbiter.agent = fake  # type: ignore[assignment]
    outcome = DecisionOutcome(
        state=DecisionState.DECIDED,
        reply=None,
        decision="SSO beta for Acme on December 15, GA in Q1.",
        proposed_by="tomas",
        confirmed_by="maria",
        decided_at="2026-11-05T03:18:00+00:00",
    )
    await arbiter._on_decided(item, outcome)

    message = fake.posts[-1][1]
    assert 'Decision recorded: "SSO beta for Acme on December 15, GA in Q1."' in message
    assert "(proposed by @tomas, confirmed by @maria," in message
    assert "UTC" in message
    assert message.endswith("Correcting the original threads now.")
    assert '".' not in message and '"!' not in message and '"?' not in message
    assert "Decided at:" in item.record and "UTC" in item.record


async def test_reminded_updates_the_decision_record_and_posts_in_the_conflict_room() -> None:
    from contextlib import asynccontextmanager

    from splitbrain.core.packets import encode
    from splitbrain.core.protocol import RemindedPacket
    from splitbrain.switch.events import MessageFrame, MessagePayload

    class FakeAgent:
        def __init__(self) -> None:
            self.updates: list[dict] = []
            self.posts: list[tuple[str, str]] = []

        @asynccontextmanager
        async def act_in(self, room_id: str):
            yield self

        async def op(self, name: str, /, **args) -> dict:
            self.updates.append({"name": name, **args})
            return {}

        async def post(self, room_id: str, body: str, **kwargs) -> dict:
            self.posts.append((room_id, body))
            return {}

    arbiter = make_arbiter()
    arbiter.is_holder = True
    arbiter.coverage.rooms["r-ops"] = "splitbrain-ops"
    item = verification(granted=True)
    item.room_id = "r-conflict"
    item.room_name = "conflict-sb-0001-sso"
    item.document_id = "doc-1"
    item.record = (
        "Status: DECIDED\nDecision: SSO in Q1\n\nCorrections posted in #sales, #engineering"
    )
    item.decided = True
    arbiter.verifications[item.candidate.id] = item
    fake = FakeAgent()
    arbiter.agent = fake  # type: ignore[assignment]

    packet = RemindedPacket(
        candidate_id="sb-0001",
        conflict_room="r-conflict",
        conflict_room_name="conflict-sb-0001-sso",
        room_name="support",
        author="lucia",
        message_id="sw_followup_1",
    )
    frame = MessageFrame(
        kind="message",
        sequence=1,
        room_id="r-ops",
        payload=MessagePayload(
            message_id="sw_reminded",
            sender_name="splitbrain-sentinel",
            body="Reminder posted.\n" + encode("reminded", packet),
            timestamp=1793974320000,
        ),
    )
    await arbiter.on_frame(frame)
    assert "Reminder: Lucía Pérez repeated the earlier information in #support on " in item.record
    assert " and was pointed to this decision." in item.record
    assert fake.updates[-1]["name"] == "update_room_document"
    assert (
        "Reminder: Lucía Pérez repeated the earlier information in #support"
        in (fake.updates[-1]["content"])
    )
    assert fake.posts[-1] == (
        "r-conflict",
        "Heads-up: Lucía Pérez repeated the earlier information in #support; "
        "I pointed Lucía Pérez to this decision.",
    )
    # Idempotency: redelivering the same sb:reminded does not duplicate the line.
    await arbiter.on_frame(frame)
    assert len(fake.posts) == 1
    assert item.record.count("Reminder: Lucía Pérez") == 1


async def test_inconclusive_evidence_discards_candidate_and_contacts_nobody() -> None:
    from splitbrain.core.packets import decode, encode
    from splitbrain.switch.events import MessageFrame, MessagePayload

    class FakeAgent:
        def __init__(self) -> None:
            self.posts: list[tuple[str, str, str | None]] = []
            self.targeted_calls: list[dict] = []

        async def post(self, room_id: str, body: str, *, thread_id: str | None = None) -> dict:
            self.posts.append((room_id, body, thread_id))
            return {}

        async def targeted(self, room_id: str, body: str, **kwargs) -> dict:
            self.targeted_calls.append({"room_id": room_id, "body": body, **kwargs})
            return {}

    arbiter = make_arbiter()
    arbiter.is_holder = True
    arbiter.coverage.rooms["r-ops"] = "splitbrain-ops"
    item = verification()
    item.evidence = None
    arbiter.verifications[item.candidate.id] = item
    fake = FakeAgent()
    arbiter.agent = fake  # type: ignore[assignment]

    inconclusive = Evidence(
        candidate_id="sb-0001",
        source="github",
        status="inconclusive",
        summary='2 open issue(s) mention "SSO", but none mentions $250, $500, Q4 or December 1.',
        items=[],
    )
    frame = MessageFrame(
        kind="message",
        sequence=1,
        room_id="r-ops",
        payload=MessagePayload(
            message_id="sw_ev",
            sender_name="splitbrain-verifier",
            body="Evidence.\n" + encode("evidence", inconclusive),
            thread_id="sw-root",
        ),
    )
    await arbiter.on_frame(frame)
    assert item.verdict == "discarded"
    assert item.finished is True
    assert item.room_id is None
    assert fake.targeted_calls == []
    assert len(fake.posts) == 1
    room_id, body, thread_id = fake.posts[0]
    assert room_id == "r-ops"
    assert thread_id == "sw-root"
    assert (
        "Verdict for SB-0001: DISCARDED. Evidence was inconclusive: "
        '2 open issue(s) mention "SSO", but none mentions $250, $500, Q4 or December 1. '
        "Nobody is contacted."
    ) in body
    kind, payload = decode(body.splitlines()[-1])
    assert kind == "verdict"
    assert payload["verdict"] == "discarded"
    assert payload["evidence_status"] == "inconclusive"

"""Business follow-up outcomes and cross-room publication policy tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from decision_fakes import FakeSwitch

from splitbrain import bootstrap
from splitbrain.agents import arbiter as arbiter_mod
from splitbrain.agents.sentinel import Sentinel
from splitbrain.core.decision import DecisionMachine
from splitbrain.core.decision_record import (
    CorrectionJournal,
    latest_record,
    load_decision_records,
    pending_corrections,
)
from splitbrain.core.followup import (
    CUSTOMER_COMMITMENTS_DOC,
    customer_for_claims,
    extract_followup_task,
)
from splitbrain.core.models import Claim, Decision, Evidence
from splitbrain.core.packets import encode
from splitbrain.core.protocol import (
    CandidatePacket,
    ConsentPacket,
    CorrectedPacket,
    DecidedPacket,
    OriginRef,
    PacketClaim,
)
from splitbrain.core.publication import (
    PUBLICATION_NOTICE,
    PublicationPolicyError,
    assert_can_publish,
    public_topic_fields,
)
from splitbrain.core.store import ClaimStore
from splitbrain.switch.events import MessageFrame, MessagePayload

PRIVATE_QUOTE = "Heads up: we're pulling SSO out of Q4. The auth migration has to land first."
PUBLIC_QUOTE = "Morning! Big one: confirmed with Acme that SSO will be live for them on December 1."


def _claim(
    *,
    author: str,
    room: str,
    private: bool,
    subject: str = "SSO",
    subject_key: str = "sso",
    scope: str = "Acme",
    scope_key: str = "acme",
    value: str = "live on 2026-12-01",
    text: str | None = PUBLIC_QUOTE,
) -> PacketClaim:
    return PacketClaim(
        id=f"clm_{author}",
        room_id=f"r-{room}",
        room_name=room,
        channel_type="channel_private" if private else "channel_public",
        message_id=f"sw_{author}",
        author=author,
        ts=1793776781000,
        text=None if private else text,
        text_withheld=private,
        subject=subject,
        subject_key=subject_key,
        scope=scope,
        scope_key=scope_key,
        value=value,
    )


def _make_arbiter(fake_agent: Any, *, name: str = arbiter_mod.AGENT_NAME) -> arbiter_mod.Arbiter:
    state = bootstrap.BootstrapState(
        rooms={
            "splitbrain-ops": bootstrap.RoomState(room_id="r-ops", channel_type="channel_private")
        }
    )
    arb = arbiter_mod.Arbiter(
        agent=fake_agent,
        state=state,
        name=name,
        consent_timeout_s=600.0,
        evidence_timeout_s=60.0,
    )
    arb.is_holder = True
    return arb


class FakeSwitchAgent:
    def __init__(self) -> None:
        self.room_ops: list[tuple[str, str, dict[str, Any]]] = []
        self.posts: list[tuple[str, str]] = []
        self.targeted_calls: list[dict[str, Any]] = []
        self._active_room = ""
        self.ops_documents: list[dict[str, str]] = []
        self.conflict_documents: dict[str, dict[str, str]] = {}

    @asynccontextmanager
    async def act_in(self, room_id: str):
        prev = self._active_room
        self._active_room = room_id
        try:
            yield self
        finally:
            self._active_room = prev

    async def op(self, name: str, /, **args: Any) -> Any:
        self.room_ops.append((self._active_room, name, args))
        if name == "connect_to_room":
            room_id = args.get("room_id") or self._active_room
            if room_id == "r-ops":
                return {"documents": list(self.ops_documents)}
            return {
                "documents": [
                    {"id": doc["id"], "name": doc["name"]}
                    for doc in self.conflict_documents.values()
                ]
            }
        if name == "load_internal_documents":
            ids = set(args.get("ids") or [])
            found = [doc for doc in self.ops_documents if doc["id"] in ids]
            found.extend(doc for doc_id, doc in self.conflict_documents.items() if doc_id in ids)
            return found
        if name == "create_room_document":
            if self._active_room == "r-ops":
                doc_id = f"doc-{len(self.ops_documents) + 1}"
                self.ops_documents.append(
                    {
                        "id": doc_id,
                        "name": str(args.get("name", "")),
                        "content": str(args.get("content", "")),
                    }
                )
                return {"document_id": doc_id}
            doc_id = f"doc-conflict-{len(self.conflict_documents) + 1}"
            self.conflict_documents[doc_id] = {
                "id": doc_id,
                "name": str(args.get("name", "")),
                "content": str(args.get("content", "")),
            }
            return {"document_id": doc_id}
        if name == "update_room_document":
            doc_id = str(args.get("document_id", ""))
            for doc in self.ops_documents:
                if doc["id"] == doc_id:
                    doc["content"] = str(args.get("content", ""))
            if doc_id in self.conflict_documents:
                self.conflict_documents[doc_id]["content"] = str(args.get("content", ""))
            return {"document_id": doc_id, "status": "ok"}
        return {}

    async def post(self, room_id: str, body: str, **kwargs: Any) -> dict[str, Any]:
        self.posts.append((room_id, body))
        return {}

    async def targeted(self, room_id: str, body: str, **kwargs: Any) -> dict[str, Any]:
        self.targeted_calls.append({"room_id": room_id, "body": body, **kwargs})
        return {}


def _sso_verification() -> arbiter_mod.Verification:
    candidate = CandidatePacket(
        id="sb-0001",
        claim_a=_claim(
            author="maria",
            room="sales",
            private=False,
            subject="SSO",
            scope="Acme",
            value="live on December 1",
            text=PUBLIC_QUOTE,
        ),
        claim_b=_claim(
            author="tomas",
            room="engineering",
            private=True,
            subject="single sign-on",
            scope="*",
            scope_key="*",
            value="removed from Q4 delivery",
        ),
        confidence=0.94,
        reason="Sales promised December 1 while engineering removed it from Q4.",
    )
    ver = arbiter_mod.Verification(candidate=candidate, thread_id="sw-ops-1", requested_at=0.0)
    ver.room_id = "r-conflict-sso"
    ver.room_name = "conflict-sb-0001-sso"
    ver.document_id = "doc-record-1"
    ver.record = "SB-0001 decision record\n\nStatus: OPEN"
    ver.machine = DecisionMachine("maria", "tomas", conflict_id=candidate.id)
    ver.origins = [
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
    ver.evidence = Evidence(
        candidate_id="sb-0001",
        source="github",
        status="supports_b",
        summary="issue #2 moved from Q4 2026 to Q1 2027 on Nov 4",
    )
    ver.consents["clm_tomas"] = ConsentPacket(
        candidate_id="sb-0001",
        claim_id="clm_tomas",
        author="tomas",
        granted=True,
        text=PRIVATE_QUOTE,
    )
    return ver


def test_brief_contains_the_publication_policy_notice() -> None:
    fake = FakeSwitchAgent()
    arbiter = _make_arbiter(fake)
    ver = _sso_verification()
    brief = arbiter._brief(ver)
    assert PUBLICATION_NOTICE in brief
    assert brief.index(PUBLICATION_NOTICE) > brief.index("decision: <what you agreed>")


async def test_demo_decision_logs_customer_commitment_and_posts_maria_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_TZ", "America/Caracas")
    fake = FakeSwitchAgent()
    arbiter = _make_arbiter(fake)
    ver = _sso_verification()
    arbiter.verifications[ver.candidate.id] = ver

    assert ver.machine is not None
    ver.machine.handle(
        "maria",
        "decision: SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today.",
    )
    outcome = ver.machine.handle("tomas", "confirm")
    ver.machine.decided_at = "2026-11-06T14:30:00+00:00"
    ver.machine.confirmations[-1].confirmed_at = "2026-11-06T14:30:00+00:00"
    outcome = ver.machine._outcome()
    await arbiter._on_decided(ver, outcome)

    assert len(fake.ops_documents) == 1
    doc = fake.ops_documents[0]
    assert doc["name"] == CUSTOMER_COMMITMENTS_DOC
    content = doc["content"]
    assert "Customer: Acme" in content
    assert "Topic: SSO" in content
    assert (
        'Decision: "SSO beta for Acme on December 15, GA in Q1. I\'ll tell Acme today."' in content
    )
    assert "Proposed by: @maria (María Gómez)" in content
    assert "Confirmed by: @tomas (Tomás Rivera)" in content
    assert "Nov 6 10:30 UTC-04:00" in content
    assert "Conflict room: #conflict-sb-0001-sso" in content
    assert "#sales (subject: SSO)" in content
    assert "#engineering (private, subject: single sign-on)" in content
    assert PRIVATE_QUOTE not in content
    assert "removed from Q4 delivery" not in content

    conflict_posts = [body for room_id, body in fake.posts if room_id == "r-conflict-sso"]
    assert len(conflict_posts) == 2
    assert conflict_posts[0].startswith("Decision recorded:")
    assert conflict_posts[1] == (
        'Follow-up for @María Gómez: tell Acme (due Nov 6). Logged in "Customer commitments".'
    )

    journal = CorrectionJournal(
        decided=arbiter._decision_packet(ver),
        threads=pending_corrections(ver.origins),
    )
    for idx, progress in enumerate(journal.threads):
        progress.status = "posted"
        progress.message_id = f"sw_corr_{idx}"
    fake.conflict_documents["doc-journal"] = {
        "id": "doc-journal",
        "name": "SB-0001 correction progress",
        "content": journal.render(),
    }

    await arbiter._on_corrected(
        CorrectedPacket(
            candidate_id="sb-0001",
            conflict_room="r-conflict-sso",
            conflict_room_name="conflict-sb-0001-sso",
            rooms=["sales", "engineering"],
        )
    )
    assert fake.posts[-1] == (
        "r-conflict-sso",
        'Corrections posted in #sales, #engineering; "Customer commitments" '
        "updated for Acme in #splitbrain-ops; "
        "follow-up assigned to @María Gómez: tell Acme (due Nov 6).",
    )


async def test_decision_without_commitment_creates_no_followup_task_and_updates_existing_doc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_TZ", "America/Caracas")
    fake = FakeSwitchAgent()
    fake.ops_documents.append(
        {
            "id": "doc-existing",
            "name": CUSTOMER_COMMITMENTS_DOC,
            "content": f"{CUSTOMER_COMMITMENTS_DOC}\n\n[SB-0000] Prior entry",
        }
    )
    arbiter = _make_arbiter(fake)
    candidate = CandidatePacket(
        id="sb-0002",
        claim_a=_claim(
            author="lucia",
            room="support",
            private=False,
            subject="refund approval threshold",
            subject_key="refunds",
            scope="*",
            scope_key="*",
            value="refunds above $500 need no manager sign-off",
            text="Customer refunds above $500 are fine to approve ourselves.",
        ),
        claim_b=_claim(
            author="pablo",
            room="finance",
            private=False,
            subject="refund approval threshold",
            subject_key="refunds",
            scope="*",
            scope_key="*",
            value="threshold is $250",
            text="The manager-approval threshold is $250.",
        ),
        confidence=0.92,
    )
    ver = arbiter_mod.Verification(candidate=candidate, thread_id="sw-ops-2", requested_at=0.0)
    ver.room_id = "r-conflict-refunds"
    ver.room_name = "conflict-sb-0002-refunds"
    ver.document_id = "doc-record-2"
    ver.record = "SB-0002 decision record\n\nStatus: OPEN"
    ver.machine = DecisionMachine("lucia", "pablo", conflict_id=candidate.id)
    arbiter.verifications[candidate.id] = ver

    ver.machine.handle("lucia", "decision: Refunds above $250 require manager approval.")
    outcome = ver.machine.handle("pablo", "confirm")
    await arbiter._on_decided(ver, outcome)

    ops_update_calls = [
        (name, args)
        for room_id, name, args in fake.room_ops
        if room_id == "r-ops" and name in ("create_room_document", "update_room_document")
    ]
    assert len(ops_update_calls) == 1
    assert ops_update_calls[0][0] == "update_room_document"
    assert ops_update_calls[0][1]["document_id"] == "doc-existing"
    updated_doc = fake.ops_documents[0]["content"]
    assert "[SB-0000] Prior entry" in updated_doc
    assert "[SB-0002] Customer: all customers | Topic: refund approval threshold" in updated_doc

    conflict_posts = [body for room_id, body in fake.posts if room_id == "r-conflict-refunds"]
    assert len(conflict_posts) == 1
    assert conflict_posts[0].startswith("Decision recorded:")
    assert not any("Follow-up for" in body for _, body in fake.posts)


@pytest.mark.parametrize(
    ("text", "author", "expected_owner", "expected_action"),
    [
        (
            "SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today.",
            "maria",
            "María Gómez",
            "tell Acme",
        ),
        (
            "Refunds above $250 need manager approval; I'll retire the macro today.",
            "lucia",
            "Lucía Pérez",
            "retire the macro",
        ),
        (
            "Refunds above $250 need manager approval; I'll retire the $500 macro today.",
            "lucia",
            "Lucía Pérez",
            "retire the $500 macro",
        ),
        (
            "Agreed on the new threshold. I'll email them.",
            "pablo",
            "Pablo Ruiz",
            "email them",
        ),
    ],
)
def test_followup_task_extraction_variants(
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    author: str,
    expected_owner: str,
    expected_action: str,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_TZ", "America/Caracas")
    decision = Decision(
        candidate_id="sb-0001",
        room_id="r-conflict",
        text=text,
        proposed_by=author,
        confirmed_by="tomas",
        decided_at="2026-11-06T14:30:00+00:00",
    )
    task = extract_followup_task(decision)
    assert task is not None
    assert task.owner_display == expected_owner
    assert task.action == expected_action
    assert task.due == "Nov 6"
    assert task.format_message() == (
        f"Follow-up for @{expected_owner}: {expected_action} (due Nov 6). "
        f'Logged in "{CUSTOMER_COMMITMENTS_DOC}".'
    )


def test_customer_for_claims_uses_scope_or_subject_or_all_customers() -> None:
    pub = _claim(author="maria", room="sales", private=False, subject="SSO", scope="Acme")
    priv = _claim(author="tomas", room="engineering", private=True, subject="SSO", scope="*")
    assert customer_for_claims(pub, priv) == "Acme"

    in_subject = _claim(
        author="maria",
        room="sales",
        private=False,
        subject="SSO rollout for Globex",
        scope="*",
    )
    assert customer_for_claims(in_subject, priv) == "Globex"

    global_claim = _claim(
        author="lucia",
        room="support",
        private=False,
        subject="refund approval threshold",
        scope="*",
    )
    assert customer_for_claims(global_claim, priv) == "all customers"


def test_publication_policy_blocks_private_derived_fields_outside_conflict_and_ops() -> None:
    public_claim = _claim(
        author="maria",
        room="sales",
        private=False,
        subject="SSO",
        scope="Acme",
        value="live on December 1",
    )
    private_claim = _claim(
        author="tomas",
        room="engineering",
        private=True,
        subject="auth migration blocker",
        scope="*",
        value="removed from Q4 delivery",
    )
    reason = "Sales promised December 1 while engineering removed it from Q4."
    consents = {
        "clm_tomas": ConsentPacket(
            candidate_id="sb-0001",
            claim_id="clm_tomas",
            author="tomas",
            granted=True,
            text=PRIVATE_QUOTE,
        )
    }

    with pytest.raises(PublicationPolicyError, match="Derived value"):
        assert_can_publish(
            "sales",
            "Engineering says SSO was removed from Q4 delivery.",
            private_claims=[private_claim],
            public_claims=[public_claim],
            consents=consents,
        )

    with pytest.raises(PublicationPolicyError, match="Derived subject"):
        assert_can_publish(
            "support",
            "Note on auth migration blocker.",
            private_claims=[private_claim],
            public_claims=[public_claim],
            consents=consents,
        )

    with pytest.raises(PublicationPolicyError, match="Classifier reason"):
        assert_can_publish(
            "sales",
            f"Summary: {reason}",
            private_claims=[private_claim],
            public_claims=[public_claim],
            consents=consents,
            classifier_reason=reason,
        )

    with pytest.raises(PublicationPolicyError, match="Verbatim quote"):
        assert_can_publish(
            "splitbrain-ops",
            f"Quote: {PRIVATE_QUOTE}",
            private_claims=[private_claim],
            public_claims=[public_claim],
            consents=consents,
        )

    with pytest.raises(PublicationPolicyError, match="without author consent"):
        assert_can_publish(
            "conflict-sb-0001-sso",
            f"Quote: {PRIVATE_QUOTE}",
            private_claims=[private_claim.model_copy(update={"text": PRIVATE_QUOTE})],
            public_claims=[public_claim],
            consents={"clm_tomas": False},
        )

    # Allowed in splitbrain-ops (derived fields only, no verbatim quote)
    assert_can_publish(
        "splitbrain-ops",
        f"Subject: auth migration blocker. Value: removed from Q4 delivery. Reason: {reason}",
        private_claims=[private_claim],
        public_claims=[public_claim],
        consents=consents,
        classifier_reason=reason,
    )

    # Allowed in the conflict room when consent is granted
    assert_can_publish(
        "conflict-sb-0001-sso",
        f'Tomás: "{PRIVATE_QUOTE}" (removed from Q4 delivery)',
        private_claims=[private_claim],
        public_claims=[public_claim],
        consents=consents,
        classifier_reason=reason,
    )

    # Approved decision text is allowed to travel to any team channel
    decision_text = "SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today."
    assert_can_publish(
        "sales",
        f'Update: @maria and @tomas resolved a conflict about SSO for Acme. "{decision_text}"',
        private_claims=[private_claim],
        public_claims=[public_claim],
        consents=consents,
        approved_decision_text=decision_text,
    )


def test_public_topic_fields_never_select_private_derived_subject_when_claim_a_is_private() -> None:
    private_first = CandidatePacket(
        id="sb-0009",
        claim_a=_claim(
            author="tomas",
            room="engineering",
            private=True,
            subject="internal auth migration",
            subject_key="sso",
            scope="*",
            scope_key="*",
            value="removed from Q4 delivery",
        ),
        claim_b=_claim(
            author="maria",
            room="sales",
            private=False,
            subject="SSO",
            subject_key="sso",
            scope="Acme",
            scope_key="acme",
            value="live on December 1",
        ),
        confidence=0.91,
    )
    assert public_topic_fields(private_first) == ("SSO", "sso", "Acme", "acme")


async def test_publish_decision_twice_creates_single_commitment_entry_and_single_followup_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_TZ", "America/Caracas")
    fake = FakeSwitch(arbiter_mod.AGENT_NAME)
    fake.state.add_origin("r-ops", "sw-ops-1")
    arbiter = _make_arbiter(fake)
    arbiter.coverage.rooms["r-conflict"] = "conflict-sb-0001-sso"

    ver = _sso_verification()
    ver.room_id = "r-conflict"
    ver.document_id = ""
    ver.record = arbiter._open_record(ver)
    arbiter.verifications[ver.candidate.id] = ver
    arbiter.by_room["r-conflict"] = ver.candidate.id
    await arbiter._save_record(ver)

    assert ver.machine is not None
    ver.machine.handle(
        "maria",
        "decision: SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today.",
    )
    outcome = ver.machine.handle("tomas", "confirm")
    ver.machine.decided_at = "2026-11-06T14:30:00+00:00"
    ver.machine.confirmations[-1].confirmed_at = "2026-11-06T14:30:00+00:00"
    outcome = ver.machine._outcome()

    # First run via _on_decided -> _publish_decision
    await arbiter._on_decided(ver, outcome)
    assert ver.followup_logged is True
    assert ver.durable is not None and ver.durable.followup_logged is True

    # Running _publish_decision a second time (and even after simulating a lost flag checkpoint)
    await arbiter._publish_decision(ver, retry=True)
    ver.followup_logged = False
    ver.durable.followup_logged = False
    await arbiter._publish_decision(ver, retry=True)

    commitments_docs = [
        doc
        for doc in fake.state.documents.values()
        if doc["room_id"] == "r-ops" and doc["name"].startswith(CUSTOMER_COMMITMENTS_DOC)
    ]
    assert len(commitments_docs) == 1
    assert commitments_docs[0]["content"].count("[SB-0001]") == 1

    followup_posts = [
        post["body"]
        for post in fake.posts
        if post["room_id"] == "r-conflict" and post["body"].startswith("Follow-up for @")
    ]
    assert followup_posts == [
        'Follow-up for @María Gómez: tell Acme (due Nov 6). Logged in "Customer commitments".'
    ]


async def test_standby_arbiter_adopting_decided_room_with_followup_logged_does_not_repeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_TZ", "America/Caracas")
    primary_switch = FakeSwitch(arbiter_mod.AGENT_NAME)
    primary_switch.state.add_origin("r-ops", "sw-ops-1")
    primary = _make_arbiter(primary_switch, name=arbiter_mod.AGENT_NAME)
    primary.coverage.rooms["r-conflict"] = "conflict-sb-0001-sso"

    ver = _sso_verification()
    ver.room_id = "r-conflict"
    ver.document_id = ""
    ver.record = primary._open_record(ver)
    primary.verifications[ver.candidate.id] = ver
    primary.by_room["r-conflict"] = ver.candidate.id
    await primary._save_record(ver)

    assert ver.machine is not None
    ver.machine.handle(
        "maria",
        "decision: SSO beta for Acme on December 15, GA in Q1. I'll tell Acme today.",
    )
    ver.machine.handle("tomas", "confirm")
    ver.machine.decided_at = "2026-11-06T14:30:00+00:00"
    ver.machine.confirmations[-1].confirmed_at = "2026-11-06T14:30:00+00:00"
    await primary._on_decided(ver, ver.machine._outcome())

    records, _ = await load_decision_records(primary_switch, "r-conflict", "sb-0001")
    saved = latest_record(records)
    assert saved is not None and saved.state is not None
    assert saved.state.followup_logged is True

    standby_switch = FakeSwitch(arbiter_mod.STANDBY_NAME, primary_switch.state)
    standby = _make_arbiter(standby_switch, name=arbiter_mod.STANDBY_NAME)
    standby.is_holder = False
    await standby._ensure_role()

    adopted = standby.verifications["sb-0001"]
    assert adopted.decided is True
    assert adopted.followup_logged is True
    assert adopted.durable is not None and adopted.durable.followup_logged is True
    assert adopted.followup_task is not None
    assert adopted.followup_task.action == "tell Acme"
    assert not standby_switch.posts

    commitments_docs = [
        doc
        for doc in primary_switch.state.documents.values()
        if doc["room_id"] == "r-ops" and doc["name"].startswith(CUSTOMER_COMMITMENTS_DOC)
    ]
    assert len(commitments_docs) == 1
    assert commitments_docs[0]["content"].count("[SB-0001]") == 1


async def test_sentinel_correction_containing_private_derived_value_is_blocked(
    tmp_path: Path,
    llm_factory: Any,
) -> None:
    switch = FakeSwitch("splitbrain-sentinel")
    switch.state.add_origin("r-sales", "sw_clm_maria")
    switch.state.add_origin("r-engineering", "sw_clm_tomas")
    switch.state.documents["doc-1"] = {
        "id": "doc-1",
        "name": "SB-0001 decision record",
        "room_id": "r-conflict",
        "owner": arbiter_mod.AGENT_NAME,
        "content": "SB-0001 decision record\n\nStatus: DECIDED\n",
    }

    llm, _, _, _ = llm_factory([], mode="live")
    store = ClaimStore(tmp_path / "sentinel.db")
    await store.add_claim(
        Claim(
            id="clm_maria",
            room_id="r-sales",
            room_name="sales",
            channel_type="channel_public",
            message_id="sw_clm_maria",
            author="maria",
            ts=1793776781000,
            text=PUBLIC_QUOTE,
            subject="SSO",
            subject_key="sso",
            scope="Acme",
            scope_key="acme",
            value="December 1",
        )
    )
    await store.add_claim(
        Claim(
            id="clm_tomas",
            room_id="r-engineering",
            room_name="engineering",
            channel_type="channel_private",
            message_id="sw_clm_tomas",
            author="tomas",
            ts=1793776782000,
            text=PRIVATE_QUOTE,
            subject="internal auth migration blocker",
            subject_key="sso",
            scope="*",
            scope_key="*",
            value="removed from Q4 delivery",
        )
    )

    sentinel = Sentinel(
        agent=switch,  # type: ignore[arg-type]
        llm=llm,
        store=store,
        state=bootstrap.BootstrapState(
            rooms={
                "splitbrain-ops": bootstrap.RoomState(
                    room_id="r-ops", channel_type="channel_private"
                ),
                "sales": bootstrap.RoomState(room_id="r-sales", channel_type="channel_public"),
                "engineering": bootstrap.RoomState(
                    room_id="r-engineering", channel_type="channel_private"
                ),
            }
        ),
    )
    try:
        leaking_packet = DecidedPacket(
            candidate_id="sb-0001",
            decision=Decision(
                candidate_id="sb-0001",
                room_id="r-conflict",
                text="SSO beta for Acme on December 15, GA in Q1.",
                proposed_by="maria",
                confirmed_by="tomas",
                decided_at="2026-11-06T14:30:00+00:00",
            ),
            conflict_room="r-conflict",
            conflict_room_name="conflict-sb-0001-sso",
            origins=[
                OriginRef(
                    room_id="r-sales",
                    room_name="sales",
                    thread_id="sw_clm_maria",
                    message_id="sw_clm_maria",
                    author="maria",
                    claim_id="clm_maria",
                ),
                OriginRef(
                    room_id="r-engineering",
                    room_name="engineering",
                    thread_id="sw_clm_tomas",
                    message_id="sw_clm_tomas",
                    author="tomas",
                    claim_id="clm_tomas",
                ),
            ],
            # Topic leaks the private room's extracted value into the team room update:
            subject="SSO (removed from Q4 delivery)",
            subject_key="sso",
            scope="Acme",
            scope_key="acme",
            authors=["maria", "tomas"],
        )
        frame = MessageFrame(
            sequence=10,
            room_id="r-ops",
            payload=MessagePayload(
                sender_name=arbiter_mod.AGENT_NAME,
                message_id="sw-decided-leak",
                thread_id="sw-ops-1",
                body=encode("decided", leaking_packet),
            ),
        )
        with pytest.raises(PublicationPolicyError, match="Derived value"):
            await sentinel.on_frame(frame)
        assert switch.posts == []
        assert "sb-0001" not in sentinel.corrected
    finally:
        await sentinel.aclose()


def test_arbiter_refuses_to_publish_outside_conflict_and_ops_rooms() -> None:
    fake = FakeSwitchAgent()
    arbiter = _make_arbiter(fake)
    ver = _sso_verification()
    with pytest.raises(PublicationPolicyError, match="Arbiter cannot publish to #sales"):
        arbiter._validate_post("r-sales", "Hello #sales", verification=ver, room_name="sales")

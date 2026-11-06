"""Independent examples for revisions, authorized exceptions and retained conflicts."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from splitbrain.config import LLMSettings
from splitbrain.core.classifier import Classifier
from splitbrain.core.classifier_guard import guard_classification
from splitbrain.core.extractor import Extractor
from splitbrain.core.models import Claim, ClaimKind, Relation
from splitbrain.llm.cassette import CassetteStore
from splitbrain.llm.client import LLMClient
from splitbrain.recording import _scenario_messages


def _claim(text: str, **changes: object) -> Claim:
    fields: dict[str, object] = {
        "id": "old",
        "message_id": "old-message",
        "room_id": "planning",
        "room_name": "planning",
        "author": "alex",
        "ts": 100,
        "text": text,
        "kind": "policy",
        "subject": "Archive export",
        "subject_key": "archive-export",
        "scope": "Northstar",
        "scope_key": "northstar",
        "value": text,
    }
    fields.update(changes)
    return Claim.model_validate(fields)


def _later(text: str, **changes: object) -> Claim:
    return _claim(
        text,
        **{
            "id": "new",
            "message_id": "new-message",
            "room_id": "delivery",
            "room_name": "delivery",
            "author": "bea",
            "ts": 200,
            **changes,
        },
    )


@pytest.mark.parametrize(
    "text",
    [
        "Correction to my earlier note: Northstar archive exports cost 17 CAD, not 19 CAD.",
        "Correction to my own post: Northstar archive exports cost 17 CAD, not 19 CAD.",
        "Corrección a mi nota anterior: exportar el archivo de Northstar cuesta 17 CAD.",
        "Rectificación a mi mensaje anterior: la cuota de Northstar pasa a 17 CAD.",
    ],
)
def test_explicit_self_correction_can_be_relayed_to_another_room(text: str) -> None:
    result = guard_classification(
        _claim("Northstar archive exports cost 19 CAD from April."), _later(text)
    )
    assert result is not None and result.relation == Relation.UPDATE


@pytest.mark.parametrize(
    ("room", "text"),
    [
        ("compliance", "Actualización de cumplimiento: el archivo se guarda solo para auditoría."),
        ("engineering", "Engineering update: archive exports are enabled only for auditing."),
        ("product", "Update from product: archive exports now cost 17 CAD."),
    ],
)
def test_named_originating_team_can_revise_its_internal_note(room: str, text: str) -> None:
    result = guard_classification(
        _claim("Archive exports are enabled for all Northstar workflows.", room_name=room),
        _later(text),
    )
    assert result is not None and result.relation == Relation.UPDATE


def test_internal_plan_revision_requires_explicit_withdrawal_of_the_old_value() -> None:
    old = _claim("Archive export goes live for Northstar in April.")
    new = _later("Engineering update: exports ship in June; the April slot is cancelled.")
    for a, b in ((old, new), (new, old)):
        result = guard_classification(a, b)
        assert result is not None and result.relation == Relation.UPDATE


@pytest.mark.parametrize(
    "text",
    [
        "Engineering update: exports ship in June; another feature was cancelled.",
        "Engineering update: exports ship in June, with an April preview.",
        "Update: exports might ship in June; the April slot would be cancelled.",
        "Update: if exports ship in June, the April slot is cancelled.",
        "Update: the proposal moves exports to June; the April slot is cancelled.",
        "Correction to my earlier note: do archive exports move to June?",
        "Archive exports are now planned for June instead of April.",
    ],
)
def test_ambiguous_or_tentative_internal_changes_defer_to_model(text: str) -> None:
    assert (
        guard_classification(_claim("Archive exports ship for Northstar in April."), _later(text))
        is None
    )


@pytest.mark.parametrize(
    "promise",
    [
        "We promised Northstar archive exports in April.",
        "Confirmed with Northstar: archive exports go live in April.",
        "The signed Northstar contract requires archive exports in April.",
        "Confirmamos a Northstar que el archivo se entrega en abril.",
        "Nos comprometimos con Northstar a entregar el archivo en abril.",
    ],
)
def test_another_team_revision_does_not_undo_a_customer_promise(promise: str) -> None:
    assert (
        guard_classification(
            _claim(promise, room_name="sales"),
            _later("Engineering update: exports ship in June; the April slot is cancelled."),
        )
        is None
    )


def test_same_author_can_explicitly_correct_their_own_customer_promise() -> None:
    result = guard_classification(
        _claim("I promised Northstar archive exports in April."),
        _later("Correction to my earlier note: exports ship in June.", author="alex"),
    )
    assert result is not None and result.relation == Relation.UPDATE


@pytest.mark.parametrize(("old_ts", "new_ts"), [(0, 0), (100, 100), (300, 200), (0, 200)])
def test_revision_needs_a_known_newer_message(old_ts: int, new_ts: int) -> None:
    assert (
        guard_classification(
            _claim("Archive exports cost 19 CAD.", ts=old_ts),
            _later("Correction to my earlier note: exports cost 17 CAD.", ts=new_ts),
        )
        is None
    )


@pytest.mark.parametrize(
    ("general_scope", "exception_scope", "text"),
    [
        ("*", "northstar", "An approved exception gives Northstar 240 archive exports per hour."),
        (
            "northstar",
            "northstar",
            "Finance signed an exception: Northstar overnight archive exports cost 17 CAD.",
        ),
        (
            "northstar",
            "northstar-overnight",
            "Compliance granted Northstar overnight a signed exception for 240 exports per hour.",
        ),
        (
            "*",
            "northstar",
            "Dirección autorizó una excepción: Northstar puede exportar 240 archivos por hora.",
        ),
        ("*", "northstar", "The exception is approved for Northstar archive exports at 240/hour."),
    ],
)
def test_authorized_scoped_exceptions_can_coexist_with_general_rule(
    general_scope: str, exception_scope: str, text: str
) -> None:
    old = _claim("Archive exports are limited to 120 per hour.", scope_key=general_scope)
    new = _later(text, scope_key=exception_scope)
    for a, b in ((old, new), (new, old)):
        result = guard_classification(a, b)
        assert result is not None and result.relation == Relation.COMPATIBLE


@pytest.mark.parametrize(
    "text",
    [
        "An exception gives Northstar 240 archive exports per hour.",
        "Northstar requested an approved exception for 240 archive exports per hour.",
        "An approved exception for Northstar is pending the compliance review.",
        "If approved, an exception gives Northstar 240 archive exports per hour.",
        "The exception is not approved for Northstar archive exports at 240/hour.",
        "Finance never signed an exception for Northstar archive exports at 240/hour.",
        "Finance has not yet signed an exception for Northstar exports at 240/hour.",
        "The approved exception for Northstar archive exports at 240/hour was rejected.",
        "No ha sido aprobada la excepción de Northstar para 240 exportaciones por hora.",
        "An approved exception for Northstar expired yesterday; the limit is 240/hour.",
        "Finance removed the approved exception for Northstar archive exports at 240/hour.",
        "No se autorizó una excepción: Northstar tiene 240 exportaciones por hora.",
        "An approved exception gives every customer, including Northstar, 240 exports/hour.",
        "An approved exception gives Southbank 240 archive exports per hour.",
        "Finance signed an exception for Southbank. Northstar exports are limited to 240/hour.",
    ],
)
def test_unapproved_unbounded_or_inapplicable_exceptions_defer(text: str) -> None:
    assert (
        guard_classification(
            _claim("Archive exports are limited to 120 per hour.", scope_key="*"), _later(text)
        )
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "Northstar archive exports are limited to 120 per hour, with no exceptions.",
        "The approved exception for Northstar was revoked; exports are limited to 120 per hour.",
    ],
)
def test_policy_disputing_an_exception_still_needs_classification(text: str) -> None:
    assert (
        guard_classification(
            _claim(text),
            _later("An approved exception gives Northstar 240 archive exports per hour."),
        )
        is None
    )


def test_grace_period_alone_does_not_establish_compatibility() -> None:
    assert (
        guard_classification(
            _claim("Northstar archive exports cost 19 CAD from April."),
            _later("There is a 14-day grace period after April starts before Northstar pays."),
        )
        is None
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"scope_key": "southbank"},
        {"subject_key": "archive-import"},
        {"kind": ClaimKind.DECISION, "message_id": "decision:sb-4321"},
        {"kind": ClaimKind.DECISION, "room_name": "conflict-sb-4321-archive"},
    ],
)
def test_guard_preserves_scope_subject_and_human_decision_boundaries(
    changes: dict[str, object],
) -> None:
    assert (
        guard_classification(
            _claim("Archive exports cost 19 CAD.", **changes),
            _later("Correction to my earlier note: exports cost 17 CAD."),
        )
        is None
    )


async def test_classifier_guards_model_false_alarm_without_rewriting_raw_cassette(
    llm_factory, tmp_path: Path
) -> None:
    raw = {"relation": "contradiction", "confidence": 0.94, "reason": "Different prices."}
    llm, transport, _, _ = llm_factory([raw])
    try:
        result = await Classifier(llm).classify(
            _claim("Archive exports cost 19 CAD."),
            _later("Correction to my earlier note: exports cost 17 CAD."),
        )
    finally:
        await llm.aclose()
    assert result.relation == Relation.UPDATE
    assert len(transport.calls) == 1
    recorded = next((tmp_path / "cassettes" / "classify").glob("*.json"))
    assert json.loads(recorded.read_text(encoding="utf-8"))["output"] == raw


async def test_classifier_preserves_model_non_contradiction(llm_factory) -> None:
    raw = {"relation": "unrelated", "confidence": 0.81, "reason": "Different concerns."}
    llm, _, _, _ = llm_factory([raw])
    try:
        result = await Classifier(llm).classify(
            _claim("Archive exports cost 19 CAD."),
            _later("Correction to my earlier note: exports cost 17 CAD."),
        )
    finally:
        await llm.aclose()
    assert result.model_dump(mode="json") == raw


async def test_demo_sso_pair_remains_a_contradiction_without_network() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = replace(LLMSettings.load(mode="replay"), api_key="")
    cassettes = CassetteStore(root / "cassettes", model=settings.model, mode="replay")
    llm = LLMClient(settings, cassettes)
    messages = [
        m for m in _scenario_messages("sso", root) if m.room_name in {"sales", "engineering"}
    ]
    try:
        claims = await Extractor(llm).extract_batch(messages)
        a, b = (claims[message.message_id][0] for message in messages)
        result = await Classifier(llm).classify(a, b)
    finally:
        await llm.aclose()
    assert result.relation == Relation.CONTRADICTION
    assert result.confidence >= 0.7
    assert llm.stats().calls == 0


async def test_sso_with_an_explicit_engineering_update_still_conflicts(llm_factory) -> None:
    llm, _, _, _ = llm_factory(
        [{"relation": "contradiction", "confidence": 0.94, "reason": "Customer promise broken."}]
    )
    try:
        result = await Classifier(llm).classify(
            _claim(
                "Confirmed with Acme: SSO will be live for them on December 1.",
                room_name="sales",
                subject="SSO",
                subject_key="sso",
                scope_key="acme",
            ),
            _later(
                "Engineering update: SSO moves to Q1; the December slot is cancelled.",
                room_name="engineering",
                subject="SSO",
                subject_key="sso",
                scope_key="*",
                kind=ClaimKind.DECISION,
            ),
        )
    finally:
        await llm.aclose()
    assert result.relation == Relation.CONTRADICTION
    assert result.confidence >= 0.7

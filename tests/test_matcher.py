"""SPEC 4.4 step 3: model-free matching rules."""

from __future__ import annotations

from splitbrain.core.matcher import find_matches, match_report
from splitbrain.core.models import Claim, ClaimStatus


def claim(
    identifier: str = "c1",
    *,
    room: str = "sales",
    author: str = "maria",
    subject: str = "SSO",
    subject_key: str = "sso",
    scope_key: str = "acme",
    status: ClaimStatus = ClaimStatus.ACTIVE,
) -> Claim:
    return Claim(
        id=identifier,
        room_id=room,
        room_name=room,
        author=author,
        message_id=f"m-{identifier}",
        text="placeholder chat text",
        kind="commitment",
        subject=subject,
        subject_key=subject_key,
        scope="Acme" if scope_key == "acme" else scope_key,
        scope_key=scope_key,
        value="live on 2026-12-01",
        polarity="affirm",
        confidence=0.9,
        status=status,
    )


def test_same_subject_different_room_matches() -> None:
    new = claim("new", room="engineering", author="tomas")
    assert [c.id for c in find_matches(new, [claim("old")])] == ["old"]


def test_same_room_is_skipped() -> None:
    new = claim("new", room="sales", author="tomas")
    report = match_report(new, [claim("old")])
    assert report.matches == []
    assert "same room" in report.skip_reasons


def test_same_author_is_skipped() -> None:
    new = claim("new", room="engineering", author="maria")
    report = match_report(new, [claim("old")])
    assert report.matches == []
    assert report.skip_reasons == ("same author",)


def test_different_scope_is_skipped() -> None:
    new = claim("new", room="engineering", author="tomas", scope_key="globex")
    report = match_report(new, [claim("old", scope_key="acme")])
    assert report.matches == []
    assert "different scope" in report.skip_reasons


def test_global_scope_matches_any_scope() -> None:
    new = claim("new", room="engineering", author="tomas", scope_key="*")
    assert find_matches(new, [claim("old", scope_key="acme")])
    scoped = claim("scoped", room="engineering", author="tomas", scope_key="acme")
    assert find_matches(scoped, [claim("old", scope_key="*")])


def test_different_subject_is_skipped_but_fuzzy_synonym_matches() -> None:
    new = claim(
        "new", room="engineering", author="tomas", subject="Refund policy", subject_key="refunds"
    )
    assert not find_matches(new, [claim("old", subject="SSO", subject_key="sso")])
    fuzzy = claim(
        "fuzzy", room="engineering", author="tomas", subject="SSO login", subject_key="sso-login"
    )
    assert find_matches(fuzzy, [claim("old", subject="SSO")])


def test_pairs_seen_and_superseded_are_skipped() -> None:
    new = claim("new", room="engineering", author="tomas")
    old = claim("old")
    assert not find_matches(new, [old], pairs_seen={"new|old"})
    assert not find_matches(new, [old.model_copy(update={"status": ClaimStatus.SUPERSEDED})])


def test_multiple_active_claims_returns_all_matches() -> None:
    new = claim("new", room="engineering", author="tomas")
    stored = [claim("old1", room="sales"), claim("old2", room="support")]
    assert {c.id for c in find_matches(new, stored)} == {"old1", "old2"}

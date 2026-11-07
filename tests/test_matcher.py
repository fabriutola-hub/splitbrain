"""Model-free matching rules."""

from __future__ import annotations

from splitbrain.core.matcher import find_matches, match_report
from splitbrain.core.models import Claim, ClaimKind, ClaimStatus


def claim(
    identifier: str = "c1",
    *,
    room: str = "sales",
    author: str = "maria",
    subject: str = "SSO",
    subject_key: str = "sso",
    scope_key: str = "acme",
    kind: ClaimKind = ClaimKind.COMMITMENT,
    status: ClaimStatus = ClaimStatus.ACTIVE,
    ts: int = 0,
    value: str = "live on 2026-12-01",
    text: str = "",
) -> Claim:
    return Claim(
        id=identifier,
        room_id=room,
        room_name=room,
        author=author,
        message_id=f"m-{identifier}",
        text=text,
        kind=kind,
        subject=subject,
        subject_key=subject_key,
        scope="Acme" if scope_key == "acme" else scope_key,
        scope_key=scope_key,
        value=value,
        polarity="affirm",
        confidence=0.9,
        status=status,
        ts=ts,
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


def test_decision_claims_have_priority_and_ignore_same_author_filter() -> None:
    new_by_maria = claim("new", room="sales", author="maria")
    other_claim = claim("ordinary", room="support", author="lucia")
    decision_claim = claim(
        "decided",
        room="conflict-sb-0001-sso",
        author="maria",
        kind=ClaimKind.DECISION,
    )
    matches = find_matches(new_by_maria, [other_claim, decision_claim])
    assert [c.id for c in matches] == ["decided", "ordinary"]


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
        "new",
        room="engineering",
        author="tomas",
        subject="Refund policy",
        subject_key="refunds",
        value="refund policy applies",
    )
    old = claim(
        "old",
        subject="SSO",
        subject_key="sso",
        value="SSO available",
    )
    assert not find_matches(new, [old])
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


def test_matches_are_decisions_first_then_most_recent() -> None:
    new = claim("new", room="engineering", author="tomas", ts=500)
    old = claim("old", room="sales", ts=100)
    recent = claim("recent", room="support", ts=300)
    decision = claim("decision", room="conflict-sb-0001-sso", kind=ClaimKind.DECISION, ts=50)
    matches = find_matches(new, [old, recent, decision])
    assert [item.id for item in matches] == ["decision", "recent", "old"]


def refunds_support() -> Claim:
    return claim(
        "refunds-support",
        room="support",
        author="lucia",
        subject="refund approval threshold",
        subject_key="refunds",
        scope_key="*",
        value="refunds above $500 can be approved without manager sign-off",
        text=(
            "Quick reminder for the desk: customer refunds above $500 are still fine to "
            "approve ourselves, no manager sign-off needed."
        ),
    )


def refunds_finance(subject: str, subject_key: str) -> Claim:
    return claim(
        "refunds-finance",
        room="finance",
        author="pablo",
        subject=subject,
        subject_key=subject_key,
        scope_key="*",
        value="manager approval required above $250",
        text=(
            "Policy update from finance: as of this week the manager-approval threshold is "
            "$250, so anything above $250 needs my OK."
        ),
    )


def test_refunds_pair_forms_when_subject_key_is_approval_threshold() -> None:
    finance = refunds_finance("refund approval threshold", "approval-threshold")
    assert find_matches(finance, [refunds_support()])


def test_refunds_pair_forms_with_a_manager_approval_variant() -> None:
    finance = refunds_finance("manager approval threshold", "manager-approval-threshold")
    assert find_matches(finance, [refunds_support()])


def test_beta_and_general_availability_are_the_same_launch() -> None:
    beta = claim(
        "beta",
        room="marketing",
        author="emma",
        subject="mobile app beta",
        subject_key="mobile-app-beta",
        scope_key="*",
        value="opens on 2026-12-01",
        text="The mobile app beta opens on December 1 for selected customers.",
    )
    ga = claim(
        "ga",
        room="engineering",
        author="owen",
        subject="mobile app general availability",
        subject_key="mobile-app-ga",
        scope_key="*",
        value="general availability in Q1",
        text="The mobile app reaches general availability in Q1 after the December beta.",
    )
    assert find_matches(ga, [beta])


def test_different_topics_that_share_a_word_do_not_match() -> None:
    residency = claim(
        "residency",
        room="security",
        author="hana",
        subject="data residency",
        subject_key="data-region",
        scope_key="*",
        value="data stays in Frankfurt",
        text="All EU customer data must stay in the Frankfurt region.",
    )
    retention = claim(
        "retention",
        room="data",
        author="noah",
        subject="data retention",
        subject_key="backup-retention",
        scope_key="*",
        value="retention is 30 days",
        text="Backup retention is 30 days for every customer.",
    )
    assert not find_matches(retention, [residency])

    rate_limit = claim(
        "rate-limit",
        room="product",
        author="priya",
        subject="API rate limit",
        subject_key="api-rate-limits",
        scope_key="*",
        value="1000 requests per minute",
        text="The API rate limit is 1000 requests per minute.",
    )
    api_keys = claim(
        "api-keys",
        room="engineering",
        author="owen",
        subject="API keys",
        subject_key="api-keys",
        scope_key="*",
        value="rotate every 90 days",
        text="API keys rotate every 90 days.",
    )
    assert not find_matches(api_keys, [rate_limit])

    hours = claim(
        "hours",
        room="support",
        author="lucia",
        subject="support hours",
        subject_key="support-hours",
        scope_key="*",
        value="24/7 coverage",
        text="Support goes 24/7 from January 1.",
    )
    plan = claim(
        "plan",
        room="ops",
        author="dana",
        subject="support plan",
        subject_key="support-plan",
        scope_key="*",
        value="premium plan",
        text="The support plan is premium for all customers.",
    )
    assert not find_matches(plan, [hours])


def test_same_topic_for_another_customer_does_not_match() -> None:
    acme = claim(
        "acme",
        room="finance",
        author="pablo",
        subject="refund approval threshold",
        subject_key="refunds",
        scope_key="acme",
        value="refunds above $250 need approval",
        text="For Acme, refunds above $250 need manager approval.",
    )
    globex = claim(
        "globex",
        room="support",
        author="lucia",
        subject="refund approval threshold",
        subject_key="refunds",
        scope_key="globex",
        value="refunds above $500 need approval",
        text="For Globex, refunds above $500 need manager approval.",
    )
    report = match_report(globex, [acme])
    assert report.matches == []
    assert "different scope" in report.skip_reasons


def test_scope_prefix_matches_a_site_but_not_a_region() -> None:
    customer = claim(
        "customer",
        room="pricing",
        author="nadia",
        subject="refrigerated pallet price",
        subject_key="pallet-pricing",
        scope_key="kestrel-logistics",
        value="40 USD per pallet",
        text="Every Kestrel Logistics site pays 40 USD per refrigerated pallet from April.",
    )
    site = claim(
        "site",
        room="billing",
        author="ravi",
        subject="refrigerated pallet price",
        subject_key="pallet-pricing",
        scope_key="kestrel-logistics-oslo",
        value="32 USD per pallet",
        text="Finance approved an exception: the Kestrel Logistics Oslo site pays 32 USD.",
    )
    assert find_matches(site, [customer])

    region = claim(
        "region",
        room="ops",
        author="dana",
        subject="data residency",
        subject_key="data-region",
        scope_key="kestrel-logistics-latam",
        value="data moves to Lima",
        text="Kestrel Logistics LATAM data moves to Lima.",
    )
    assert not find_matches(region, [customer])


def test_shared_distinctive_value_links_the_same_commitment() -> None:
    commitment = claim(
        "commitment",
        room="operaciones",
        author="elena",
        subject="solar inverter availability",
        subject_key="solar-inverter-availability",
        scope_key="nordvik-energi",
        value="98% availability",
        text=(
            "Nos comprometimos con Nordvik Energi a un 98% de disponibilidad para los "
            "inversores solares."
        ),
    )
    correction = claim(
        "correction",
        room="energia",
        author="ivan",
        subject="uptime commitment",
        subject_key="uptime-sla",
        scope_key="nordvik-energi",
        value="99%",
        text=("Corrección a mi nota anterior: el compromiso con Nordvik Energi es de 99%, no 98%."),
    )
    assert find_matches(correction, [commitment])

"""Canonical keys: one concept -> one slug, and the subject/scope swap guard."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from splitbrain.core.keys import (
    canonical_scope_key,
    canonical_subject_key,
    slugify,
)
from splitbrain.core.models import ExtractedClaim


@pytest.mark.parametrize(
    "value",
    ["SSO", "single sign-on", "SAML login", "SAML SSO", "oidc", "Single-Sign-On"],
)
def test_sso_synonyms_share_one_key(value: str) -> None:
    assert canonical_subject_key(value) == "sso"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("refund approval threshold", "refunds"),
        ("API rate limits", "api-rate-limits"),
        ("Rate limiting", "api-rate-limits"),
        ("requests per minute", "api-rate-limits"),
        ("Data residency", "data-region"),
        ("uptime SLA", "uptime-sla"),
        ("Q4 launch date", "q4-launch-date"),
        ("Trial Period", "trial-length"),
        ("Holiday cover", "holiday-cover"),
        ("Refund policy", "refunds"),
    ],
)
def test_other_canonical_families(value: str, expected: str) -> None:
    assert canonical_subject_key(value) == expected


def test_slugify_and_scope() -> None:
    assert slugify("Acme Corp!") == "acme-corp"
    assert canonical_scope_key("*") == "*"
    assert canonical_scope_key("Global") == "*"
    assert canonical_scope_key("ACME") == "acme"
    assert canonical_scope_key("EU customers") == "eu-customers"
    assert canonical_scope_key("Q4") == "*"
    assert canonical_scope_key("2026-12-01") == "*"
    assert canonical_scope_key("December") == "*"


def test_pydantic_normalizes_keys_on_the_way_in() -> None:
    claim = ExtractedClaim(
        subject="single sign-on",
        subject_key="Single Sign-On",
        scope="ACME Corp",
        scope_key="ACME Corp",
        value="live on December 1",
    )
    assert claim.subject_key == "sso"
    assert claim.scope_key == "acme-corp"


def test_pydantic_rejects_an_obvious_subject_scope_swap() -> None:
    with pytest.raises(ValidationError, match="looks like a customer name"):
        ExtractedClaim(
            subject="Acme",
            subject_key="acme",
            scope="SSO go-live date",
            scope_key="sso-go-live-date",
            value="December 1",
        )

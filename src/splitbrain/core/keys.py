"""Canonical lowercase slugs: the same concept always gets the same key.

The model is asked to do this (see prompts.py); this module is the deterministic
backstop that guarantees it across messages, batches and models.
"""

from __future__ import annotations

import re
import unicodedata

# Customer names used as scopes. A subject_key equal to one of these is almost
# certainly a subject/scope swap (verified failure mode on River AI).
KNOWN_CUSTOMER_KEYS = frozenset(
    {
        "acme",
        "globex",
        "initech",
        "contoso",
        "northwind",
        "umbrella",
        "hooli",
        "stark-industries",
        "wayne-enterprises",
        "bluewave",
        "helios",
    }
)

_ALIASES: dict[str, str] = {
    "single-sign-on": "sso",
    "saml-login": "sso",
    "saml-sso": "sso",
    "saml": "sso",
    "oidc-login": "sso",
    "oidc": "sso",
    "enterprise-login": "sso",
    "sso-login": "sso",
    "sso-rollout": "sso",
    "refund-policy": "refunds",
    "refund-approval": "refunds",
    "refund-threshold": "refunds",
    "refund-approval-threshold": "refunds",
    "refund": "refunds",
    "price-increase": "pricing",
    "price": "pricing",
    "list-price": "pricing",
    "rate-limiting": "api-rate-limits",
    "rate-limit": "api-rate-limits",
    "rate-limits": "api-rate-limits",
    "api-rate-limit": "api-rate-limits",
    "requests-per-minute": "api-rate-limits",
    "data-residency": "data-region",
    "data-residency-region": "data-region",
    "data-region": "data-region",
    "uptime-sla": "uptime-sla",
    "sla": "uptime-sla",
    "support-hours": "support-hours",
    "holiday-cover": "holiday-cover",
    "pto-policy": "holiday-cover",
    "vacation-policy": "holiday-cover",
    "trial-period": "trial-length",
    "trial": "trial-length",
    "launch": "launch-date",
    "release-date": "launch-date",
    "go-live-date": "launch-date",
    "invoice-payment-terms": "invoice-terms",
    "payment-terms": "invoice-terms",
    "net-30-terms": "invoice-terms",
    "onboarding-fee": "onboarding-fee",
    "audit-log-export": "audit-log-export",
    "audit-logs": "audit-log-export",
    "backup-window": "backup-retention",
    "webhook-retries": "webhook-retries",
    "seat-limit": "seat-limits",
    "seats": "seat-limits",
    "mobile-app": "mobile-app",
    "mobile-release": "mobile-app",
    "dark-mode": "dark-mode",
}

# Token rules catch inflected or compounded slugs the exact map misses. Matching
# whole hyphen-separated tokens avoids accidental hits inside unrelated words.
_TOKEN_RULES: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"sso", "saml", "oidc"}), "sso"),
    (frozenset({"refund", "refunds", "reembolso", "reembolsos"}), "refunds"),
    (frozenset({"residency", "region", "regions"}), "data-region"),
    (frozenset({"uptime", "sla"}), "uptime-sla"),
    (frozenset({"trial", "trials"}), "trial-length"),
    (frozenset({"holiday", "vacation", "pto", "vacaciones"}), "holiday-cover"),
)

_COMPOUND_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("rate-limit", "ratelimit", "requests-per-minute"), "api-rate-limits"),
    (("single-sign-on",), "sso"),
)

_GLOBAL_TOKENS = frozenset({"", "*", "all", "global", "everyone", "company-wide", "todos"})

# A date, quarter or weekday is a value, never a scope. River AI sometimes put
# "Q4" in scope; collapsing those to "*" keeps matching honest without a retry.
_TEMPORAL_TOKENS = frozenset(
    {
        "q1",
        "q2",
        "q3",
        "q4",
        "quarter",
        "today",
        "tomorrow",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    }
)


def slugify(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")
    return slug or "*"


def canonical_subject_key(value: str) -> str:
    key = slugify(str(value))
    if key in _ALIASES:
        return _ALIASES[key]
    for needles, canonical in _COMPOUND_RULES:
        if any(needle in key for needle in needles):
            return canonical
    tokens = frozenset(key.split("-"))
    for needles, canonical in _TOKEN_RULES:
        if tokens & needles:
            return canonical
    return key


def canonical_scope_key(value: str) -> str:
    text = str(value).strip().casefold()
    if text in _GLOBAL_TOKENS:
        return "*"
    key = slugify(text)
    tokens = set(key.split("-"))
    if tokens & _TEMPORAL_TOKENS or any(part.isdigit() for part in tokens):
        return "*"
    return key

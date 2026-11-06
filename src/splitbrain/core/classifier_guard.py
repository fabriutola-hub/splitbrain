"""Conservative, model-free exclusions for explicit revisions and exceptions."""

from __future__ import annotations

import re
import unicodedata

from .models import Claim, ClaimKind, ClassificationResult, Relation


def _text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(c for c in folded if not unicodedata.combining(c)).split())


_SELF_CORRECTION = re.compile(
    r"^(?:correction to my (?:earlier|previous|own) (?:note|post|message)|"
    r"(?:correccion|rectificacion) a mi (?:nota|mensaje|publicacion) anterior)\s*:"
)
_REVISION_HEADER = re.compile(
    r"^(?:(?:update|correction|revision|actualizacion|correccion|rectificacion)"
    r"(?: (?:from|by|de|del) (?P<source>[^:]{1,40}))?|"
    r"(?P<team>[a-z][a-z -]{1,30}) (?:update|correction|revision))\s*:"
)
_WITHDRAWAL = re.compile(
    r"\b(?:supersed(?:ed|ing)|cancelled|canceled|void|no longer applies|"
    r"ya no aplica|deja sin efecto|queda sin efecto|anulad[oa]|cancelad[oa])\b"
)
_VALUE_ANCHOR = re.compile(
    r"\b(?:\d+(?:[.,:/-]\d+)*|q[1-4]|january|february|march|april|may|june|july|"
    r"august|september|october|november|december|enero|febrero|marzo|abril|mayo|"
    r"junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b"
)
_EXTERNAL_COMMITMENT = re.compile(
    r"\b(?:promis(?:e[ds]?|ing)|committed|commitment|confirmed (?:with|to)|"
    r"signed|contract(?:ual)?|agreement|order form|promet\w*|"
    r"(?:nos )?compromet\w*|confirm\w* (?:con|a)|contrato|firmad[oa])\b"
)
_TENTATIVE_REVISION = re.compile(
    r"\b(?:if|unless|perhaps|maybe|might|could|pending|proposed|proposal|"
    r"request(?:ed|ing)?|awaiting|not approved|not authorized|"
    r"si|quiza|podria|pendiente|propuesta|solicit\w*)\b"
)
_AUTHORIZED_EXCEPTION = re.compile(
    r"\b(?:approved|authorized|authorised|signed|granted|autoriz\w*|aprob\w*|"
    r"firmo|firmada|conced\w*)\b[^.!?;:]{0,80}\b(?:exception|excepcion)\b|"
    r"\b(?:exception|excepcion)\s+(?:(?:has been|was|is|esta|ha sido)\s+)?"
    r"(?:approved|authorized|authorised|signed|aprobada|autorizada|firmada)\b"
)
_EXCEPTION_DENIAL = re.compile(
    r"\b(?:no exceptions?|without exceptions?|"
    r"(?:not|never|no)\b[^.!?;:]{0,35}\b(?:approved|authorized|authorised|signed|"
    r"aprobo|autorizo|firmo|aprobada|autorizada)|unapproved|unauthorized|denied|rejected|"
    r"revok\w*|rescind\w*|expir\w*|removed|cancel\w*|sin excepciones|"
    r"no (?:se )?(?:aprobo|autorizo|firmo|aprobada|autorizada)|rechaz\w*)\b"
)
_UNIVERSAL_EXCEPTION = re.compile(
    r"\b(?:all customers|every customer|everyone|all integrations|every integration|"
    r"todos los clientes|todas las integraciones)\b"
)
_TEAM_NAMES = {
    "engineering": "engineering",
    "ingenieria": "engineering",
    "product": "product",
    "producto": "product",
    "compliance": "compliance",
    "cumplimiento": "compliance",
    "finance": "finance",
    "finanzas": "finance",
    "operations": "operations",
    "operaciones": "operations",
    "sales": "sales",
    "ventas": "sales",
    "legal": "legal",
}


def _recorded_decision(claim: Claim) -> bool:
    return claim.kind == ClaimKind.DECISION and (
        claim.message_id.startswith("decision:") or claim.room_name.startswith("conflict-")
    )


def _overlapping_scope(a: Claim, b: Claim) -> bool:
    return a.scope_key == b.scope_key or "*" in (a.scope_key, b.scope_key)


def _team(value: str) -> str:
    normalized = _text(value).replace("-", " ").strip("# ")
    return _TEAM_NAMES.get(normalized, normalized)


def _revision(earlier: Claim, later: Claim) -> str | None:
    # Cache order is lexical, not chronological; unknown/tied timestamps defer.
    if earlier.ts <= 0 or later.ts <= earlier.ts:
        return None
    text = _text(later.text)
    if _TENTATIVE_REVISION.search(text) or "?" in text:
        return None
    own_correction = _SELF_CORRECTION.match(text)
    header = _REVISION_HEADER.match(text)
    if not (own_correction or header):
        return None
    same_author = earlier.author.casefold() == later.author.casefold()
    # A new internal plan does not undo another person's customer promise.
    if not same_author and _EXTERNAL_COMMITMENT.search(_text(earlier.text)):
        return None
    if own_correction or same_author:
        return "An explicit correction replaces the earlier note, rather than a customer promise."
    assert header is not None
    source = header.group("source") or header.group("team")
    if source and _team(source) == _team(earlier.room_name):
        return "The originating team explicitly revises its earlier internal statement."
    old_values = set(_VALUE_ANCHOR.findall(_text(earlier.text)))
    if _WITHDRAWAL.search(text) and old_values & set(_VALUE_ANCHOR.findall(text)):
        return "The internal plan explicitly withdraws the earlier value and supplies a revision."
    return None


def _scoped_exception(general: Claim, exception: Claim) -> bool:
    text = _text(exception.text)
    if (
        not _AUTHORIZED_EXCEPTION.search(text)
        or _TENTATIVE_REVISION.search(text)
        or _EXCEPTION_DENIAL.search(text)
        or _EXCEPTION_DENIAL.search(_text(general.text))
        or _UNIVERSAL_EXCEPTION.search(text)
        or exception.scope_key == "*"
    ):
        return False
    # Keep authorization and its scope in one sentence; other claims may share a message.
    scope_words = set(exception.scope_key.split("-"))
    scope_matches = general.scope_key == "*" or set(general.scope_key.split("-")) <= scope_words
    return scope_matches and any(
        _AUTHORIZED_EXCEPTION.search(sentence) and scope_words <= set(re.findall(r"\w+", sentence))
        for sentence in re.split(r"[.!?;]", text)
    )


def guard_classification(a: Claim, b: Claim) -> ClassificationResult | None:
    """Return a narrow non-alert rule; otherwise leave the model's answer intact.

    Explicit authorization is taken from the message, not verified externally.
    Human decision records always stay on the normal classification path.
    """
    if a.subject_key != b.subject_key or _recorded_decision(a) or _recorded_decision(b):
        return None
    if _overlapping_scope(a, b):
        earlier, later = sorted((a, b), key=lambda claim: claim.ts)
        reason = _revision(earlier, later)
        if reason:
            return ClassificationResult(relation=Relation.UPDATE, confidence=0.95, reason=reason)
    if _scoped_exception(a, b) or _scoped_exception(b, a):
        return ClassificationResult(
            relation=Relation.COMPATIBLE,
            confidence=0.95,
            reason="An explicitly authorized, scoped exception can coexist with the general rule.",
        )
    return None

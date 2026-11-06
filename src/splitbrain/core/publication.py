"""Cross-room publication policy for quotes, derived fields and human decisions.

Splitbrain enforces three publication boundaries across Switch rooms:

1. A verbatim quote from a ``channel_private`` room is shown only in the
   private ``conflict-sb-*`` room and only after its author grants consent
   (plus inside the targeted ``sb:consent`` packet to the Arbiter). It is never
   posted in ``splitbrain-ops`` readable text, in ``Customer commitments``, or
   in any team room.
2. Fields derived by the model from a ``channel_private`` message (extracted
   ``subject``, extracted ``value``, classifier ``reason``) may appear only in
   ``splitbrain-ops`` and in the private ``conflict-sb-*`` room — never in team
   rooms.
3. The only content from a conflict resolution that travels to other channels
   (origin-thread corrections and decision-memory reminders) is the exact
   decision text that the two authors wrote and confirmed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..config import SplitbrainError
from .models import Claim, ClaimKind
from .protocol import CandidatePacket, ConsentPacket, OriginRef, PacketClaim

OPS_ROOM = "splitbrain-ops"
CONFLICT_PREFIX = "conflict-"

PUBLICATION_NOTICE = (
    "Once you decide, your exact decision text (nothing else from this room) "
    "will be posted in both original threads, logged in Customer commitments "
    "and used to answer anyone who repeats the old information."
)


class PublicationPolicyError(SplitbrainError):
    """Raised when an outbound message violates the cross-room publication policy."""


def _clean_room(room_name: str) -> str:
    return room_name.strip().lstrip("#").casefold()


def is_ops_room(room_name: str) -> bool:
    return _clean_room(room_name) == OPS_ROOM


def is_conflict_room(room_name: str) -> bool:
    return _clean_room(room_name).startswith(CONFLICT_PREFIX)


def is_internal_room(room_name: str) -> bool:
    """True only for ``splitbrain-ops`` and ``conflict-*`` resolution rooms."""
    return is_ops_room(room_name) or is_conflict_room(room_name)


def is_private_claim(claim: Claim | PacketClaim) -> bool:
    return claim.channel_type == "channel_private" or bool(getattr(claim, "text_withheld", False))


def format_prior_claim(claim: Claim | PacketClaim) -> str:
    """Format an original claim for ``Customer commitments`` in ``splitbrain-ops``.

    Private-room claims never include their verbatim quote or extracted value
    outside the conflict room: only the room name and subject are recorded.
    """
    subject = (claim.subject or claim.subject_key or "unknown").strip()
    if is_private_claim(claim):
        return f"#{claim.room_name} (private, subject: {subject})"
    quote = (claim.text or "").strip()
    if quote:
        return f'#{claim.room_name} (subject: {subject}): "{quote}"'
    value = (claim.value or "").strip()
    if value:
        return f"#{claim.room_name} (subject: {subject}, value: {value})"
    return f"#{claim.room_name} (subject: {subject})"


def public_topic_fields(candidate: CandidatePacket) -> tuple[str, str, str, str]:
    """Return ``(subject, subject_key, scope, scope_key)`` safe for team rooms.

    When ``claim_a`` comes from a private channel and ``claim_b`` is public,
    prefer the public claim's extracted subject and scope so private derived
    fields are not echoed into public origin threads.
    """
    a, b = candidate.claims
    if is_private_claim(a) and not is_private_claim(b):
        subject = b.subject or b.subject_key or a.subject_key
        subject_key = b.subject_key or a.subject_key
        scope = b.scope if b.scope and b.scope != "*" else "*"
        scope_key = b.scope_key if b.scope_key and b.scope_key != "*" else "*"
        return subject, subject_key, scope, scope_key
    if is_private_claim(a) and is_private_claim(b):
        key = a.subject_key or b.subject_key or "topic"
        return key, key, "*", "*"
    scope = a.scope
    scope_key = a.scope_key
    if (not scope or scope == "*") and not is_private_claim(b) and b.scope and b.scope != "*":
        scope = b.scope
        scope_key = b.scope_key
    return a.subject or a.subject_key, a.subject_key, scope or "*", scope_key or "*"


def _consent_granted(
    claim_id: str, consents: Mapping[str, ConsentPacket | bool] | None
) -> tuple[bool, str | None]:
    if not consents or claim_id not in consents:
        return False, None
    entry = consents[claim_id]
    if isinstance(entry, bool):
        return entry, None
    return bool(entry.granted), entry.text


def assert_can_publish(
    target_room: str,
    body: str,
    *,
    private_claims: Iterable[Claim | PacketClaim] = (),
    public_claims: Iterable[Claim | PacketClaim] = (),
    consents: Mapping[str, ConsentPacket | bool] | None = None,
    classifier_reason: str | None = None,
    approved_decision_text: str | None = None,
) -> str:
    """Validate that ``body`` obeys the cross-room publication policy for ``target_room``.

    Raises :class:`PublicationPolicyError` if:
    - a verbatim quote from a private claim appears outside a conflict room, or
      in a conflict room without granted consent;
    - a derived field from a private claim (``value``, private-only ``subject``,
      or ``classifier_reason``) appears in a room other than a conflict room or
      ``splitbrain-ops`` (excluding the exact human-approved decision text).
    """
    if not target_room or not target_room.strip():
        raise PublicationPolicyError("Target room name is required for publication checks.")

    inspected = body
    if approved_decision_text and approved_decision_text.strip():
        inspected = inspected.replace(approved_decision_text.strip(), "")

    public_terms = {
        term.strip().casefold()
        for claim in public_claims
        if not is_private_claim(claim)
        for term in (claim.subject, claim.subject_key, claim.scope)
        if term and term.strip()
    }

    internal = is_internal_room(target_room)
    conflict = is_conflict_room(target_room)

    for claim in private_claims:
        if not is_private_claim(claim):
            continue
        granted, consent_text = _consent_granted(claim.id, consents)
        for quote in (claim.text, consent_text):
            cleaned_quote = (quote or "").strip()
            if cleaned_quote and cleaned_quote in inspected:
                if not conflict:
                    raise PublicationPolicyError(
                        f"Verbatim quote from private room #{claim.room_name} cannot be "
                        f"published in #{target_room.lstrip('#')} (allowed only in the "
                        "conflict room after author consent)."
                    )
                if not granted:
                    raise PublicationPolicyError(
                        f"Verbatim quote from private room #{claim.room_name} cannot be "
                        f"published in #{target_room.lstrip('#')} without author consent."
                    )

        if not internal:
            value = (claim.value or "").strip()
            if value and value in inspected:
                raise PublicationPolicyError(
                    f"Derived value {value!r} from private room #{claim.room_name} cannot "
                    f"be published in #{target_room.lstrip('#')} (allowed only in conflict "
                    "rooms and splitbrain-ops)."
                )
            subject = (claim.subject or "").strip()
            if subject and subject.casefold() not in public_terms and subject in inspected:
                raise PublicationPolicyError(
                    f"Derived subject {subject!r} from private room #{claim.room_name} cannot "
                    f"be published in #{target_room.lstrip('#')} (allowed only in conflict "
                    "rooms and splitbrain-ops)."
                )

    if not internal and classifier_reason and classifier_reason.strip():
        reason = classifier_reason.strip()
        if reason in inspected:
            raise PublicationPolicyError(
                f"Classifier reason {reason!r} cannot be published in "
                f"#{target_room.lstrip('#')} (allowed only in conflict rooms and "
                "splitbrain-ops)."
            )

    return body


def assert_arbiter_can_publish(
    target_room: str,
    body: str,
    *,
    verification: Any = None,
    approved_decision_text: str | None = None,
) -> str:
    """Enforce that the Arbiter publishes only to internal rooms and obeys the policy."""
    if not is_internal_room(target_room):
        raise PublicationPolicyError(
            f"Arbiter cannot publish to #{target_room.lstrip('#')}; "
            "allowed only in conflict rooms and splitbrain-ops."
        )
    claims = verification.claims if verification is not None else ()
    consents = verification.consents if verification is not None else None
    reason = verification.candidate.reason if verification is not None else None
    if approved_decision_text is None and verification is not None and verification.machine:
        approved_decision_text = verification.machine.decision
    return assert_can_publish(
        target_room,
        body,
        private_claims=claims,
        public_claims=claims,
        consents=consents,
        classifier_reason=reason,
        approved_decision_text=approved_decision_text,
    )


async def collect_policy_claims(
    store: Any,
    candidate_id: str,
    *,
    record: str | None = None,
    origins: Iterable[OriginRef] = (),
) -> tuple[list[Claim | PacketClaim], str | None]:
    """Gather stored claims and decision-record metadata for Sentinel publication checks."""
    from .decision_record import STATE_PREFIX, DecisionRecord

    claims: list[Claim | PacketClaim] = []
    seen_ids: set[str] = set()
    reason: str | None = None

    if store is not None:
        for origin in origins:
            claim = await store.claim_by_id(origin.claim_id)
            if claim is not None and claim.id not in seen_ids:
                claims.append(claim)
                seen_ids.add(claim.id)
        if hasattr(store, "candidate_by_id"):
            candidate = await store.candidate_by_id(candidate_id)
            if candidate is not None:
                reason = reason or candidate.reason or None
                for cand_claim in (candidate.claim_a, candidate.claim_b):
                    if cand_claim.id not in seen_ids:
                        claims.append(cand_claim)
                        seen_ids.add(cand_claim.id)

    if record and STATE_PREFIX in record:
        try:
            state = DecisionRecord.model_validate_json(record.rpartition(STATE_PREFIX)[2])
            reason = reason or state.candidate.reason or None
            for pkt_claim in state.candidate.claims:
                if pkt_claim.id not in seen_ids:
                    claims.append(pkt_claim)
                    seen_ids.add(pkt_claim.id)
                else:
                    claims.append(pkt_claim)
        except ValueError:
            pass

    if not claims and store is not None and hasattr(store, "all_claims"):
        for stored_claim in await store.all_claims():
            if stored_claim.kind != ClaimKind.DECISION and stored_claim.id not in seen_ids:
                claims.append(stored_claim)
                seen_ids.add(stored_claim.id)

    return claims, reason

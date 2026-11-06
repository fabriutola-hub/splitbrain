"""Post-decision business outcomes: Customer commitments log and follow-up tasks.

Every action here uses ONLY the decision text that the two claim authors wrote
and confirmed in the conflict room:

1. ``Customer commitments`` room document in ``splitbrain-ops`` (created on the
   first decision with ``create_room_document``, updated on subsequent decisions
   with ``update_room_document``). Records the customer, topic, exact decision
   text, proposer, confirmer, local timestamp, conflict room, and the two prior
   claims replaced (room and subject only for private channels).
2. Follow-up task in the conflict room when the approved decision text contains
   an explicit commitment to communicate or act (``"I'll tell Acme today"``,
   ``"I'll retire the macro today"``, ``"I'll email them"``). Never invented
   when no commitment was written.
3. One-line closing summary in the conflict room after thread corrections land.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .. import bootstrap
from .keys import KNOWN_CUSTOMER_KEYS, canonical_scope_key, slugify
from .models import Claim, Decision
from .protocol import CandidatePacket, PacketClaim
from .publication import (
    OPS_ROOM,
    assert_can_publish,
    format_prior_claim,
    is_private_claim,
)
from .timefmt import short_day, stamp_iso

CUSTOMER_COMMITMENTS_DOC = "Customer commitments"

_GENERIC_SCOPES = frozenset(
    {
        "",
        "*",
        "all",
        "all customers",
        "customers",
        "customer",
        "global",
        "everyone",
        "company-wide",
        "todos",
    }
)

_GENERIC_SUBJECT_TARGETS = frozenset(
    {
        "all",
        "customers",
        "customer",
        "everyone",
        "enterprise",
        "global",
        "team",
        "teams",
        "support",
        "sales",
        "engineering",
        "finance",
        "q1",
        "q2",
        "q3",
        "q4",
    }
)

_FIRST_PERSON_COMMITMENT_RE = re.compile(
    r"\b(?:I'll|I\s+will|I'm\s+going\s+to|I\s+am\s+going\s+to|voy\s+a)\s+"
    r"(?P<clause>[A-Za-z][^.!?;\r\n]*)",
    re.IGNORECASE,
)

_WE_COMMITMENT_RE = re.compile(
    r"\b(?:we'll|we\s+will)\s+"
    r"(?P<clause>(?:tell|email|notify|message|write|send|contact|inform|update|"
    r"retire|remove|call|ping|reach\s+out)\b[^.!?;\r\n]*)",
    re.IGNORECASE,
)

_TODAY_TAIL_RE = re.compile(
    r"\s+\b(?:today|now|tonight|right\s+away|asap|hoy|ahora)\s*$",
    re.IGNORECASE,
)
_TOMORROW_TAIL_RE = re.compile(
    r"\s+\b(?:tomorrow|mañana|manana)\s*$",
    re.IGNORECASE,
)
_PREPOSITION_DUE_TAIL_RE = re.compile(
    r"\s+\b(?:by|on|before|due)\s+"
    r"(?P<when>(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
    r"|today|tomorrow|next\s+week|this\s+week|end\s+of\s+day|EOD))\s*$",
    re.IGNORECASE,
)
_THIS_PERIOD_TAIL_RE = re.compile(
    r"\s+\b(?P<when>this\s+(?:morning|afternoon|evening|week))\s*$",
    re.IGNORECASE,
)
_TRAILING_CONJUNCTION_RE = re.compile(
    r",\s+(?:and|so|but|because|since|then)\b.*$",
    re.IGNORECASE,
)


def _person(author: str) -> str:
    return bootstrap.DEMO_USER_DISPLAY_NAMES.get(author, author)


def _decided_ts(decided_at: str) -> int:
    if not decided_at or not decided_at.strip():
        return int(time.time() * 1000)
    try:
        moment = datetime.fromisoformat(decided_at)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return int(moment.timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000)


def _customer_from_scope(scope: str) -> str | None:
    cleaned = scope.strip()
    if not cleaned or cleaned.casefold() in _GENERIC_SCOPES:
        return None
    if canonical_scope_key(cleaned) == "*":
        return None
    return cleaned


def _customer_from_subject(subject: str) -> str | None:
    cleaned = subject.strip()
    if not cleaned:
        return None
    slug_tokens = slugify(cleaned).split("-")
    for key in KNOWN_CUSTOMER_KEYS:
        key_parts = key.split("-")
        for idx in range(len(slug_tokens) - len(key_parts) + 1):
            if slug_tokens[idx : idx + len(key_parts)] == key_parts:
                pattern = re.compile(
                    r"\b" + r"[\s-]+".join(re.escape(part) for part in key_parts) + r"\b",
                    re.IGNORECASE,
                )
                match = pattern.search(cleaned)
                if match:
                    found = match.group(0)
                    return found if any(ch.isupper() for ch in found) else found.title()
                return key.replace("-", " ").title()
    for_match = re.search(r"\bfor\s+([A-Z][A-Za-z0-9_-]{1,30})\b", cleaned)
    if for_match:
        candidate = for_match.group(1)
        if (
            candidate.casefold() not in _GENERIC_SUBJECT_TARGETS
            and canonical_scope_key(candidate) != "*"
        ):
            return candidate
    return None


def customer_for_claims(
    claim_a: Claim | PacketClaim,
    claim_b: Claim | PacketClaim,
) -> str:
    """Resolve the customer name from the claims' scope or subject, or ``all customers``."""
    ordered = (
        (claim_a, claim_b)
        if not is_private_claim(claim_a) or is_private_claim(claim_b)
        else (claim_b, claim_a)
    )
    for claim in ordered:
        scoped = _customer_from_scope(claim.scope)
        if scoped is not None:
            return scoped
    for claim in ordered:
        named = _customer_from_subject(claim.subject)
        if named is not None:
            return named
    return "all customers"


def topic_for_claims(
    claim_a: Claim | PacketClaim,
    claim_b: Claim | PacketClaim,
) -> str:
    """Choose a human-readable topic for the commitment entry."""
    if not is_private_claim(claim_a) and (claim_a.subject or claim_a.subject_key):
        return (claim_a.subject or claim_a.subject_key).strip()
    if not is_private_claim(claim_b) and (claim_b.subject or claim_b.subject_key):
        return (claim_b.subject or claim_b.subject_key).strip()
    return (claim_a.subject or claim_a.subject_key or claim_b.subject or "topic").strip()


@dataclass(frozen=True, slots=True)
class FollowupTask:
    owner: str
    owner_display: str
    action: str
    due: str

    def format_message(self) -> str:
        return (
            f"Follow-up for @{self.owner_display}: {self.action} "
            f'(due {self.due}). Logged in "{CUSTOMER_COMMITMENTS_DOC}".'
        )


def _split_action_and_due(clause: str, base_ts: int) -> tuple[str, str]:
    cleaned = _TRAILING_CONJUNCTION_RE.sub("", clause.strip()).strip(" \t\r\n.!?,;:")
    today_label = short_day(base_ts)

    prep_match = _PREPOSITION_DUE_TAIL_RE.search(cleaned)
    if prep_match:
        action = cleaned[: prep_match.start()].strip(" \t\r\n.!?,;:")
        raw_when = prep_match.group("when").strip()
        lowered = raw_when.casefold()
        if lowered in ("today", "end of day", "eod"):
            due = today_label
        elif lowered == "tomorrow":
            due = short_day(base_ts + 86_400_000)
        else:
            due = raw_when
        return action, due

    period_match = _THIS_PERIOD_TAIL_RE.search(cleaned)
    if period_match:
        action = cleaned[: period_match.start()].strip(" \t\r\n.!?,;:")
        raw_when = period_match.group("when").strip()
        due = raw_when if "week" in raw_when.casefold() else today_label
        return action, due

    if _TODAY_TAIL_RE.search(cleaned):
        action = _TODAY_TAIL_RE.sub("", cleaned).strip(" \t\r\n.!?,;:")
        return action, today_label

    if _TOMORROW_TAIL_RE.search(cleaned):
        action = _TOMORROW_TAIL_RE.sub("", cleaned).strip(" \t\r\n.!?,;:")
        return action, short_day(base_ts + 86_400_000)

    return cleaned, today_label


def extract_followup_task(decision: Decision) -> FollowupTask | None:
    """Extract an explicit follow-up task from the approved decision text, or None."""
    text = re.sub(r"^\s*(?:decision|decisión)\s*:\s*", "", decision.text or "", flags=re.I)
    if not text.strip():
        return None
    match = _FIRST_PERSON_COMMITMENT_RE.search(text) or _WE_COMMITMENT_RE.search(text)
    if match is None:
        return None
    base_ts = _decided_ts(decision.decided_at)
    action, due = _split_action_and_due(match.group("clause"), base_ts)
    if not action:
        return None
    owner = decision.proposed_by
    return FollowupTask(
        owner=owner,
        owner_display=_person(owner),
        action=action,
        due=due,
    )


def format_commitment_entry(
    candidate: CandidatePacket,
    decision: Decision,
    conflict_room_name: str,
    *,
    task: FollowupTask | None = None,
) -> str:
    """Build one audit entry for the ``Customer commitments`` room document."""
    a, b = candidate.claims
    customer = customer_for_claims(a, b)
    topic = topic_for_claims(a, b)
    when = stamp_iso(decision.decided_at) if decision.decided_at else short_day(0)
    proposer = f"@{decision.proposed_by} ({_person(decision.proposed_by)})"
    confirmer = f"@{decision.confirmed_by} ({_person(decision.confirmed_by)})"
    prior_a = format_prior_claim(a)
    prior_b = format_prior_claim(b)
    lines = [
        f"[{candidate.id.upper()}] Customer: {customer} | Topic: {topic}",
        f'Decision: "{decision.text}"',
        f"Proposed by: {proposer} | Confirmed by: {confirmer}",
        f"Decided at: {when} | Conflict room: #{conflict_room_name.lstrip('#')}",
        f"Replaces: {prior_a}; {prior_b}",
    ]
    if task is not None:
        lines.append(f"Follow-up: @{task.owner_display} — {task.action} (due {task.due})")
    entry = "\n".join(lines)
    assert_can_publish(
        OPS_ROOM,
        entry,
        private_claims=candidate.claims,
        public_claims=candidate.claims,
        approved_decision_text=decision.text,
    )
    return entry


async def upsert_customer_commitments(
    agent: Any,
    ops_room_id: str,
    entry: str,
    *,
    state_holder: Any = None,
) -> tuple[str, str]:
    """Create or update the ``Customer commitments`` room document in ``splitbrain-ops``."""
    cached_id = str(getattr(state_holder, "_commitments_doc_id", "") or "")
    cached_content = str(getattr(state_holder, "_commitments_content", "") or "")

    async with agent.act_in(ops_room_id):
        doc_id = cached_id
        existing_content = cached_content
        if not doc_id:
            joined = await agent.op("connect_to_room", room_id=ops_room_id)
            documents = (joined.get("documents") if isinstance(joined, dict) else None) or []
            doc_id = next(
                (
                    str(doc.get("id") or doc.get("document_id") or "")
                    for doc in documents
                    if isinstance(doc, dict)
                    and (doc.get("id") or doc.get("document_id"))
                    and str(doc.get("name", "")) == CUSTOMER_COMMITMENTS_DOC
                ),
                "",
            )
            if doc_id:
                loaded = await agent.op("load_internal_documents", ids=[doc_id])
                items = (
                    loaded
                    if isinstance(loaded, list)
                    else (loaded.get("documents") if isinstance(loaded, dict) else None) or []
                )
                existing_content = "\n".join(
                    str(item.get("content", "")) for item in items if isinstance(item, dict)
                ).strip()

        if doc_id:
            updated = (
                f"{existing_content}\n\n{entry}"
                if existing_content
                else (f"{CUSTOMER_COMMITMENTS_DOC}\n\n{entry}")
            )
            await agent.op(
                "update_room_document",
                document_id=doc_id,
                content=updated,
            )
            if state_holder is not None:
                state_holder._commitments_doc_id = doc_id
                state_holder._commitments_content = updated
            return doc_id, updated

        initial = f"{CUSTOMER_COMMITMENTS_DOC}\n\n{entry}"
        created = await agent.op(
            "create_room_document",
            name=CUSTOMER_COMMITMENTS_DOC,
            description="Customer commitments and approved decisions across rooms",
            instructions=(
                "Maintained by the Arbiter. Entries reflect only human-approved decisions; "
                "private-room quotes are never included."
            ),
            content=initial,
        )
        new_id = (
            str(created.get("document_id") or created.get("id") or "")
            if isinstance(created, dict)
            else ""
        ) or "doc-customer-commitments"
        if state_holder is not None:
            state_holder._commitments_doc_id = new_id
            state_holder._commitments_content = initial
        return new_id, initial


async def record_business_followup(
    arbiter: Any,
    verification: Any,
    decision: Decision,
) -> FollowupTask | None:
    """Log the decision in ``Customer commitments`` and post any follow-up task."""
    task = extract_followup_task(decision)
    verification.followup_task = task
    entry = format_commitment_entry(
        verification.candidate,
        decision,
        verification.room_name,
        task=task,
    )
    await upsert_customer_commitments(
        arbiter.agent,
        arbiter.ops_room_id,
        entry,
        state_holder=arbiter,
    )
    if task is not None:
        verification.record += (
            f"\nFollow-up: @{task.owner_display} — {task.action} (due {task.due})"
        )
        task_line = task.format_message()
        assert_can_publish(
            verification.room_name or "conflict-room",
            task_line,
            private_claims=verification.claims,
            public_claims=verification.claims,
            consents=verification.consents,
            approved_decision_text=decision.text,
        )
        await arbiter.agent.post(verification.room_id or "", task_line)
    return task


def closing_summary_line(verification: Any, rooms_label: str) -> str:
    """One-line final summary in the conflict room after thread corrections land."""
    customer = customer_for_claims(*verification.claims)
    task: FollowupTask | None = getattr(verification, "followup_task", None)
    if task is not None:
        return (
            f'Corrections posted in {rooms_label}; "{CUSTOMER_COMMITMENTS_DOC}" '
            f"updated for {customer} in #splitbrain-ops; "
            f"follow-up assigned to @{task.owner_display}: {task.action} (due {task.due})."
        )
    return (
        f'Corrections posted in {rooms_label}; "{CUSTOMER_COMMITMENTS_DOC}" '
        f"updated for {customer} in #splitbrain-ops (no follow-up task)."
    )

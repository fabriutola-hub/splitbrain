"""Pydantic payloads for the detection pipeline."""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ..llm.cassette import normalize_text
from .keys import KNOWN_CUSTOMER_KEYS, canonical_scope_key, canonical_subject_key


class ClaimKind(StrEnum):
    COMMITMENT = "commitment"
    DECISION = "decision"
    POLICY = "policy"
    STATUS = "status"
    OTHER = "other"


class ClaimStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"


class Relation(StrEnum):
    CONTRADICTION = "contradiction"
    UPDATE = "update"
    COMPATIBLE = "compatible"
    UNRELATED = "unrelated"


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    room_id: str
    room_name: str
    channel_type: str = "channel_public"
    thread_id: str | None = None
    author: str
    sender_kind: str | None = None
    ts: int = 0
    text: str


class ExtractedClaim(BaseModel):
    """One claim as returned by the extraction model (no Switch metadata yet)."""

    model_config = ConfigDict(extra="forbid")

    kind: ClaimKind = ClaimKind.OTHER
    subject: str
    subject_key: str
    scope: str
    scope_key: str
    value: str
    polarity: Literal["affirm", "negate"] = "affirm"
    effective_date: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("subject_key", mode="before")
    @classmethod
    def _subject_key(cls, value: Any) -> str:
        key = canonical_subject_key(str(value))
        # Cheap repair guard for the swap River AI produced with a vague prompt.
        if key in KNOWN_CUSTOMER_KEYS:
            raise ValueError(
                "subject_key looks like a customer name; subject is the feature, policy or "
                "thing promised/decided, scope is the customer, segment or region"
            )
        return key

    @field_validator("scope_key", mode="before")
    @classmethod
    def _scope_key(cls, value: Any) -> str:
        return canonical_scope_key(str(value))

    @field_validator("effective_date")
    @classmethod
    def _date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    claims: list[ExtractedClaim] = Field(default_factory=list)


class ExtractionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[ExtractionResult]

    @model_validator(mode="after")
    def _one_result_per_message(self, info: ValidationInfo) -> ExtractionBatch:
        expected = (info.context or {}).get("expected_ids")
        if expected is None:
            return self
        got = [item.message_id for item in self.results]
        if got != list(expected):
            raise ValueError(
                f"return exactly one result per message in order {list(expected)}, got {got}"
            )
        return self


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: Relation
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str

    @field_validator("reason")
    @classmethod
    def _one_sentence(cls, value: str) -> str:
        return " ".join(value.split())


class Claim(ExtractedClaim):
    """A fully identified claim, as stored in the Sentinel's SQLite database."""

    id: str
    room_id: str
    room_name: str
    channel_type: str = "channel_public"
    message_id: str
    thread_id: str | None = None
    author: str
    ts: int = 0
    text: str
    status: ClaimStatus = ClaimStatus.ACTIVE


class Candidate(BaseModel):
    id: str
    claim_a: Claim
    claim_b: Claim
    relation: Relation = Relation.CONTRADICTION
    confidence: float
    reason: str
    created_at: str


class EvidenceItem(BaseModel):
    title: str
    url: str = ""
    state: str = ""
    milestone: str = ""
    labels: list[str] = Field(default_factory=list)
    updated_at: str = ""


EvidenceStatus = Literal[
    "supports_a",
    "supports_b",
    "conflicting",
    "inconclusive",
    "none",
    "unavailable",
]

EVIDENCE_SUMMARY_LABELS: dict[EvidenceStatus, str] = {
    "supports_a": "Supports A:",
    "supports_b": "Supports B:",
    "conflicting": "Ambiguous:",
    "inconclusive": "Insufficient evidence:",
    "none": "Insufficient evidence:",
    "unavailable": "Evidence unavailable:",
}
EVIDENCE_SUMMARY_LABEL_TEXTS: tuple[str, ...] = tuple(
    dict.fromkeys(EVIDENCE_SUMMARY_LABELS.values())
)


def labeled_evidence_summary(status: EvidenceStatus, summary: str) -> str:
    """Prefix one short summary with its status label, exactly once."""
    text = summary.strip()
    label = EVIDENCE_SUMMARY_LABELS[status]
    if not text:
        return label
    if any(text.casefold().startswith(item.casefold()) for item in EVIDENCE_SUMMARY_LABEL_TEXTS):
        return text
    return f"{label} {text}"


class Evidence(BaseModel):
    candidate_id: str
    source: Literal["github", "fixture", "scenario_fixture"]
    status: EvidenceStatus
    items: list[EvidenceItem] = Field(default_factory=list)
    # `summary` is one short source-free sentence for the brief; `detail` keeps
    # the full timeline/counts for the decision record and the ops thread.
    summary: str = ""
    detail: str = ""


class Decision(BaseModel):
    candidate_id: str
    room_id: str
    text: str
    proposed_by: str
    confirmed_by: str
    decided_at: str


class EvalSide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room: str
    author: str
    text: str


class EvalPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    a: EvalSide
    b: EvalSide
    label: Relation
    note: str = ""


def make_claim_id(message_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{message_id}|{index}".encode()).hexdigest()[:10]
    return f"clm_{digest}"


def claim_key(claim: Claim) -> str:
    """Canonical signature of a claim for the semantic classification cache."""
    room = re.sub(r"^conflict-sb-[0-9a-z]+-", "conflict-", claim.room_name)
    return "|".join(
        (
            room,
            claim.author,
            normalize_text(claim.text),
            claim.subject_key,
            claim.scope_key,
            normalize_text(claim.value),
            claim.polarity,
            claim.effective_date or "",
            str(claim.kind),
        )
    )


def claim_from_extraction(message: Message, extracted: ExtractedClaim, index: int) -> Claim:
    return Claim(
        **extracted.model_dump(),
        id=make_claim_id(message.message_id, index),
        room_id=message.room_id,
        room_name=message.room_name,
        channel_type=message.channel_type,
        message_id=message.message_id,
        thread_id=message.thread_id,
        author=message.author,
        ts=message.ts,
        text=message.text,
    )

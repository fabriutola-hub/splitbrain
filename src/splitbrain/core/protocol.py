"""Validated payloads for the inter-agent packets.

A `sb:candidate` carries a `text: null, text_withheld: true` claim for a quote
from a private room, so it cannot be validated as a `Candidate` from models.py
(that model has a non-nullable `text` and forbids extra fields). These models
are the tolerant wire contract; chat packets are untrusted data, so a bad
payload is logged and ignored rather than crashing the agent.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from .models import Decision, Evidence
from .packets import decode_message

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class WireModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class PacketClaim(WireModel):
    """One claim on the wire. A private quote has text=None until consent."""

    id: str
    room_id: str
    room_name: str
    channel_type: str = "channel_public"
    message_id: str
    thread_id: str | None = None
    author: str
    ts: int = 0
    text: str | None = None
    text_withheld: bool = False
    subject: str = ""
    subject_key: str = ""
    scope: str = "*"
    scope_key: str = "*"
    value: str = ""
    polarity: str = "affirm"
    effective_date: str | None = None
    confidence: float = 0.0
    status: str = "active"
    kind: str = "other"

    @property
    def thread_root(self) -> str:
        """Where a threaded reply to the original claim must be posted."""
        return self.thread_id or self.message_id

    @property
    def origin_label(self) -> str:
        return f"origin: #{self.room_name} ({self.author})"


class CandidatePacket(WireModel):
    id: str
    claim_a: PacketClaim
    claim_b: PacketClaim
    relation: str = "contradiction"
    confidence: float = 0.0
    reason: str = ""
    created_at: str = ""

    @property
    def claims(self) -> tuple[PacketClaim, PacketClaim]:
        return self.claim_a, self.claim_b


class EvidenceClaim(WireModel):
    room: str
    value: str = ""
    date: str | None = None


class EvidenceRequestPacket(WireModel):
    candidate_id: str
    subject: str
    subject_key: str = ""
    scope: str = "*"
    claim_a: EvidenceClaim
    claim_b: EvidenceClaim


class VerdictPacket(WireModel):
    candidate_id: str
    verdict: Literal["confirmed", "discarded"]
    confidence: float = 0.0
    evidence_status: str = "none"
    reason: str = ""


class ConsentRequestPacket(WireModel):
    candidate_id: str
    claim_id: str
    author: str
    other_author: str = ""
    room_id: str = ""
    thread_id: str = ""


class ConsentPacket(WireModel):
    candidate_id: str
    claim_id: str
    author: str
    granted: bool
    text: str | None = None


class OriginRef(WireModel):
    room_id: str
    room_name: str
    thread_id: str
    message_id: str
    author: str
    claim_id: str


class DecidedPacket(WireModel):
    candidate_id: str
    decision: Decision
    conflict_room: str
    conflict_room_name: str
    origins: list[OriginRef]
    subject: str
    subject_key: str = ""
    scope: str = "*"
    scope_key: str = "*"
    authors: list[str]


class CorrectedPacket(WireModel):
    candidate_id: str
    conflict_room: str
    conflict_room_name: str
    rooms: list[str]


class RemindedPacket(WireModel):
    candidate_id: str
    conflict_room: str
    conflict_room_name: str
    room_name: str
    author: str
    message_id: str


class LinkTarget(WireModel):
    room_id: str
    label: str


class LinkRequestPacket(WireModel):
    """Fallback: the Sentinel is a member of every origin room."""

    candidate_id: str
    conflict_room_id: str
    origins: list[LinkTarget]


class LinkedPacket(WireModel):
    candidate_id: str
    conflict_room_id: str
    labels: list[str]


PACKET_MODELS: dict[str, type[BaseModel]] = {
    "candidate": CandidatePacket,
    "evidence_request": EvidenceRequestPacket,
    "evidence": Evidence,
    "verdict": VerdictPacket,
    "consent_request": ConsentRequestPacket,
    "consent": ConsentPacket,
    "decided": DecidedPacket,
    "corrected": CorrectedPacket,
    "reminded": RemindedPacket,
    "link_request": LinkRequestPacket,
    "linked": LinkedPacket,
}


def validate(kind: str, data: dict[str, Any]) -> BaseModel | None:
    model = PACKET_MODELS.get(kind)
    if model is None:
        logger.warning("No payload model for packet %r; ignored", kind)
        return None
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        logger.warning("Ignoring malformed %s packet: %s", kind, exc)
        return None


def read_packet(body: str, sender_name: str) -> tuple[str, BaseModel] | None:
    """Return (kind, validated payload) for a packet from one of our agents."""
    decoded = decode_message(body, sender_name)
    if decoded is None:
        return None
    kind, data = decoded
    payload = validate(kind, data)
    if payload is None:
        return None
    return kind, payload

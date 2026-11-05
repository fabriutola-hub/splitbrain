"""Strict encode/decode of the `sb:<kind> {json}` packet line."""

from __future__ import annotations

import json
import logging
from collections.abc import Collection, Mapping
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

PACKET_KINDS = frozenset(
    {
        "candidate",
        "evidence_request",
        "evidence",
        "verdict",
        "consent_request",
        "consent",
        "decided",
        "corrected",
        "reminded",
        # Fallback: the Arbiter may ask the Sentinel (member of every origin
        # room) to create the room links if Switch refuses its own link_rooms.
        "link_request",
        "linked",
    }
)
OWN_AGENT_NAMES = frozenset(
    {
        "splitbrain-sentinel",
        "splitbrain-arbiter",
        "splitbrain-verifier",
        "splitbrain-arbiter-b",
    }
)


def encode(kind: str, payload: BaseModel | Mapping[str, Any]) -> str:
    if kind not in PACKET_KINDS:
        raise ValueError(f"Unknown packet kind: {kind!r}")
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else dict(payload)
    return f"sb:{kind} {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}"


def decode(line: str) -> tuple[str, dict[str, Any]] | None:
    """Parse one packet line; unknown kinds and bad JSON are logged and ignored."""
    text = line.strip()
    if not text.startswith("sb:"):
        logger.warning("Ignoring a non-packet line passed to decode(): %.80r", text)
        return None
    head, separator, body = text.partition(" ")
    if not separator or not body.strip():
        logger.warning("Ignoring a malformed packet line (no payload)")
        return None
    kind = head[3:]
    if kind not in PACKET_KINDS:
        logger.warning("Ignoring packet with unknown kind %r", kind)
        return None
    try:
        data = json.loads(body)
    except ValueError:
        logger.warning("Ignoring packet %r with invalid JSON", kind)
        return None
    if not isinstance(data, dict):
        logger.warning("Ignoring packet %r whose payload is not a JSON object", kind)
        return None
    return kind, data


def decode_message(
    body: str,
    sender_name: str,
    own_agent_names: Collection[str] | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Packets are trusted only when they come from one of our own agents."""
    allowed = OWN_AGENT_NAMES if own_agent_names is None else own_agent_names
    if sender_name not in allowed:
        return None
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    packet_lines = [line for line in lines if line.startswith("sb:")]
    if not packet_lines:
        return None
    if len(packet_lines) > 1 or lines[-1] != packet_lines[0]:
        logger.warning("Ignoring a message with more than one packet line or a packet not last")
        return None
    return decode(packet_lines[0])

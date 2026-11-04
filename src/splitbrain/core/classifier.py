"""Model-based pair classification, cached per ordered claim pair."""

from __future__ import annotations

from ..llm.cassette import classify_key
from ..llm.client import LLMClient
from ..llm.prompts import CLASSIFICATION_SYSTEM, build_classification_user
from .models import Claim, ClassificationResult, claim_key


def claim_view(claim: Claim) -> dict[str, object]:
    return {
        "room": claim.room_name,
        "author": claim.author,
        "text": claim.text,
        "kind": str(claim.kind),
        "subject": claim.subject,
        "subject_key": claim.subject_key,
        "scope": claim.scope,
        "scope_key": claim.scope_key,
        "value": claim.value,
        "polarity": claim.polarity,
        "effective_date": claim.effective_date,
    }


class Classifier:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def classify(self, claim_a: Claim, claim_b: Claim) -> ClassificationResult:
        key_a, key_b = claim_key(claim_a), claim_key(claim_b)
        first, second = sorted((claim_a, claim_b), key=claim_key)
        key = classify_key(key_a, key_b)
        description = (
            f"pair {first.subject_key}/{first.scope_key} in #{first.room_name} vs "
            f"{second.subject_key}/{second.scope_key} in #{second.room_name}"
        )
        result = await self.llm.cached(
            task="classify",
            key=key,
            description=description,
            input_payload={"claim_a": claim_view(first), "claim_b": claim_view(second)},
            system=CLASSIFICATION_SYSTEM,
            user=build_classification_user(first, second),
            schema=ClassificationResult,
        )
        return result

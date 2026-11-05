"""The shared detection path: prefilter -> extract -> match -> classify -> candidate.

`splitbrain eval` and the Sentinel both call `Brain.analyze_pair`, so the
numbers in eval/results.md describe exactly what the agent will do.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ..llm.client import LLMClient
from .classifier import Classifier
from .extractor import Extractor
from .matcher import match_report
from .models import Candidate, Claim, EvalPair, EvalSide, Message, Relation
from .prefilter import prefilter
from .store import ClaimStore, pair_id

CANDIDATE_THRESHOLD = 0.7


@dataclass(frozen=True, slots=True)
class PairResult:
    id: str
    label: str
    predicted: str
    relation: str | None
    confidence: float | None
    reason: str
    stage: str
    candidate: bool
    note: str


def message_from_side(pair_id: str, side: EvalSide, suffix: str, ts: int) -> Message:
    return Message(
        message_id=f"{pair_id}-{suffix}",
        room_id=side.room,
        room_name=side.room,
        author=side.author,
        text=side.text,
        ts=ts,
    )


class Brain:
    def __init__(self, llm: LLMClient) -> None:
        self.extractor = Extractor(llm)
        self.classifier = Classifier(llm)

    async def analyze_pair(self, pair: EvalPair, store: ClaimStore | None = None) -> PairResult:
        owns_store = store is None
        local_store = store or ClaimStore()
        try:
            return await self._analyze(pair, local_store)
        finally:
            if owns_store:
                await local_store.close()

    async def _analyze(self, pair: EvalPair, store: ClaimStore) -> PairResult:
        message_a = message_from_side(pair.id, pair.a, "a", 1)
        message_b = message_from_side(pair.id, pair.b, "b", 2)

        decisions = [prefilter(message_a), prefilter(message_b)]
        for side, message, decision in zip("ab", (message_a, message_b), decisions, strict=True):
            if not decision.keep:
                return self._result(
                    pair,
                    "unrelated",
                    stage="prefilter",
                    reason=(
                        f"message {side} in #{message.room_name} filtered out: {decision.reason}"
                    ),
                )
            if await store.is_processed(message.message_id):
                return self._result(
                    pair,
                    "unrelated",
                    stage="prefilter",
                    reason=f"message {side} already processed (idempotency)",
                )

        claims = await self.extractor.extract_batch([message_a, message_b])
        claims_a: list[Claim] = claims[message_a.message_id]
        claims_b: list[Claim] = claims[message_b.message_id]
        if not claims_a or not claims_b:
            return self._result(
                pair,
                "unrelated",
                stage="extraction",
                reason=(
                    f"no asserted claim extracted from message "
                    f"{'a' if not claims_a else 'b'} (question, hypothetical or chatter)"
                ),
            )

        for claim in claims_a:
            await store.add_claim(claim)
        for message in (message_a, message_b):
            await store.mark_processed(message.message_id)
        stored = await store.active_claims()

        best_match: tuple[Claim, Claim] | None = None
        skip_reasons: set[str] = set()
        for claim_b in claims_b:
            report = match_report(claim_b, stored)
            skip_reasons.update(report.skip_reasons)
            for claim_a in report.matches:
                if await store.has_pair(pair_id(claim_a, claim_b)):
                    skip_reasons.add("pair already seen")
                    continue
                best_match = (claim_a, claim_b)
                break
            if best_match:
                break

        if best_match is None:
            # A same-author revision is an update by product rule, not a conflict.
            only_same_author = skip_reasons == {"same author"}
            predicted = "update" if only_same_author else "unrelated"
            return self._result(
                pair,
                predicted,
                stage="matching",
                reason=(
                    "matcher rejected the pair ("
                    + ", ".join(sorted(skip_reasons) or ["no candidate claims"])
                    + ")"
                ),
            )

        claim_a, claim_b = best_match
        await store.mark_pair(pair_id(claim_a, claim_b))
        classification = await self.classifier.classify(claim_a, claim_b)
        candidate = (
            classification.relation == Relation.CONTRADICTION
            and classification.confidence >= CANDIDATE_THRESHOLD
        )
        if candidate:
            await store.add_candidate(
                Candidate(
                    id=f"sb-{pair.id}",
                    claim_a=claim_a,
                    claim_b=claim_b,
                    confidence=classification.confidence,
                    reason=classification.reason,
                    created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                )
            )
            predicted = "contradiction"
        else:
            # Below the threshold a contradiction is not raised: it is a non-alert.
            predicted = (
                "compatible"
                if classification.relation == Relation.CONTRADICTION
                else str(classification.relation)
            )
        return self._result(
            pair,
            predicted,
            stage="classification",
            reason=classification.reason,
            relation=str(classification.relation),
            confidence=classification.confidence,
            candidate=candidate,
        )

    @staticmethod
    def _result(
        pair: EvalPair,
        predicted: str,
        *,
        stage: str,
        reason: str,
        relation: str | None = None,
        confidence: float | None = None,
        candidate: bool = False,
    ) -> PairResult:
        return PairResult(
            id=pair.id,
            label=str(pair.label),
            predicted=predicted,
            relation=relation,
            confidence=confidence,
            reason=reason,
            stage=stage,
            candidate=candidate,
            note=pair.note,
        )

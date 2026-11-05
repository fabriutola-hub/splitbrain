"""Batched claim extraction with a semantic cassette per message.

One unique message body is extracted once per Brain instance. Reusing that exact
result for every pair keeps classification cassette keys stable across record and
replay, independently of batching or timing.
"""

from __future__ import annotations

from ..llm.cassette import extract_key, normalize_text
from ..llm.client import LLMClient
from ..llm.prompts import EXTRACTION_SYSTEM, build_extraction_user
from .models import (
    Claim,
    ExtractedClaim,
    ExtractionBatch,
    ExtractionResult,
    Message,
    claim_from_extraction,
)

DEFAULT_BATCH_SIZE = 8


def _describe(message: Message) -> str:
    body = normalize_text(message.text)[:100]
    return f"message {message.message_id} in #{message.room_name}: {body!r}"


class Extractor:
    def __init__(self, llm: LLMClient, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.llm = llm
        self.batch_size = batch_size
        self._cache: dict[str, list[ExtractedClaim]] = {}

    async def extract_batch(self, messages: list[Message]) -> dict[str, list[Claim]]:
        missing: list[Message] = []
        pending: set[str] = set()
        for message in messages:
            key = extract_key(message.text)
            if key not in self._cache and key not in pending:
                pending.add(key)
                missing.append(message)

        for start in range(0, len(missing), self.batch_size):
            self._cache.update(await self._extract_chunk(missing[start : start + self.batch_size]))

        return {
            message.message_id: [
                claim_from_extraction(message, claim, index)
                for index, claim in enumerate(self._cache[extract_key(message.text)])
            ]
            for message in messages
        }

    async def _extract_chunk(self, messages: list[Message]) -> dict[str, list[ExtractedClaim]]:
        keys = {message.message_id: extract_key(message.text) for message in messages}
        results: dict[str, ExtractionResult] = {}
        if self.llm.mode == "replay":
            for message in messages:
                results[message.message_id] = ExtractionResult.model_validate(
                    self.llm.cassettes.read("extract", keys[message.message_id], _describe(message))
                )
        else:
            to_call: list[Message] = []
            for message in messages:
                key = keys[message.message_id]
                if (
                    self.llm.mode == "record"
                    and not self.llm.cassettes.overwrite
                    and self.llm.cassettes.has("extract", key)
                ):
                    cached = self.llm.cassettes.read("extract", key, _describe(message))
                    cached["message_id"] = message.message_id
                    results[message.message_id] = ExtractionResult.model_validate(cached)
                else:
                    to_call.append(message)
            if to_call:
                batch = await self.llm.structured(
                    EXTRACTION_SYSTEM,
                    build_extraction_user(to_call),
                    ExtractionBatch,
                    context={"expected_ids": [message.message_id for message in to_call]},
                )
                for item in batch.results:
                    results[item.message_id] = item
                for message in to_call:
                    self.llm.cassettes.write(
                        "extract",
                        keys[message.message_id],
                        {
                            "message_id": message.message_id,
                            "room": message.room_name,
                            "author": message.author,
                            "text": message.text,
                        },
                        results[message.message_id].model_dump(mode="json"),
                    )
        return {keys[message_id]: result.claims for message_id, result in results.items()}

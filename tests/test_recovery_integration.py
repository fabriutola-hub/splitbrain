"""Run the recovery demo against a real stack, resetting it for an isolated case.

Run this test on its own: it owns the same stack and agent processes as the CLI
demo. Replay and fixture evidence make it independent of model keys and GitHub.
"""

from __future__ import annotations

import asyncio

import pytest

from splitbrain import demo

pytestmark = pytest.mark.integration


async def test_recovery_demo_preserves_the_case_across_both_process_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLITBRAIN_LLM_API_KEY", "")
    monkeypatch.setenv("NO_COLOR", "1")
    report = await asyncio.wait_for(
        demo.run(scenario="sso", auto_decide=True, recovery=True, offline=True), timeout=420.0
    )
    assert report is not None
    assert report.room_count == 1
    assert report.proposal_version == 1
    assert report.adopted_author == "maria"
    assert report.adopted_confirmations == 0
    assert report.decision_sender == "splitbrain-arbiter-b"
    assert report.sentinel_exit_code == 86
    assert report.checkpoint_statuses == ["posted", "pending"]
    assert report.correction_counts == [1, 1]
    assert report.decision_count == 1
    assert report.repeated_confirmations == 2
    assert report.canonical_document_id
    assert len(report.recovery_document_ids) == 1
    assert report.canonical_document_id not in report.recovery_document_ids

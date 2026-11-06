"""Explicit process-crash injection for demos and tests, disabled by default."""

from __future__ import annotations

import os

from .core.decision_record import CorrectionJournal

ENV_VAR = "SPLITBRAIN_FAULT"
SENTINEL_AFTER_FIRST = "sentinel-exit-after-first-correction"
EXIT_CODE = 86


def after_correction_checkpoint(journal: CorrectionJournal) -> None:
    if os.environ.get(ENV_VAR) != SENTINEL_AFTER_FIRST:
        return
    posted = [item for item in journal.threads if item.status == "posted"]
    if len(journal.threads) > 1 and len(posted) == 1:
        print(
            f"[DEMO FAULT] {SENTINEL_AFTER_FIRST}: receipt {posted[0].message_id} "
            f"saved for {journal.decided.candidate_id}; exiting with code {EXIT_CODE}.",
            flush=True,
        )
        os._exit(EXIT_CODE)

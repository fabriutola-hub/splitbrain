from collections import Counter
from pathlib import Path

from splitbrain.evaluation import load_dataset_v2

V3_DATASET = Path(__file__).resolve().parents[1] / "eval" / "dataset-v3.jsonl"


def test_dataset_v3_has_unique_ids_and_expected_label_counts() -> None:
    pairs = load_dataset_v2(V3_DATASET)

    assert len(pairs) == 60
    ids = [pair.id for pair in pairs]
    assert len(set(ids)) == 60
    assert ids == [f"w{number:03d}" for number in range(1, 61)]
    assert Counter(str(pair.label) for pair in pairs) == {
        "contradiction": 20,
        "update": 10,
        "compatible": 15,
        "unrelated": 15,
    }

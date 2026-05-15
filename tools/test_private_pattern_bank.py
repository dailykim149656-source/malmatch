#!/usr/bin/env python3
"""Focused tests for source-text-free private pattern bank generation."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from build_private_pattern_bank import build_private_pattern_bank


def write_inventory(root: Path, zip_path: Path) -> Path:
    inventory = {
        "schema_version": 1,
        "root": str(root),
        "policy": {"source_text_values": "omitted"},
        "files": [
            {
                "path": zip_path.relative_to(root).as_posix(),
                "dataset": "synthetic_aihub",
                "extension": ".zip",
                "split": "training",
                "data_role": "label",
            }
        ],
    }
    path = root / "inventory.json"
    path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return path


def write_multi_inventory(root: Path, records: list[tuple[Path, str]]) -> Path:
    inventory = {
        "schema_version": 1,
        "root": str(root),
        "policy": {"source_text_values": "omitted"},
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "dataset": dataset,
                "extension": ".zip",
                "split": "training",
                "data_role": "label",
            }
            for path, dataset in records
        ],
    }
    path = root / "inventory.json"
    path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return path


def test_private_pattern_bank_from_synthetic_zip() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        dataset_dir = root / "synthetic_aihub"
        dataset_dir.mkdir()
        zip_path = dataset_dir / "sample.zip"
        source_phrase = "보라색우산코드"
        payload = [
            {
                "topic": "고객 항의",
                "speaker_relation": "고객",
                "conversation": [
                    {
                        "utterance": f"고객님, 죄송합니다. {source_phrase} 확인해 보겠습니다.",
                        "speaker_emotion": "불만",
                    },
                    {
                        "utterance": f"환불은 안됩니다. {source_phrase}",
                        "listener_empathy": "없음",
                    },
                ],
            }
        ]
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("labels/sample.json", json.dumps(payload, ensure_ascii=False))

        inventory_path = write_inventory(root, zip_path)
        bank = build_private_pattern_bank(inventory_path, max_entries_per_zip=20)

    assert bank["schema"] == "private_pattern_bank"
    assert bank["policy"]["stored_text"] is False
    assert bank["coverage"]["utterance_count"] >= 2
    assert "customer_complaint" in bank["context_baselines"]
    assert bank["global_baselines"]["act_counts"]["apology"] >= 1
    assert bank["global_baselines"]["act_counts"]["refusal"] >= 1
    assert bank["speech_level_baselines"]["counts"]

    serialized = json.dumps(bank, ensure_ascii=False)
    assert source_phrase not in serialized
    assert "죄송합니다" not in serialized
    assert "환불은 안됩니다" not in serialized


def test_full_scan_and_balanced_baselines() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        dataset_a = root / "dataset_a"
        dataset_b = root / "dataset_b"
        dataset_a.mkdir()
        dataset_b.mkdir()
        zip_a = dataset_a / "sample.zip"
        zip_b = dataset_b / "sample.zip"
        source_phrase = "SOURCE_SECRET_DO_NOT_STORE"

        with zipfile.ZipFile(zip_a, "w") as archive:
            for index in range(9):
                archive.writestr(
                    f"a/{index}.json",
                    json.dumps({"utterance": f"short{index} {source_phrase}"}),
                )
        with zipfile.ZipFile(zip_b, "w") as archive:
            archive.writestr(
                "b/0.json",
                json.dumps({"utterance": "x" * 80 + source_phrase}),
            )

        inventory_path = write_multi_inventory(
            root, [(zip_a, "large_short_dataset"), (zip_b, "small_long_dataset")]
        )
        bank = build_private_pattern_bank(inventory_path, max_entries_per_zip=0)

    assert bank["coverage"]["full_entry_scan"] is True
    assert bank["coverage"]["entries_sampled"] == 10
    assert set(bank["dataset_profiles"]) == {"large_short_dataset", "small_long_dataset"}
    assert "raw_global_baselines" in bank
    assert "balanced_baselines" in bank
    assert bank["balanced_baselines"]["dataset_count"] == 2

    raw_short_rate = bank["raw_global_baselines"]["length_bucket_rates"].get("31-60", 0)
    balanced_short_rate = bank["balanced_baselines"]["global_baselines"][
        "length_bucket_rates"
    ].get("31-60", 0)
    assert raw_short_rate > balanced_short_rate
    assert balanced_short_rate == 0.5

    serialized = json.dumps(bank, ensure_ascii=False)
    assert source_phrase not in serialized


def main() -> int:
    test_private_pattern_bank_from_synthetic_zip()
    test_full_scan_and_balanced_baselines()
    print("Private pattern bank tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

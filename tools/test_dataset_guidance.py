#!/usr/bin/env python3
"""Focused tests for private pattern bank dataset guidance."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from dataset_guidance import build_dataset_guidance


def write_bank(path: Path) -> Path:
    raw_global = {"avg_chars": 24.0, "max_chars": 140}
    raw_contexts = {
        "customer_complaint": {
            "utterance_count": 40,
            "marker_rates": {"apology": 0.35, "polite_buffer": 0.45},
        },
        "formal_first_meeting": {
            "utterance_count": 30,
            "marker_rates": {"polite_buffer": 0.4},
        },
        "empathy_support": {
            "utterance_count": 30,
            "marker_rates": {"empathy": 0.5},
        },
    }
    bank = {
        "schema": "private_pattern_bank",
        "version": "0.1",
        "policy": {"stored_text": False, "source_text_values": "omitted"},
        "coverage": {"utterance_count": 100},
        "global_baselines": raw_global,
        "context_baselines": raw_contexts,
        "raw_global_baselines": raw_global,
        "raw_context_baselines": raw_contexts,
        "balanced_baselines": {
            "dataset_count": 2,
            "utterance_count_raw": 100,
            "global_baselines": {"avg_chars": 18.0, "max_chars": 120},
            "context_baselines": {
                "customer_complaint": {
                    "utterance_count": 40,
                    "dataset_count": 2,
                    "marker_rates": {"apology": 0.5, "polite_buffer": 0.6},
                },
                "formal_first_meeting": {
                    "utterance_count": 30,
                    "dataset_count": 2,
                    "marker_rates": {"polite_buffer": 0.55},
                },
                "empathy_support": {
                    "utterance_count": 30,
                    "dataset_count": 2,
                    "marker_rates": {"empathy": 0.65},
                },
            },
        },
    }
    path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    return path


def write_legacy_bank(path: Path) -> Path:
    bank = {
        "schema": "private_pattern_bank",
        "version": "0.1",
        "policy": {"stored_text": False, "source_text_values": "omitted"},
        "coverage": {"utterance_count": 100},
        "global_baselines": {"avg_chars": 24.0, "max_chars": 140},
        "context_baselines": {
            "customer_complaint": {
                "utterance_count": 40,
                "marker_rates": {"apology": 0.35, "polite_buffer": 0.45},
            },
            "formal_first_meeting": {
                "utterance_count": 30,
                "marker_rates": {"polite_buffer": 0.4},
            },
            "empathy_support": {
                "utterance_count": 30,
                "marker_rates": {"empathy": 0.5},
            },
        },
    }
    path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    return path


def signals(result: dict[str, object]) -> set[str]:
    return {str(item["signal"]) for item in result["guidance"]}  # type: ignore[index]


def guidance_item(result: dict[str, object], signal: str) -> dict[str, object]:
    for item in result["guidance"]:  # type: ignore[index]
        if item["signal"] == signal:
            return item
    raise AssertionError(f"missing signal {signal}")


def test_customer_complaint_refusal_guidance() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        bank_path = write_bank(Path(raw_tmp) / "bank.json")
        result = build_dataset_guidance(
            bank_path=bank_path,
            scene="고객이 환불 문제로 항의하는 상황",
            relationship_boundaries="초면, 공식, 고객",
            lines_to_review=["A: 안됩니다."],
        )

    assert result["bank_loaded"] is True
    assert result["requested_baseline_mode"] == "balanced"
    assert result["baseline_mode"] == "balanced"
    assert result["baseline_source"] == "balanced_baselines"
    assert "customer_complaint" in result["matched_contexts"]
    assert "customer_complaint_refusal" in signals(result)
    assert "customer_complaint_refusal" in result["signal_catalog"]
    item = guidance_item(result, "customer_complaint_refusal")
    assert item["basis"]["apology_rate"] == 0.5  # type: ignore[index]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "안됩니다" not in serialized


def test_raw_and_legacy_baseline_selection() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        bank_path = write_bank(tmp / "bank.json")
        raw = build_dataset_guidance(
            bank_path=bank_path,
            baseline_mode="raw",
            lines_to_review=["A: " + ("x" * 160)],
        )
        legacy_path = write_legacy_bank(tmp / "legacy.json")
        legacy = build_dataset_guidance(
            bank_path=legacy_path,
            lines_to_review=["A: " + ("x" * 160)],
        )

    raw_item = guidance_item(raw, "dialogue_density_outlier")
    assert raw["requested_baseline_mode"] == "raw"
    assert raw["baseline_mode"] == "raw"
    assert raw_item["basis"]["bank_avg_chars"] == 24.0  # type: ignore[index]
    assert legacy["requested_baseline_mode"] == "balanced"
    assert legacy["baseline_mode"] == "legacy_raw"
    assert legacy["baseline_source"] == "legacy_global_baselines"


def test_formal_and_empathy_guidance() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        bank_path = write_bank(Path(raw_tmp) / "bank.json")
        formal = build_dataset_guidance(
            bank_path=bank_path,
            scene="처음 만난 고객에게 요청하는 상황",
            relationship_boundaries="초면, 공식, 고객",
            lines_to_review=["A: 빨리 보내세요."],
        )
        empathy = build_dataset_guidance(
            bank_path=bank_path,
            scene="친구가 힘들다고 털어놓는 위로 장면",
            relationship_boundaries="친구",
            lines_to_review=["A: 그냥 참아야 해."],
        )

    assert "formal_request_directness" in signals(formal)
    assert "empathy_advice_timing" in signals(empathy)


def test_missing_corrupt_and_empty_bank_fallbacks() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        missing = build_dataset_guidance(
            bank_path=tmp / "missing.json",
            scene="고객 문의",
            lines_to_review=["A: 확인하겠습니다."],
        )
        corrupt_path = tmp / "corrupt.json"
        corrupt_path.write_text("{not json", encoding="utf-8")
        corrupt = build_dataset_guidance(
            bank_path=corrupt_path,
            scene="고객 문의",
            lines_to_review=["A: 확인하겠습니다."],
        )
        bank_path = write_bank(tmp / "bank.json")
        empty = build_dataset_guidance(bank_path=bank_path, lines_to_review="")

    assert missing["bank_loaded"] is False
    assert "bank_unavailable" in signals(missing)
    assert corrupt["bank_loaded"] is False
    assert "bank_unavailable" in signals(corrupt)
    assert empty["bank_loaded"] is True
    assert "empty_input" in signals(empty)


def main() -> int:
    test_customer_complaint_refusal_guidance()
    test_raw_and_legacy_baseline_selection()
    test_formal_and_empathy_guidance()
    test_missing_corrupt_and_empty_bank_fallbacks()
    print("Dataset guidance tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

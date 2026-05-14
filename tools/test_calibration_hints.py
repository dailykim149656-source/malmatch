#!/usr/bin/env python3
"""Focused tests for source-text-free calibration hints."""

from __future__ import annotations

import json
from pathlib import Path

from calibration_hints import build_calibration_hints


def test_mixed_speech_and_relationship_hints() -> None:
    lines = [
        "A: 고객님, 지금 처리하겠습니다.",
        "B: 야, 너 진짜 운명이야.",
        "C: 이 문제는 제가 다 해결해 드릴게요.",
    ]
    result = build_calibration_hints(
        lines,
        profile_path=Path("missing-profile.json"),
        scene="고객 응대 중 처음 만난 상황",
        relationship_boundaries="초면, 공식, 고객",
    )

    axes = {hint["axis"] for hint in result["hints"]}
    assert "speech_level_consistency" in axes
    assert "relationship_fit" in axes
    assert result["basis"]["stored_text"] is False
    assert result["basis"]["profile_source"] == "built_in_defaults"
    assert result["input_metrics"]["line_count"] == 3

    serialized = json.dumps(result, ensure_ascii=False)
    for source_fragment in ["고객님", "운명이야", "해결해 드릴게요"]:
        assert source_fragment not in serialized


def test_length_and_anachronism_hints() -> None:
    long_line = "A: " + "설명을 계속 이어 가는 문장입니다. " * 12
    result = build_calibration_hints(
        [long_line, "B: 카톡으로 보내면 되지."],
        profile_path=Path("missing-profile.json"),
        genre="조선 사극",
    )

    axes = {hint["axis"] for hint in result["hints"]}
    assert "naturalness" in axes
    assert "genre_fit" in axes
    assert "anachronism_risk" in axes
    assert result["input_metrics"]["max_chars"] > result["thresholds"]["hard_max_chars"]


def main() -> int:
    test_mixed_speech_and_relationship_hints()
    test_length_and_anachronism_hints()
    print("Calibration hint tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

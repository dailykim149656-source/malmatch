#!/usr/bin/env python3
"""Runtime dataset guidance from a local private pattern bank."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .calibration_hints import classify_speech_level, normalize_lines, strip_speaker_prefix
except ImportError:  # pragma: no cover - direct script execution
    from calibration_hints import classify_speech_level, normalize_lines, strip_speaker_prefix


VERSION = "0.1"

ACT_PATTERNS: dict[str, re.Pattern[str]] = {
    "question": re.compile(r"(\?|까요|나요|습니까|니[?!.…\s]*$|냐[?!.…\s]*$)"),
    "command": re.compile(r"(하세요|해라|기다려|보내세요|제출하세요|확인하세요|내놔|그만해)"),
    "request": re.compile(r"(부탁|주세요|주실 수|주시겠|가능하실까요|해 주|도와)"),
    "refusal": re.compile(r"(안\s*돼|안됩니다|못\s*해요|불가능|싫어요|거절)"),
    "apology": re.compile(r"(죄송|미안|사과|실례)"),
    "gratitude": re.compile(r"(감사|고맙)"),
    "empathy": re.compile(r"(속상|힘들|괜찮|이해|그랬구나|걱정|불안|슬프|화나)"),
    "advice": re.compile(r"(해야|해라|그냥|꼭|추천|좋겠|하지 마|참아|버텨)"),
    "overpromise": re.compile(r"(항상|절대|무조건|다 해결|내가 해결|평생|영원히)"),
    "polite_buffer": re.compile(
        r"(죄송|미안|실례|괜찮으시면|혹시|잠시|부탁|양해|감사|고맙|확인해\s*보|먼저|가능하실까요|주시겠|주실 수|드리)"
    ),
}

CONTEXT_PATTERNS: dict[str, re.Pattern[str]] = {
    "customer_complaint": re.compile(r"(고객|환불|민원|불만|항의|문의|상담|주문|고장|취소)"),
    "formal_first_meeting": re.compile(r"(초면|처음|공식|면접|고객|상사|거래처|교수|선생|사장|팀장|부장)"),
    "hierarchy": re.compile(r"(상사|선배|후배|교수|선생|팀장|부장|어른|연장자|군주|왕)"),
    "empathy_support": re.compile(r"(위로|힘들|속상|슬프|우울|걱정|불안|화나|감정|상처)"),
    "friends": re.compile(r"(친구|동료|친한|동급생)"),
    "family": re.compile(r"(가족|엄마|아빠|부모|동생|형|누나|언니|오빠)"),
    "conflict": re.compile(r"(갈등|싸움|다툼|화해|사과|잘못|배신)"),
    "refusal": re.compile(r"(거절|안\s*돼|안됩니다|불가능|못\s*해요)"),
    "request": re.compile(r"(부탁|요청|주세요|주시|가능하실까요)"),
}

SIGNAL_DESCRIPTIONS = {
    "customer_complaint_refusal": "고객 항의/거절 맥락에서 사과, 확인, 양해 표현이 부족한 후보",
    "formal_request_directness": "초면/공식 관계에서 요청이 지시처럼 들리는 후보",
    "empathy_advice_timing": "감정 반응보다 조언이나 해결책이 먼저 나온 후보",
    "speech_level_context_mismatch": "관계 맥락 대비 어체 전환 근거가 약한 후보",
    "dialogue_density_outlier": "비공개 패턴 뱅크 기준보다 한 턴 설명 밀도가 높은 후보",
    "bank_unavailable": "비공개 패턴 뱅크가 없어 데이터셋 기준을 적용하지 못한 상태",
    "empty_input": "검수할 대사가 비어 있어 데이터셋 기준 비교를 건너뛴 상태",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source-text-free dataset guidance.")
    parser.add_argument("--bank", type=Path, default=Path(".malmatch/private_pattern_bank.json"))
    parser.add_argument("--baseline-mode", choices=["balanced", "raw"], default="balanced")
    parser.add_argument("--scene", default="")
    parser.add_argument("--medium", default="")
    parser.add_argument("--genre", default="")
    parser.add_argument("--character-profiles", default="")
    parser.add_argument("--relationship-boundaries", default="")
    parser.add_argument("--lines", default="")
    return parser.parse_args()


def compact_confidence(value: float) -> float:
    return round(max(0.0, min(value, 0.99)), 2)


def detect_many(patterns: dict[str, re.Pattern[str]], text: str) -> set[str]:
    return {name for name, pattern in patterns.items() if pattern.search(text)}


def load_bank(bank_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not bank_path.exists():
        return None, ["private pattern bank not found"]
    try:
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"private pattern bank read error: {type(exc).__name__}"]
    if bank.get("schema") != "private_pattern_bank":
        return None, ["private pattern bank has unexpected schema"]
    return bank, []


def normalize_baseline_mode(mode: str) -> tuple[str, list[str]]:
    if mode in {"balanced", "raw"}:
        return mode, []
    return "balanced", [f"unsupported baseline_mode {mode!r}; using balanced"]


def select_baselines(
    bank: dict[str, Any] | None,
    requested_mode: str,
) -> dict[str, Any]:
    if bank is None:
        return {"mode": "none", "source": "not_loaded", "global": {}, "contexts": {}}

    raw_global = bank.get("raw_global_baselines") or bank.get("global_baselines", {})
    raw_contexts = bank.get("raw_context_baselines") or bank.get("context_baselines", {})
    if requested_mode == "balanced":
        balanced = bank.get("balanced_baselines", {})
        balanced_global = balanced.get("global_baselines")
        balanced_contexts = balanced.get("context_baselines")
        if isinstance(balanced_global, dict) and isinstance(balanced_contexts, dict):
            return {
                "mode": "balanced",
                "source": "balanced_baselines",
                "global": balanced_global,
                "contexts": balanced_contexts,
            }

    return {
        "mode": "raw" if "raw_global_baselines" in bank else "legacy_raw",
        "source": "raw_baselines" if "raw_global_baselines" in bank else "legacy_global_baselines",
        "global": raw_global if isinstance(raw_global, dict) else {},
        "contexts": raw_contexts if isinstance(raw_contexts, dict) else {},
    }


def build_input_metrics(lines_to_review: Any) -> dict[str, Any]:
    lines = normalize_lines(lines_to_review)
    stripped = [strip_speaker_prefix(line) for line in lines]
    lengths = [len(line) for line in stripped]
    speech_counts = Counter(classify_speech_level(line) for line in stripped)
    acts = Counter()
    for line in stripped:
        acts.update(detect_many(ACT_PATTERNS, line))
    return {
        "line_count": len(stripped),
        "total_chars": sum(lengths),
        "avg_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0.0,
        "max_chars": max(lengths) if lengths else 0,
        "speech_level_counts": dict(sorted(speech_counts.items())),
        "act_counts": dict(sorted(acts.items())),
    }


def match_contexts(
    *,
    scene: str = "",
    medium: str = "",
    genre: str = "",
    character_profiles: Any = "",
    relationship_boundaries: Any = "",
    lines_to_review: Any = "",
) -> list[str]:
    lines = " ".join(strip_speaker_prefix(line) for line in normalize_lines(lines_to_review))
    context_blob = " ".join(
        str(value)
        for value in [scene, medium, genre, character_profiles, relationship_boundaries, lines]
        if value
    )
    return sorted(detect_many(CONTEXT_PATTERNS, context_blob))


def marker_rate(context_baselines: dict[str, Any], context: str, marker: str) -> float:
    return float(
        context_baselines.get(context, {})
        .get("marker_rates", {})
        .get(marker, 0.0)
    )


def context_count(context_baselines: dict[str, Any], context: str) -> int:
    return int(
        context_baselines.get(context, {})
        .get("utterance_count", 0)
    )


def make_guidance(
    signal: str,
    axis: str,
    confidence: float,
    matched_contexts: list[str],
    rationale: str,
    *,
    basis: dict[str, Any],
    recommended_check: str,
) -> dict[str, Any]:
    return {
        "axis": axis,
        "signal": signal,
        "confidence": compact_confidence(confidence),
        "matched_contexts": matched_contexts,
        "basis": basis,
        "rationale": rationale,
        "recommended_check": recommended_check,
    }


def build_signal_catalog(guidance: list[dict[str, Any]]) -> dict[str, str]:
    return {
        item["signal"]: SIGNAL_DESCRIPTIONS[item["signal"]]
        for item in guidance
        if item.get("signal") in SIGNAL_DESCRIPTIONS
    }


def build_dataset_guidance(
    *,
    bank_path: Path,
    baseline_mode: str = "balanced",
    scene: str = "",
    medium: str = "",
    genre: str = "",
    character_profiles: Any = "",
    relationship_boundaries: Any = "",
    lines_to_review: Any = "",
) -> dict[str, Any]:
    requested_baseline_mode, mode_warnings = normalize_baseline_mode(baseline_mode)
    bank, warnings = load_bank(bank_path)
    warnings = [*mode_warnings, *warnings]
    selected_baseline = select_baselines(bank, requested_baseline_mode)
    global_baseline = selected_baseline["global"]
    context_baselines = selected_baseline["contexts"]
    baseline_basis = {
        "baseline_mode": selected_baseline["mode"],
        "baseline_source": selected_baseline["source"],
    }
    input_metrics = build_input_metrics(lines_to_review)
    matched_contexts = match_contexts(
        scene=scene,
        medium=medium,
        genre=genre,
        character_profiles=character_profiles,
        relationship_boundaries=relationship_boundaries,
        lines_to_review=lines_to_review,
    )
    acts = set(input_metrics["act_counts"])
    speech_levels = {
        level
        for level, count in input_metrics["speech_level_counts"].items()
        if count and level != "unknown"
    }
    guidance: list[dict[str, Any]] = []

    if input_metrics["line_count"] == 0:
        guidance.append(
            make_guidance(
                "empty_input",
                "genre_fit",
                0.99,
                [],
                "No dialogue lines were provided for dataset baseline comparison.",
                basis={"source": "input_validation", **baseline_basis},
                recommended_check="Provide lines_to_review before relying on dataset guidance.",
            )
        )
    elif bank is None:
        guidance.append(
            make_guidance(
                "bank_unavailable",
                "genre_fit",
                0.99,
                matched_contexts,
                "Private pattern bank is unavailable; run the local builder to enable dataset guidance.",
                basis={"source": "missing_private_pattern_bank", **baseline_basis},
                recommended_check="Run tools/build_private_pattern_bank.py after dataset_inventory.py.",
            )
        )
    else:
        if (
            "customer_complaint" in matched_contexts
            and "refusal" in acts
            and "apology" not in acts
            and "polite_buffer" not in acts
        ):
            guidance.append(
                make_guidance(
                    "customer_complaint_refusal",
                    "relationship_fit",
                    0.78,
                    matched_contexts,
                    "Input resembles a customer complaint/refusal context without apology or acknowledgement markers.",
                    basis={
                        "source": "private_pattern_bank",
                        **baseline_basis,
                        "context": "customer_complaint",
                        "utterance_count": context_count(context_baselines, "customer_complaint"),
                        "apology_rate": marker_rate(context_baselines, "customer_complaint", "apology"),
                        "polite_buffer_rate": marker_rate(context_baselines, "customer_complaint", "polite_buffer"),
                    },
                    recommended_check="Check whether apology, confirmation, or a softened explanation should precede refusal.",
                )
            )

        if (
            ("formal_first_meeting" in matched_contexts or "hierarchy" in matched_contexts)
            and ("command" in acts or "request" in acts)
            and "polite_buffer" not in acts
        ):
            context = "formal_first_meeting" if "formal_first_meeting" in matched_contexts else "hierarchy"
            guidance.append(
                make_guidance(
                    "formal_request_directness",
                    "relationship_fit",
                    0.7,
                    matched_contexts,
                    "Input contains request or command markers in a formal context without softening markers.",
                    basis={
                        "source": "private_pattern_bank",
                        **baseline_basis,
                        "context": context,
                        "utterance_count": context_count(context_baselines, context),
                        "polite_buffer_rate": marker_rate(context_baselines, context, "polite_buffer"),
                    },
                    recommended_check="Check whether the line needs a Korean politeness buffer such as apology, 혹시, 잠시, or 부탁.",
                )
            )

        if "empathy_support" in matched_contexts and "advice" in acts and "empathy" not in acts:
            guidance.append(
                make_guidance(
                    "empathy_advice_timing",
                    "relationship_fit",
                    0.66,
                    matched_contexts,
                    "Advice appears in an emotional-support context without empathy markers.",
                    basis={
                        "source": "private_pattern_bank",
                        **baseline_basis,
                        "context": "empathy_support",
                        "utterance_count": context_count(context_baselines, "empathy_support"),
                        "empathy_rate": marker_rate(context_baselines, "empathy_support", "empathy"),
                    },
                    recommended_check="Check whether emotional acknowledgement should come before advice.",
                )
            )

        if len(speech_levels) >= 2 and (
            "formal_first_meeting" in matched_contexts or "hierarchy" in matched_contexts
        ):
            guidance.append(
                make_guidance(
                    "speech_level_context_mismatch",
                    "speech_level_consistency",
                    0.64,
                    matched_contexts,
                    "Multiple speech levels appear in a context where relationship distance is likely important.",
                    basis={
                        "source": "private_pattern_bank",
                        **baseline_basis,
                        "observed_speech_levels": sorted(speech_levels),
                    },
                    recommended_check="Check whether the speech-level shift has a scene or relationship trigger.",
                )
            )

        bank_avg = float(global_baseline.get("avg_chars", 0.0) or 0.0)
        bank_max = int(global_baseline.get("max_chars", 0) or 0)
        density_threshold = max(80, int(bank_avg * 2.5), min(bank_max, 180))
        if input_metrics["max_chars"] > density_threshold:
            guidance.append(
                make_guidance(
                    "dialogue_density_outlier",
                    "naturalness",
                    0.62,
                    matched_contexts,
                    "One or more input turns are longer than the private-bank density baseline.",
                    basis={
                        "source": "private_pattern_bank",
                        **baseline_basis,
                        "bank_avg_chars": bank_avg,
                        "density_threshold": density_threshold,
                    },
                    recommended_check="Check whether the line should be split, shortened, or moved to narration.",
                )
            )

    return {
        "schema": "dataset_guidance",
        "version": VERSION,
        "bank_loaded": bank is not None,
        "bank_source": "local_private_pattern_bank" if bank is not None else "not_loaded",
        "requested_baseline_mode": requested_baseline_mode,
        "baseline_mode": selected_baseline["mode"],
        "baseline_source": selected_baseline["source"],
        "matched_contexts": matched_contexts,
        "input_metrics": input_metrics,
        "guidance": guidance,
        "signal_catalog": build_signal_catalog(guidance),
        "source_basis": ["private_pattern_bank"] if bank is not None else [],
        "source_text_values": "omitted",
        "quality_warnings": warnings,
    }


def main() -> int:
    args = parse_args()
    result = build_dataset_guidance(
        bank_path=args.bank,
        baseline_mode=args.baseline_mode,
        scene=args.scene,
        medium=args.medium,
        genre=args.genre,
        character_profiles=args.character_profiles,
        relationship_boundaries=args.relationship_boundaries,
        lines_to_review=args.lines,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

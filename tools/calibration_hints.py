#!/usr/bin/env python3
"""Rule-based calibration hints for Korean character dialogue audits.

The module only returns aggregate signals and line indexes. It never stores or
returns the user's dialogue text.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


VERSION = "0.2.1"

DEFAULT_THRESHOLDS = {
    "soft_max_chars": 60,
    "hard_max_chars": 120,
    "target_scene_min_turns": 6,
    "target_scene_max_turns": 20,
}

SPEECH_LEVELS = ("banmal", "haeyo", "hapsyo", "unknown")

HAPSYO_RE = re.compile(r"(습니다|습니까|십시오|입니다|입니까|ㅂ니다)[.!?…]*$")
HAEYO_RE = re.compile(r"(요|예요|이에요|해요|네요|군요|죠|까요|나요)[.!?…]*$")
BANMAL_RE = re.compile(r"(어|아|야|지|니|냐|네|군|자|마|거든|잖아|다)[.!?…]*$")
SPEAKER_PREFIX_RE = re.compile(r"^\s*[^:\n]{1,20}:\s*")

ADVICE_RE = re.compile(r"(해야|해라|하지 마|그냥|당장|무조건|꼭|잊어|참아|버텨)")
OVERPROMISE_RE = re.compile(r"(항상|영원히|절대|무조건|다 해결|내가 해결|평생)")
INTIMACY_RE = re.compile(r"(사랑|좋아해|내 사람|운명|평생|안아|키스)")
CRINGE_RE = re.compile(r"(내 매력|나는 원래|심장이|영혼|세상에서 제일|운명처럼)")
HUMOR_RE = re.compile(r"(ㅋㅋ|ㅎㅎ|농담|드립|개그|웃기)")
SERIOUS_SCENE_RE = re.compile(r"(장례|사망|죽|위험|피|울|실패|부상|이별|배신)")
MODERN_TERM_RE = re.compile(r"(카톡|디엠|DM|인스타|밈|구독|알고리즘|업로드|스마트폰|셀카)")
OLD_WORLD_RE = re.compile(r"(사극|조선|고려|중세|고대|왕국|궁궐|무협|판타지)")
FORMAL_RELATION_RE = re.compile(
    r"(초면|상사|고객|공식|면접|선배|스승|군주|왕|어른|연장자|교수|선생|거래처|민원|환자|보호자|사장|팀장|부장)"
)
INFORMAL_ADDRESS_RE = re.compile(r"(야|너|니가|네가|자기야)")
INTENTIONAL_SHIFT_RE = re.compile(r"(반존대|전환|일부러|의도|거리|친해|무너)")
POLITENESS_EVENT_RE = re.compile(r"(실수|늦|지각|사과|불만|항의|환불|민원|거절|부탁|요청|고객|고장|문제|취소)")
POLITE_BUFFER_RE = re.compile(
    r"(죄송|미안|실례|괜찮으시면|혹시|잠시|부탁|양해|감사|고맙|확인해\s*보|확인해보|확인하겠|확인드리|확인해\s*드리|먼저|가능하실까요|주시겠|주실 수|드리|도와)"
)
DIRECT_COMMAND_RE = re.compile(
    r"(?:빨리\s*|당장\s*|그냥\s*)?(해|와|가|앉아|기다려|말해|내놔|줘|보내|나가|들어와|그만해|조용히 해)[.!?…]*$"
)
BLUNT_REFUSAL_RE = re.compile(r"(안\s*돼|안됩니다|못\s*해요|불가능|그건\s*안|싫어요|몰라요|제가\s*왜|어쩌라고)")
UNSOFTENED_POLITE_REQUEST_RE = re.compile(
    r"(?:빨리\s*|당장\s*|그냥\s*)?.{0,16}(하세요|해요|말하세요|기다리세요|보내세요|제출하세요|확인하세요)[.!?…]*$"
)

SIGNAL_DESCRIPTIONS = {
    "very_long_utterance": "대사 길이가 기준보다 긴 후보",
    "exposition_density_risk": "설명 밀도 과다 후보",
    "medium_density_risk": "매체 호흡에 비해 대사가 긴 후보",
    "long_utterance_cluster": "긴 대사가 몰린 후보",
    "mixed_speech_levels_without_context_trigger": "맥락 근거 없는 어체 혼합 후보",
    "overfamiliar_address_in_formal_context": "공식/거리 있는 관계에서 과하게 친근한 호칭 후보",
    "direct_command_in_polite_context": "예의가 필요한 관계에서 완충 없는 직접 명령 후보",
    "unsoftened_request_in_polite_context": "정중해야 하는 관계에서 양해/부탁 없이 지시처럼 들리는 요청 후보",
    "blunt_refusal_without_buffer": "거절·불만 상황에서 사과나 설명 없이 직설적으로 끊는 후보",
    "missing_apology_or_acknowledgement_in_service_context": "고객·민원·실수 맥락에서 사과/양해/확인 표현이 부족한 후보",
    "advice_overload": "조언 과다 후보",
    "overpromise_risk": "과한 약속 후보",
    "intimacy_jump": "관계에 비해 친밀 표현이 급격한 후보",
    "self_explanation_or_melodrama": "자기 설명 또는 과한 감정 강조 후보",
    "humor_in_serious_scene": "무거운 장면에서 농담 타이밍 위험 후보",
    "modern_term_in_old_world_context": "시대/세계관에 맞지 않는 현대어 후보",
    "large_scene_packet": "짧은 장면 검수 기준보다 입력 턴이 많은 후보",
}


def strip_speaker_prefix(line: str) -> str:
    return SPEAKER_PREFIX_RE.sub("", line).strip()


def normalize_lines(lines: Any) -> list[str]:
    if isinstance(lines, str):
        return [line.strip() for line in lines.splitlines() if line.strip()]
    if not isinstance(lines, list):
        return []

    normalized: list[str] = []
    for item in lines:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("line") or item.get("text") or item.get("content") or "").strip()
        else:
            text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def classify_speech_level(line: str) -> str:
    cleaned = strip_speaker_prefix(line)
    if HAPSYO_RE.search(cleaned):
        return "hapsyo"
    if HAEYO_RE.search(cleaned):
        return "haeyo"
    if BANMAL_RE.search(cleaned) or INFORMAL_ADDRESS_RE.search(cleaned):
        return "banmal"
    return "unknown"


def load_thresholds(profile_path: Path | None) -> dict[str, Any]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    thresholds["profile_loaded"] = False
    thresholds["profile_source"] = "built_in_defaults"

    if not profile_path or not profile_path.exists():
        return thresholds

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return thresholds

    length_buckets: Counter[str] = Counter()
    turn_buckets: Counter[str] = Counter()
    for dataset in profile.get("datasets", {}).values():
        length_buckets.update(dataset.get("utterance_length_buckets", {}))
        turn_buckets.update(dataset.get("turn_count_buckets", {}))

    total_lengths = sum(length_buckets.values())
    if total_lengths:
        short_or_mid = (
            length_buckets.get("0-10", 0)
            + length_buckets.get("11-30", 0)
            + length_buckets.get("31-60", 0)
        )
        if short_or_mid / total_lengths < 0.6:
            thresholds["soft_max_chars"] = 80
        thresholds["profile_loaded"] = True
        thresholds["profile_source"] = "local_pattern_profile"

    if turn_buckets:
        thresholds["target_scene_min_turns"] = 6
        thresholds["target_scene_max_turns"] = 20
        thresholds["profile_loaded"] = True
        thresholds["profile_source"] = "local_pattern_profile"

    return thresholds


def compact_confidence(value: float) -> float:
    return round(max(0.0, min(value, 0.99)), 2)


def make_hint(
    axis: str,
    hint: int,
    confidence: float,
    signals: list[str],
    line_refs: list[int],
    rationale: str,
) -> dict[str, Any]:
    return {
        "axis": axis,
        "hint": hint,
        "confidence": compact_confidence(confidence),
        "signals": sorted(set(signals)),
        "line_refs": sorted(set(line_refs)),
        "rationale": rationale,
    }


def build_signal_catalog(hints: list[dict[str, Any]]) -> dict[str, str]:
    signals: set[str] = set()
    for hint in hints:
        signals.update(str(signal) for signal in hint.get("signals", []))
    return {
        signal: SIGNAL_DESCRIPTIONS[signal]
        for signal in sorted(signals)
        if signal in SIGNAL_DESCRIPTIONS
    }


def context_has(pattern: re.Pattern[str], *values: Any) -> bool:
    joined = " ".join(str(value) for value in values if value)
    return bool(pattern.search(joined))


def build_calibration_hints(
    lines_to_review: Any,
    *,
    profile_path: Path | None = None,
    scene: str = "",
    medium: str = "",
    genre: str = "",
    character_profiles: Any = "",
    relationship_boundaries: Any = "",
) -> dict[str, Any]:
    """Build soft calibration hints without returning source dialogue text."""

    lines = normalize_lines(lines_to_review)
    thresholds = load_thresholds(profile_path)
    stripped = [strip_speaker_prefix(line) for line in lines]
    lengths = [len(line) for line in stripped]
    line_count = len(lines)
    total_chars = sum(lengths)
    avg_chars = round(total_chars / line_count, 1) if line_count else 0.0
    max_chars = max(lengths) if lengths else 0
    speech_counts = Counter(classify_speech_level(line) for line in lines)
    context = " ".join(
        str(value)
        for value in [scene, medium, genre, character_profiles, relationship_boundaries]
        if value
    )

    hints: list[dict[str, Any]] = []
    soft_max = int(thresholds["soft_max_chars"])
    hard_max = int(thresholds["hard_max_chars"])

    long_refs = [index for index, length in enumerate(lengths, 1) if length > soft_max]
    very_long_refs = [index for index, length in enumerate(lengths, 1) if length > hard_max]
    if very_long_refs:
        hints.append(
            make_hint(
                "naturalness",
                -1,
                0.82,
                ["very_long_utterance", "exposition_density_risk"],
                very_long_refs,
                "One or more lines are far above the local length baseline.",
            )
        )
        hints.append(
            make_hint(
                "genre_fit",
                -1,
                0.74,
                ["medium_density_risk"],
                very_long_refs,
                "Long lines may be hard to fit into compact dialogue media.",
            )
        )
    elif long_refs and avg_chars > soft_max:
        hints.append(
            make_hint(
                "naturalness",
                -1,
                0.68,
                ["long_utterance_cluster"],
                long_refs,
                "Several lines are above the local length baseline.",
            )
        )

    known_speech_levels = [
        level for level in ("banmal", "haeyo", "hapsyo") if speech_counts.get(level, 0)
    ]
    intentional_shift = context_has(INTENTIONAL_SHIFT_RE, context)
    if len(known_speech_levels) >= 2 and not intentional_shift:
        mixed_refs = [
            index
            for index, line in enumerate(lines, 1)
            if classify_speech_level(line) in known_speech_levels
        ]
        hints.append(
            make_hint(
                "speech_level_consistency",
                -1,
                0.8,
                ["mixed_speech_levels_without_context_trigger"],
                mixed_refs,
                "Multiple speech levels appear without an explicit relationship or scene trigger.",
            )
        )

    formal_context = context_has(FORMAL_RELATION_RE, context)
    informal_refs = [
        index for index, line in enumerate(stripped, 1) if INFORMAL_ADDRESS_RE.search(line)
    ]
    if formal_context and informal_refs:
        hints.append(
            make_hint(
                "relationship_fit",
                -1,
                0.76,
                ["overfamiliar_address_in_formal_context"],
                informal_refs,
                "Informal address appears in a formal or distant relationship context.",
            )
        )

    politeness_event_context = context_has(POLITENESS_EVENT_RE, context)
    buffered_refs = [
        index for index, line in enumerate(stripped, 1) if POLITE_BUFFER_RE.search(line)
    ]
    direct_command_refs = [
        index
        for index, line in enumerate(stripped, 1)
        if formal_context and DIRECT_COMMAND_RE.search(line) and not POLITE_BUFFER_RE.search(line)
    ]
    if direct_command_refs:
        hints.append(
            make_hint(
                "relationship_fit",
                -1,
                0.78,
                ["direct_command_in_polite_context"],
                direct_command_refs,
                "Direct commands appear in a context that usually requires Korean politeness buffers.",
            )
        )

    unsoftened_request_refs = [
        index
        for index, line in enumerate(stripped, 1)
        if formal_context
        and UNSOFTENED_POLITE_REQUEST_RE.search(line)
        and not POLITE_BUFFER_RE.search(line)
    ]
    if unsoftened_request_refs:
        hints.append(
            make_hint(
                "relationship_fit",
                -1,
                0.68,
                ["unsoftened_request_in_polite_context"],
                unsoftened_request_refs,
                "Requests may sound like bare instructions without apology, acknowledgement, or softening.",
            )
        )

    blunt_refusal_refs = [
        index
        for index, line in enumerate(stripped, 1)
        if politeness_event_context
        and BLUNT_REFUSAL_RE.search(line)
        and not POLITE_BUFFER_RE.search(line)
    ]
    if blunt_refusal_refs:
        hints.append(
            make_hint(
                "relationship_fit",
                -1,
                0.73,
                ["blunt_refusal_without_buffer"],
                blunt_refusal_refs,
                "Refusal or denial appears without a Korean-style apology, acknowledgement, or explanation buffer.",
            )
        )

    if formal_context and politeness_event_context and line_count and not buffered_refs:
        hints.append(
            make_hint(
                "relationship_fit",
                -1,
                0.58,
                ["missing_apology_or_acknowledgement_in_service_context"],
                [],
                "The context suggests apology, acknowledgement, or confirmation before the main request or refusal.",
            )
        )

    advice_refs = [index for index, line in enumerate(stripped, 1) if ADVICE_RE.search(line)]
    overpromise_refs = [
        index for index, line in enumerate(stripped, 1) if OVERPROMISE_RE.search(line)
    ]
    if advice_refs and overpromise_refs:
        hints.append(
            make_hint(
                "relationship_fit",
                -1,
                0.7,
                ["advice_overload", "overpromise_risk"],
                advice_refs + overpromise_refs,
                "Advice and strong promises appear together; check empathy and relationship boundaries.",
            )
        )

    intimacy_refs = [index for index, line in enumerate(stripped, 1) if INTIMACY_RE.search(line)]
    if formal_context and intimacy_refs:
        hints.append(
            make_hint(
                "relationship_fit",
                -1,
                0.72,
                ["intimacy_jump"],
                intimacy_refs,
                "High-intimacy wording appears in a formal or distant context.",
            )
        )

    cringe_refs = [index for index, line in enumerate(stripped, 1) if CRINGE_RE.search(line)]
    if cringe_refs:
        hints.append(
            make_hint(
                "cringe_risk",
                -1,
                0.67,
                ["self_explanation_or_melodrama"],
                cringe_refs,
                "The line pattern resembles self-explanation or melodramatic emphasis.",
            )
        )

    humor_refs = [index for index, line in enumerate(stripped, 1) if HUMOR_RE.search(line)]
    serious_context = context_has(SERIOUS_SCENE_RE, context)
    if humor_refs and serious_context:
        hints.append(
            make_hint(
                "humor_timing",
                -1,
                0.73,
                ["humor_in_serious_scene"],
                humor_refs,
                "Humor markers appear in a serious scene context.",
            )
        )

    modern_refs = [index for index, line in enumerate(stripped, 1) if MODERN_TERM_RE.search(line)]
    old_world_context = context_has(OLD_WORLD_RE, context)
    if modern_refs and old_world_context:
        hints.append(
            make_hint(
                "anachronism_risk",
                -1,
                0.78,
                ["modern_term_in_old_world_context"],
                modern_refs,
                "Modern platform or device terms appear in an old-world genre context.",
            )
        )

    if line_count > int(thresholds["target_scene_max_turns"]):
        hints.append(
            make_hint(
                "genre_fit",
                -1,
                0.56,
                ["large_scene_packet"],
                [],
                "The submitted packet is larger than the default short-scene audit window.",
            )
        )

    return {
        "schema": "calibration_hints",
        "version": VERSION,
        "basis": {
            "profile_loaded": bool(thresholds["profile_loaded"]),
            "profile_source": thresholds["profile_source"],
            "stored_text": False,
            "source_text_values": "omitted",
        },
        "thresholds": {
            "soft_max_chars": thresholds["soft_max_chars"],
            "hard_max_chars": thresholds["hard_max_chars"],
            "target_scene_min_turns": thresholds["target_scene_min_turns"],
            "target_scene_max_turns": thresholds["target_scene_max_turns"],
        },
        "input_metrics": {
            "line_count": line_count,
            "total_chars": total_chars,
            "avg_chars": avg_chars,
            "max_chars": max_chars,
            "speech_level_counts": {level: speech_counts.get(level, 0) for level in SPEECH_LEVELS},
        },
        "hints": hints,
        "signal_catalog": build_signal_catalog(hints),
        "note": "Hints are soft calibration signals. They are not final scores.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source-text-free calibration hints.")
    parser.add_argument("--lines", help="Dialogue lines to inspect. Newlines are treated as turns.")
    parser.add_argument("--scene", default="")
    parser.add_argument("--medium", default="")
    parser.add_argument("--genre", default="")
    parser.add_argument("--profile", type=Path, default=Path(".omx/pattern_profile.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hints = build_calibration_hints(
        args.lines or "",
        profile_path=args.profile,
        scene=args.scene,
        medium=args.medium,
        genre=args.genre,
    )
    print(json.dumps(hints, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

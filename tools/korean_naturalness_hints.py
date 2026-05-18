#!/usr/bin/env python3
"""Korean grammar, idiom, and spoken-rhythm hints for Malmatch.

The module returns only aggregate metrics, signal labels, suggestion categories,
and line indexes. It does not store or return the user's dialogue text.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

try:
    from .calibration_hints import normalize_lines, strip_speaker_prefix
    from .text_metrics import build_text_metrics
except ImportError:  # pragma: no cover - direct script execution
    from calibration_hints import normalize_lines, strip_speaker_prefix
    from text_metrics import build_text_metrics


VERSION = "0.4.0"

AXES = (
    "grammar_acceptability",
    "native_korean_idiom",
    "spoken_korean_rhythm",
)

DUPLICATE_PARTICLE_RE = re.compile(
    r"(?<=[가-힣])(?:은는|는은|을를|를을|가가|이이|에에|도도|만만|에서에서|에게에게)(?=$|\s|[,.!?…])"
)
DUPLICATE_CONNECTIVE_RE = re.compile(r"(그리고\s+그리고|하지만\s+하지만|그래서\s+그래서)")
ENDING_COLLISION_RE = re.compile(
    r"(?:습니다|습니까|세요|요).{0,20}(?:야|냐|니|잖아|거든|해라)[.!?…]*$|"
    r"(?:야|냐|니|잖아|거든).{0,20}(?:습니다|습니까|세요|요)[.!?…]*$"
)
NONSTANDARD_POLITE_ENDING_RE = re.compile(
    r"(습니다요|습니까요|했어요요|해요요|하자요|보자요|먹자요|만나자요|그만하자요)[.!?…]*$"
)

GRAMMAR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("doe_dwae_confusion", re.compile(r"(되요|됬|됄|안되(?:요|나요|네|는|면|겠|다|고|지|잖|어서|어|니|나|게|$))")),
    ("eotteokhae_misspelling", re.compile(r"(어떻해|어떡게|어떻게해)")),
    ("anieyo_misspelling", re.compile(r"(아니예요|아녜요)")),
    ("myeochil_misspelling", re.compile(r"몇일")),
    ("halge_misspelling", re.compile(r"(할께|갈께|볼께|줄께|먹을께|해줄께)")),
    ("oraenman_misspelling", re.compile(r"오랫만")),
    ("geumse_misspelling", re.compile(r"금새")),
    ("intent_l_euryeogo", re.compile(r"(할려고|갈려고|볼려고|먹을려고|오려고|만날려고|줄려고|하려고자)")),
    ("bound_noun_spacing", re.compile(r"(수있|수없|것같|거같|줄알|줄모르)")),
    ("nonstandard_hante_spelling", re.compile(r"(한태|나한데|너한데|친구한데|엄마한데|아빠한데)")),
    ("waen_wen_confusion", re.compile(r"웬지|왠\s*(?:일|말|사람|것|곳|쪽|경우|상황|소리)")),
    ("an_dwae_spacing", re.compile(r"안되(?:요|나요|네|는|면|겠|다|고|지|잖|어서|어|니|나|게|$)")),
    ("mot_spacing_suspect", re.compile(r"못(?:해|하|되|가|오|먹|보|읽|찾|참|자|들)")),
    ("bound_noun_spacing_expanded", re.compile(r"(?:것|거)같|수(?:있|없)|줄(?:알|모르)")),
    ("auxiliary_spacing_suspect", re.compile(r"(?:하고|되어|돼|가고|오고|보고|먹고|살고|읽고|찾고)있")),
    ("honorific_ending_collision", ENDING_COLLISION_RE),
)

TRANSLATIONESE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("explicit_i_think", re.compile(r"(나는|저는|제가|내가).{0,24}(생각한다|생각해요|생각합니다|생각해)")),
    ("thing_pronoun_overuse", re.compile(r"(그것은|이것은|저것은|그건|이건|저건).{0,24}(이다|입니다|이에요|예요)")),
    ("want_to_do_literalism", re.compile(r"하는\s+것을\s+(원해|원합니다|바라|바랍니다)")),
    ("make_decision_literalism", re.compile(r"결정을\s+만들")),
    ("have_problem_literalism", re.compile(r"문제를\s+가지고\s+있")),
    ("tell_me_literalism", re.compile(r"(나에게|저에게|너에게)\s+말해")),
    ("good_time_literalism", re.compile(r"좋은\s+시간을\s+보내")),
)

WRITTEN_ENDING_RE = re.compile(
    r"(것이다|것입니다|것으로 보인다|라고 생각한다|라고 판단된다|라고 할 수 있다)[.!?…]*$"
)
REACTION_RE = re.compile(r"^(응|어|아|그래|맞아|아니|헐|뭐|진짜|괜찮아|그렇지)[.!?…]*$")
PRONOUN_RE = re.compile(r"(나는|저는|제가|내가|나를|저를|너는|너를|당신은|당신을)")

SIGNAL_DESCRIPTIONS = {
    "duplicate_particle_sequence": "조사 중복 또는 어색한 조사 연쇄 후보",
    "duplicate_connective": "연결어 반복 후보",
    "sentence_ending_collision": "높임 종결과 반말 종결이 한 문장 안에서 충돌하는 후보",
    "nonstandard_polite_ending": "비표준 높임 종결 후보",
    "doe_dwae_confusion": "되/돼 계열 표기 오류 후보",
    "eotteokhae_misspelling": "어떻게/어떡해 계열 표기 오류 후보",
    "anieyo_misspelling": "아니에요 계열 표기 오류 후보",
    "myeochil_misspelling": "며칠 계열 표기 오류 후보",
    "halge_misspelling": "할게 계열 표기 오류 후보",
    "oraenman_misspelling": "오랜만 계열 표기 오류 후보",
    "geumse_misspelling": "금세 계열 표기 오류 후보",
    "intent_l_euryeogo": "의도 표현의 -려고 결합 오류 후보",
    "bound_noun_spacing": "의존 명사 띄어쓰기 오류 후보",
    "nonstandard_hante_spelling": "한테/한데 혼동 후보",
    "waen_wen_confusion": "왠/웬 계열 표기 혼동 후보",
    "an_dwae_spacing": "안 되다 계열 띄어쓰기 또는 되/돼 표기 점검 후보",
    "mot_spacing_suspect": "못 계열 부정 표현의 보조 용언 띄어쓰기 점검 후보",
    "bound_noun_spacing_expanded": "의존 명사 계열 띄어쓰기 점검 후보",
    "auxiliary_spacing_suspect": "하고 있다/되어 있다 계열 보조 용언 띄어쓰기 점검 후보",
    "honorific_ending_collision": "한 턴 안에서 높임 종결과 반말 종결이 충돌하는 후보",
    "explicit_i_think": "한국어 대화에서 명시 주어와 생각하다 구문이 과하게 붙은 후보",
    "thing_pronoun_overuse": "그것/이것/저것 직역투 후보",
    "want_to_do_literalism": "영어식 want to 직역 후보",
    "make_decision_literalism": "영어식 make a decision 직역 후보",
    "have_problem_literalism": "영어식 have a problem 직역 후보",
    "tell_me_literalism": "영어식 tell me 직역 후보",
    "good_time_literalism": "영어식 have a good time 직역 후보",
    "written_register_cluster": "대화보다 문어체 문장에 가까운 말투 후보",
    "missing_short_reaction_turns": "짧은 반응 턴 부족 후보",
    "explicit_pronoun_overuse": "명시 주어/대명사 과다 후보",
}

SUGGESTION_CATALOG = {
    "doe_dwae_confusion": {
        "suggestion_type": "spelling_review",
        "rationale": "되/돼 활용과 종결 어미 결합을 다시 확인합니다.",
    },
    "eotteokhae_misspelling": {
        "suggestion_type": "spelling_review",
        "rationale": "어떻게/어떡해 계열의 의미와 표기를 구분합니다.",
    },
    "anieyo_misspelling": {
        "suggestion_type": "spelling_review",
        "rationale": "아니에요 계열 표기를 확인합니다.",
    },
    "myeochil_misspelling": {
        "suggestion_type": "spelling_review",
        "rationale": "며칠 계열 표기를 확인합니다.",
    },
    "halge_misspelling": {
        "suggestion_type": "spelling_review",
        "rationale": "약속/의지 종결 표현의 표기를 확인합니다.",
    },
    "waen_wen_confusion": {
        "suggestion_type": "spelling_review",
        "rationale": "부사와 관형사 쓰임에 따라 왠/웬을 구분합니다.",
    },
    "an_dwae_spacing": {
        "suggestion_type": "spacing_review",
        "rationale": "부정 부사와 용언 결합의 띄어쓰기 및 되/돼 활용을 확인합니다.",
    },
    "mot_spacing_suspect": {
        "suggestion_type": "spacing_review",
        "rationale": "능력 부정인지 굳어진 합성어인지에 따라 띄어쓰기 후보를 점검합니다.",
    },
    "bound_noun_spacing": {
        "suggestion_type": "spacing_review",
        "rationale": "의존 명사는 앞말과 띄는 것이 기본입니다.",
    },
    "bound_noun_spacing_expanded": {
        "suggestion_type": "spacing_review",
        "rationale": "것, 거, 수, 줄 계열 의존 명사 결합을 점검합니다.",
    },
    "auxiliary_spacing_suspect": {
        "suggestion_type": "spacing_review",
        "rationale": "보조 용언 결합은 붙임 허용 여부와 문맥을 함께 확인합니다.",
    },
    "honorific_ending_collision": {
        "suggestion_type": "speech_level_review",
        "rationale": "한 턴 안의 종결 어미 높임 단계가 의도적으로 전환된 것인지 확인합니다.",
    },
}


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


def collect_signals(hints: list[dict[str, Any]]) -> set[str]:
    signals: set[str] = set()
    for hint in hints:
        signals.update(str(signal) for signal in hint.get("signals", []))
    return signals


def build_signal_catalog(hints: list[dict[str, Any]]) -> dict[str, str]:
    return {
        signal: SIGNAL_DESCRIPTIONS[signal]
        for signal in sorted(collect_signals(hints))
        if signal in SIGNAL_DESCRIPTIONS
    }


def build_suggestion_catalog(hints: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    return {
        signal: SUGGESTION_CATALOG[signal]
        for signal in sorted(collect_signals(hints))
        if signal in SUGGESTION_CATALOG
    }


def build_korean_naturalness_hints(lines_to_review: Any) -> dict[str, Any]:
    lines = normalize_lines(lines_to_review)
    stripped = [strip_speaker_prefix(line) for line in lines]
    text_metrics = build_text_metrics(stripped, strip_speakers=False)
    line_count = text_metrics["line_count"]
    lengths = [item["nfc_chars"] for item in text_metrics["per_line"]]

    hints: list[dict[str, Any]] = []
    grammar_refs: list[int] = []
    grammar_signals: list[str] = []
    idiom_refs: list[int] = []
    idiom_signals: list[str] = []

    written_refs: list[int] = []
    short_reaction_refs: list[int] = []
    pronoun_refs: list[int] = []
    pronoun_count = 0

    for index, line in enumerate(stripped, 1):
        if DUPLICATE_PARTICLE_RE.search(line):
            grammar_refs.append(index)
            grammar_signals.append("duplicate_particle_sequence")
        if DUPLICATE_CONNECTIVE_RE.search(line):
            grammar_refs.append(index)
            grammar_signals.append("duplicate_connective")
        if ENDING_COLLISION_RE.search(line):
            grammar_refs.append(index)
            grammar_signals.append("sentence_ending_collision")
        if NONSTANDARD_POLITE_ENDING_RE.search(line):
            grammar_refs.append(index)
            grammar_signals.append("nonstandard_polite_ending")

        for signal, pattern in GRAMMAR_PATTERNS:
            if pattern.search(line):
                grammar_refs.append(index)
                grammar_signals.append(signal)

        for signal, pattern in TRANSLATIONESE_PATTERNS:
            if pattern.search(line):
                idiom_refs.append(index)
                idiom_signals.append(signal)

        if WRITTEN_ENDING_RE.search(line):
            written_refs.append(index)
        if lengths[index - 1] <= 8 and REACTION_RE.search(line):
            short_reaction_refs.append(index)

        line_pronoun_count = len(PRONOUN_RE.findall(line))
        if line_pronoun_count:
            pronoun_count += line_pronoun_count
            pronoun_refs.append(index)

    if grammar_refs:
        hints.append(
            make_hint(
                "grammar_acceptability",
                -1,
                0.76,
                grammar_signals,
                grammar_refs,
                "Possible grammar, spelling, spacing, particle, or sentence-ending acceptability issue.",
            )
        )

    if idiom_refs:
        hints.append(
            make_hint(
                "native_korean_idiom",
                -1,
                0.72,
                idiom_signals,
                idiom_refs,
                "Possible translationese or non-native Korean collocation pattern.",
            )
        )

    if line_count >= 4:
        written_ratio = len(written_refs) / line_count
        if written_ratio >= 0.75:
            hints.append(
                make_hint(
                    "spoken_korean_rhythm",
                    -1,
                    0.67,
                    ["written_register_cluster"],
                    written_refs,
                    "Most turns look like complete written sentences rather than spoken dialogue.",
                )
            )
        if not short_reaction_refs and min(lengths or [0]) > 12:
            hints.append(
                make_hint(
                    "spoken_korean_rhythm",
                    -1,
                    0.61,
                    ["missing_short_reaction_turns"],
                    [],
                    "The scene has no short reaction turns, which can flatten spoken Korean rhythm.",
                )
            )

    if line_count and pronoun_count / max(line_count, 1) >= 1.5:
        hints.append(
            make_hint(
                "native_korean_idiom",
                -1,
                0.6,
                ["explicit_pronoun_overuse"],
                pronoun_refs,
                "Frequent explicit pronouns may sound translated or over-specified in Korean dialogue.",
            )
        )

    return {
        "schema": "korean_naturalness_hints",
        "version": VERSION,
        "basis": {
            "stored_text": False,
            "source_text_values": "omitted",
            "rule_source": "built_in_korean_dialogue_patterns",
        },
        "input_metrics": {
            "line_count": line_count,
            "total_chars": text_metrics["total_nfc_chars"],
            "avg_chars": text_metrics["avg_nfc_chars"],
            "max_chars": text_metrics["max_nfc_chars"],
            "text_metrics": text_metrics,
            "short_reaction_count": len(short_reaction_refs),
            "written_sentence_count": len(written_refs),
            "explicit_pronoun_count": pronoun_count,
        },
        "axes": list(AXES),
        "hints": hints,
        "signal_catalog": build_signal_catalog(hints),
        "suggestion_catalog": build_suggestion_catalog(hints),
        "note": "Hints are soft Korean naturalness signals. They are not final scores.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source-text-free Korean naturalness hints.")
    parser.add_argument("--lines", help="Dialogue lines to inspect. Newlines are treated as turns.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hints = build_korean_naturalness_hints(args.lines or "")
    print(json.dumps(hints, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Korean grammar, idiom, and spoken-rhythm hints for Malmatch.

The module returns only aggregate metrics, signal labels, and line indexes. It
does not store or return the user's dialogue text.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from calibration_hints import normalize_lines, strip_speaker_prefix


VERSION = "0.3"

AXES = (
    "grammar_acceptability",
    "native_korean_idiom",
    "spoken_korean_rhythm",
)

DUPLICATE_PARTICLE_RE = re.compile(
    r"(은는|는은|이가|가이|을를|를을|은은|는는|이이|가가|을을|를를|에에|에서에서)"
)
DUPLICATE_CONNECTIVE_RE = re.compile(r"(그리고\s+그리고|하지만\s+하지만|그래서\s+그래서)")
ENDING_COLLISION_RE = re.compile(r"(습니다|습니까|입니다).{0,20}(어|아|야|잖아|거든)[.!?…]*$")

TRANSLATIONESE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("explicit_i_think", re.compile(r"(나는|저는|제가|내가).{0,24}(생각한다|생각해요|생각합니다)")),
    ("thing_pronoun_overuse", re.compile(r"(그것은|이것은|저것은).{0,24}(이다|입니다|이에요|예요)")),
    ("want_to_do_literalism", re.compile(r"하는\s+것을\s+(원해|원합니다|바라|바랍니다)")),
    ("make_decision_literalism", re.compile(r"결정을\s+만들")),
    ("have_problem_literalism", re.compile(r"문제를\s+가지고\s+있")),
    ("tell_me_literalism", re.compile(r"(나에게|저에게)\s+말해")),
    ("good_time_literalism", re.compile(r"좋은\s+시간을\s+보내")),
)

WRITTEN_ENDING_RE = re.compile(r"(다|것이다|것입니다|것으로 보인다|라고 생각한다)[.!?…]*$")
REACTION_RE = re.compile(r"^(응|어|아|음|그|맞아|그래|아니|잠깐|뭐|헐|진짜|괜찮)[.!?…]*$")
PRONOUN_RE = re.compile(r"(나는|저는|제가|내가|나를|저를|너는|네가|니가|당신은)")


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


def build_korean_naturalness_hints(lines_to_review: Any) -> dict[str, Any]:
    lines = normalize_lines(lines_to_review)
    stripped = [strip_speaker_prefix(line) for line in lines]
    line_count = len(stripped)
    lengths = [len(line) for line in stripped]

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

        for signal, pattern in TRANSLATIONESE_PATTERNS:
            if pattern.search(line):
                idiom_refs.append(index)
                idiom_signals.append(signal)

        if WRITTEN_ENDING_RE.search(line):
            written_refs.append(index)
        if len(line) <= 8 and REACTION_RE.search(line):
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
                0.74,
                grammar_signals,
                grammar_refs,
                "Possible particle, connective, or sentence-ending acceptability issue.",
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
            "total_chars": sum(lengths),
            "avg_chars": round(sum(lengths) / line_count, 1) if line_count else 0.0,
            "max_chars": max(lengths) if lengths else 0,
            "short_reaction_count": len(short_reaction_refs),
            "written_sentence_count": len(written_refs),
            "explicit_pronoun_count": pronoun_count,
        },
        "axes": list(AXES),
        "hints": hints,
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

#!/usr/bin/env python3
"""Build a local, source-text-free private pattern bank from dataset files."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from .calibration_hints import classify_speech_level
except ImportError:  # pragma: no cover - direct script execution
    from calibration_hints import classify_speech_level


VERSION = "0.1"
MAX_JSON_BYTES = 15 * 1024 * 1024
TEXT_LINE_EXTENSIONS = {".txt", ".ban", ".sho", ".yo"}

TEXT_FIELD_NAMES = {
    "text",
    "utterance",
    "utterances",
    "user_utterance",
    "system_utterance",
    "summary",
    "sentence",
    "content",
    "body",
    "발화",
    "문장",
    "대화",
    "요약",
}

LABEL_FIELD_NAMES = {
    "category",
    "domain",
    "type",
    "topic",
    "relation",
    "speaker_relation",
    "speaker_emotion",
    "speaker_changeemotion",
    "listener_behavior",
    "listener_empathy",
    "role",
    "grade",
    "mediatype",
    "medianame",
    "speech_level",
    "source",
}

EMOTION_LABEL_FIELDS = {
    "speaker_emotion",
    "speaker_changeemotion",
    "listener_behavior",
    "listener_empathy",
    "emotion",
    "감정",
}

COLLECTION_FIELD_NAMES = {
    "utterances",
    "dialogue",
    "dialogs",
    "conversation",
    "conversations",
    "data",
}

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a private no-source-text pattern bank from data_inventory.json."
    )
    parser.add_argument("--inventory", required=True, help="Inventory JSON path.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument(
        "--max-entries-per-zip",
        type=int,
        default=0,
        help="Max JSON/TXT entries sampled per zip archive. Use 0 for a full scan.",
    )
    return parser.parse_args()


def bucket_number(value: int, bounds: Iterable[int]) -> str:
    previous = 0
    for bound in bounds:
        if value <= bound:
            if previous == 0:
                return f"0-{bound}"
            return f"{previous + 1}-{bound}"
        previous = bound
    return f"{previous + 1}+"


def safe_counter(counter: Counter[str], limit: int = 80) -> dict[str, int]:
    return dict(counter.most_common(limit))


def safe_rate(value: float) -> float:
    return round(value, 4)


def counter_rates(counter: Counter[str], total: int) -> dict[str, float]:
    if total <= 0:
        return {}
    return {key: safe_rate(value / total) for key, value in sorted(counter.items())}


def average_rate_maps(rate_maps: Iterable[dict[str, float]]) -> dict[str, float]:
    maps = list(rate_maps)
    keys = sorted({key for rate_map in maps for key in rate_map})
    if not maps:
        return {}
    return {
        key: safe_rate(sum(rate_map.get(key, 0.0) for rate_map in maps) / len(maps))
        for key in keys
    }


def average_numbers(values: Iterable[float]) -> float:
    numbers = list(values)
    if not numbers:
        return 0.0
    return safe_rate(sum(numbers) / len(numbers))


def looks_like_label(value: str) -> bool:
    if not value or len(value) > 40:
        return False
    if "\n" in value or "\r" in value:
        return False
    if any(punctuation in value for punctuation in [".", "?", "!", "。", "…"]):
        return False
    return True


def detect_many(patterns: dict[str, re.Pattern[str]], text: str) -> set[str]:
    return {name for name, pattern in patterns.items() if pattern.search(text)}


def iter_objects(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_objects(child)


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp949", errors="ignore")


class PrivatePatternBankBuilder:
    def __init__(self) -> None:
        self.datasets: Counter[str] = Counter()
        self.files_considered = 0
        self.zip_entries_seen = 0
        self.entries_sampled = 0
        self.documents_sampled = 0
        self.documents_skipped = 0
        self.utterance_count = 0
        self.total_chars = 0
        self.max_chars = 0
        self.length_buckets: Counter[str] = Counter()
        self.turn_count_buckets: Counter[str] = Counter()
        self.speech_level_counts: Counter[str] = Counter()
        self.act_counts: Counter[str] = Counter()
        self.context_counts: Counter[str] = Counter()
        self.marker_counts: Counter[str] = Counter()
        self.label_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.emotion_label_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.context_baselines: dict[str, dict[str, Counter[str] | int]] = defaultdict(
            self._new_context_stats
        )
        self.errors: Counter[str] = Counter()
        self.quality_warnings: list[str] = []

    @staticmethod
    def _new_context_stats() -> dict[str, Counter[str] | int]:
        return {
            "utterance_count": 0,
            "length_buckets": Counter(),
            "speech_level_counts": Counter(),
            "act_counts": Counter(),
            "marker_counts": Counter(),
        }

    def add_file_meta(self, record: dict[str, Any]) -> None:
        self.files_considered += 1
        self.datasets[str(record.get("dataset", "unknown"))] += 1

    def add_label(self, key: str, value: str) -> None:
        if not looks_like_label(value):
            return
        self.label_counts[key][value] += 1
        if key.lower() in EMOTION_LABEL_FIELDS:
            self.emotion_label_counts[key][value] += 1

    def add_turn_count(self, count: int) -> None:
        self.turn_count_buckets[bucket_number(count, [1, 3, 5, 10, 20, 40])] += 1

    def add_text_features(self, text: str, context_blob: str = "") -> None:
        if not text:
            return

        length = len(text)
        length_bucket = bucket_number(length, [10, 30, 60, 120, 240])
        speech_level = classify_speech_level(text)
        acts = detect_many(ACT_PATTERNS, text)
        contexts = detect_many(CONTEXT_PATTERNS, f"{context_blob} {text}")

        self.utterance_count += 1
        self.total_chars += length
        self.max_chars = max(self.max_chars, length)
        self.length_buckets[length_bucket] += 1
        self.speech_level_counts[speech_level] += 1
        self.act_counts.update(acts)
        self.context_counts.update(contexts)
        self.marker_counts.update(acts & {"apology", "gratitude", "empathy", "polite_buffer"})

        for context in contexts:
            stats = self.context_baselines[context]
            stats["utterance_count"] = int(stats["utterance_count"]) + 1
            stats["length_buckets"].update([length_bucket])  # type: ignore[union-attr]
            stats["speech_level_counts"].update([speech_level])  # type: ignore[union-attr]
            stats["act_counts"].update(acts)  # type: ignore[union-attr]
            stats["marker_counts"].update(  # type: ignore[union-attr]
                acts & {"apology", "gratitude", "empathy", "polite_buffer"}
            )

    def collect_json(self, value: Any) -> None:
        self.documents_sampled += 1
        # iter_objects flattens the tree, so a list under a collection-named key is
        # yielded both as that dict's child (branch A) and on its own (branch B).
        # Track lists already counted by identity so each conversation counts once.
        counted_collections: set[int] = set()
        for item in iter_objects(value):
            if isinstance(item, dict):
                labels: list[str] = []
                for key, child in item.items():
                    lowered = str(key).lower()
                    if lowered in LABEL_FIELD_NAMES and isinstance(child, str):
                        self.add_label(str(key), child)
                        if looks_like_label(child):
                            labels.append(child)
                context_blob = " ".join(labels)

                for key, child in item.items():
                    lowered = str(key).lower()
                    if lowered in TEXT_FIELD_NAMES and isinstance(child, str):
                        self.add_text_features(child, context_blob)
                    if lowered in COLLECTION_FIELD_NAMES and isinstance(child, list):
                        self.add_turn_count(len(child))
                        counted_collections.add(id(child))
            elif isinstance(item, list):
                if id(item) in counted_collections:
                    continue
                if item and all(isinstance(child, dict) for child in item[: min(len(item), 5)]):
                    has_textish = any(
                        any(str(key).lower() in TEXT_FIELD_NAMES for key in child.keys())
                        for child in item[: min(len(item), 5)]
                    )
                    if has_textish:
                        self.add_turn_count(len(item))

    def collect_json_bytes(self, data: bytes) -> None:
        try:
            parsed = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.errors[type(exc).__name__] += 1
            self.documents_skipped += 1
            return
        self.collect_json(parsed)

    def collect_text_lines(self, data: bytes) -> None:
        for line in decode_text(data).splitlines():
            text = line.strip()
            if text:
                self.add_text_features(text)

    def process_zip(self, path: Path, max_entries: int) -> None:
        try:
            with zipfile.ZipFile(path) as archive:
                sampled = 0
                truncated = False
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    self.zip_entries_seen += 1
                    ext = posixpath.splitext(info.filename)[1].lower() or "<none>"
                    if ext != ".json" and ext not in TEXT_LINE_EXTENSIONS:
                        continue
                    if max_entries > 0 and sampled >= max_entries:
                        truncated = True
                        continue
                    sampled += 1
                    self.entries_sampled += 1
                    if ext == ".json" and info.file_size > MAX_JSON_BYTES:
                        self.documents_skipped += 1
                        self.errors["JsonEntryTooLarge"] += 1
                        continue
                    with archive.open(info) as handle:
                        data = handle.read()
                    if ext == ".json":
                        self.collect_json_bytes(data)
                    else:
                        self.collect_text_lines(data)
                if truncated:
                    self.quality_warnings.append(
                        f"{path.name}: sampled first {max_entries} supported entries"
                    )
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            self.errors[type(exc).__name__] += 1

    def process_json_file(self, path: Path) -> None:
        try:
            if path.stat().st_size > MAX_JSON_BYTES:
                self.documents_skipped += 1
                self.errors["JsonFileTooLarge"] += 1
                return
            self.collect_json_bytes(path.read_bytes())
        except OSError as exc:
            self.errors[type(exc).__name__] += 1

    def process_text_file(self, path: Path) -> None:
        try:
            self.collect_text_lines(path.read_bytes())
        except OSError as exc:
            self.errors[type(exc).__name__] += 1

    def absorb(self, other: "PrivatePatternBankBuilder") -> None:
        self.datasets.update(other.datasets)
        self.files_considered += other.files_considered
        self.zip_entries_seen += other.zip_entries_seen
        self.entries_sampled += other.entries_sampled
        self.documents_sampled += other.documents_sampled
        self.documents_skipped += other.documents_skipped
        self.utterance_count += other.utterance_count
        self.total_chars += other.total_chars
        self.max_chars = max(self.max_chars, other.max_chars)
        self.length_buckets.update(other.length_buckets)
        self.turn_count_buckets.update(other.turn_count_buckets)
        self.speech_level_counts.update(other.speech_level_counts)
        self.act_counts.update(other.act_counts)
        self.context_counts.update(other.context_counts)
        self.marker_counts.update(other.marker_counts)
        for key, counter in other.label_counts.items():
            self.label_counts[key].update(counter)
        for key, counter in other.emotion_label_counts.items():
            self.emotion_label_counts[key].update(counter)
        for context, other_stats in other.context_baselines.items():
            stats = self.context_baselines[context]
            stats["utterance_count"] = int(stats["utterance_count"]) + int(
                other_stats["utterance_count"]
            )
            stats["length_buckets"].update(other_stats["length_buckets"])  # type: ignore[union-attr]
            stats["speech_level_counts"].update(other_stats["speech_level_counts"])  # type: ignore[union-attr]
            stats["act_counts"].update(other_stats["act_counts"])  # type: ignore[union-attr]
            stats["marker_counts"].update(other_stats["marker_counts"])  # type: ignore[union-attr]
        self.errors.update(other.errors)
        self.quality_warnings.extend(other.quality_warnings)

    def avg_chars(self) -> float:
        if not self.utterance_count:
            return 0.0
        return round(self.total_chars / self.utterance_count, 1)

    def context_json(self, context: str) -> dict[str, Any]:
        stats = self.context_baselines[context]
        count = int(stats["utterance_count"])
        marker_counts = stats["marker_counts"]  # type: ignore[assignment]
        length_buckets = stats["length_buckets"]  # type: ignore[assignment]
        speech_level_counts = stats["speech_level_counts"]  # type: ignore[assignment]
        act_counts = stats["act_counts"]  # type: ignore[assignment]
        return {
            "utterance_count": count,
            "length_buckets": dict(sorted(length_buckets.items())),
            "length_bucket_rates": counter_rates(length_buckets, count),
            "speech_level_counts": dict(sorted(speech_level_counts.items())),
            "speech_level_rates": counter_rates(speech_level_counts, count),
            "act_counts": safe_counter(act_counts),
            "act_rates": counter_rates(act_counts, count),
            "marker_counts": safe_counter(marker_counts),  # type: ignore[arg-type]
            "marker_rates": {
                key: round(value / count, 4) if count else 0.0
                for key, value in sorted(marker_counts.items())  # type: ignore[union-attr]
            },
        }

    def context_baselines_json(self) -> dict[str, Any]:
        return {
            context: self.context_json(context)
            for context in sorted(self.context_baselines)
        }

    def global_baseline_json(self) -> dict[str, Any]:
        turn_total = sum(self.turn_count_buckets.values())
        return {
            "utterance_count": self.utterance_count,
            "avg_chars": self.avg_chars(),
            "max_chars": self.max_chars,
            "length_buckets": dict(sorted(self.length_buckets.items())),
            "length_bucket_rates": counter_rates(self.length_buckets, self.utterance_count),
            "turn_count_buckets": dict(sorted(self.turn_count_buckets.items())),
            "turn_count_rates": counter_rates(self.turn_count_buckets, turn_total),
            "speech_level_counts": dict(sorted(self.speech_level_counts.items())),
            "speech_level_rates": counter_rates(self.speech_level_counts, self.utterance_count),
            "act_counts": safe_counter(self.act_counts),
            "act_rates": counter_rates(self.act_counts, self.utterance_count),
            "context_counts": safe_counter(self.context_counts),
            "context_rates": counter_rates(self.context_counts, self.utterance_count),
            "marker_counts": safe_counter(self.marker_counts),
            "marker_rates": counter_rates(self.marker_counts, self.utterance_count),
        }

    def profile_json(self) -> dict[str, Any]:
        return {
            "files_considered": self.files_considered,
            "zip_entries_seen": self.zip_entries_seen,
            "entries_sampled": self.entries_sampled,
            "documents_sampled": self.documents_sampled,
            "documents_skipped": self.documents_skipped,
            "utterance_count": self.utterance_count,
            "avg_chars": self.avg_chars(),
            "max_chars": self.max_chars,
            "length_buckets": dict(sorted(self.length_buckets.items())),
            "turn_count_buckets": dict(sorted(self.turn_count_buckets.items())),
            "speech_level_counts": dict(sorted(self.speech_level_counts.items())),
            "act_counts": safe_counter(self.act_counts),
            "context_counts": safe_counter(self.context_counts),
            "marker_counts": safe_counter(self.marker_counts),
            "context_baselines": self.context_baselines_json(),
            "quality_warnings": sorted(set(self.quality_warnings)),
            "errors": dict(sorted(self.errors.items())),
        }

    def to_json(
        self,
        inventory_path: Path,
        dataset_builders: dict[str, "PrivatePatternBankBuilder"],
        max_entries_per_zip: int,
    ) -> dict[str, Any]:
        raw_global_baselines = self.global_baseline_json()
        raw_context_baselines = self.context_baselines_json()
        dataset_profiles = {
            dataset: builder.profile_json()
            for dataset, builder in sorted(dataset_builders.items())
        }
        balanced_baselines = build_balanced_baselines(dataset_builders, self)
        dominant_dataset_share = 0.0
        if self.utterance_count:
            dominant_dataset_share = safe_rate(
                max((builder.utterance_count for builder in dataset_builders.values()), default=0)
                / self.utterance_count
            )
        datasets_with_features = sorted(
            dataset
            for dataset, builder in dataset_builders.items()
            if builder.utterance_count > 0
        )
        politeness_contexts = {
            key: value
            for key, value in raw_context_baselines.items()
            if key in {"customer_complaint", "formal_first_meeting", "hierarchy", "request", "refusal"}
        }
        quality_warnings = set(self.quality_warnings)
        if dominant_dataset_share >= 0.5 and len(datasets_with_features) > 1:
            quality_warnings.add(
                f"largest dataset contributes {dominant_dataset_share:.2%} of raw utterance features; use balanced_baselines for runtime guidance"
            )
        return {
            "schema": "private_pattern_bank",
            "version": VERSION,
            "inventory": str(inventory_path),
            "policy": {
                "stored_text": False,
                "source_text_values": "omitted",
                "raw_dialogue_examples": "not_included",
            },
            "coverage": {
                "datasets": dict(sorted(self.datasets.items())),
                "datasets_with_features": datasets_with_features,
                "datasets_with_features_count": len(datasets_with_features),
                "files_considered": self.files_considered,
                "zip_entries_seen": self.zip_entries_seen,
                "entries_sampled": self.entries_sampled,
                "documents_sampled": self.documents_sampled,
                "documents_skipped": self.documents_skipped,
                "utterance_count": self.utterance_count,
                "max_entries_per_zip": max_entries_per_zip,
                "full_entry_scan": max_entries_per_zip == 0,
                "dominant_dataset_share": dominant_dataset_share,
            },
            "global_baselines": raw_global_baselines,
            "context_baselines": raw_context_baselines,
            "raw_global_baselines": raw_global_baselines,
            "raw_context_baselines": raw_context_baselines,
            "dataset_profiles": dataset_profiles,
            "balanced_baselines": balanced_baselines,
            "speech_level_baselines": {
                "counts": dict(sorted(self.speech_level_counts.items())),
                "context_counts": {
                    context: data["speech_level_counts"] for context, data in raw_context_baselines.items()
                },
            },
            "politeness_baselines": politeness_contexts,
            "emotion_response_baselines": {
                "label_counts": {
                    key: safe_counter(counter)
                    for key, counter in sorted(self.emotion_label_counts.items())
                },
                "act_counts": safe_counter(self.act_counts),
            },
            "label_counts": {
                key: safe_counter(counter)
                for key, counter in sorted(self.label_counts.items())
            },
            "quality_warnings": sorted(quality_warnings),
            "errors": dict(sorted(self.errors.items())),
        }


def builder_rate_map(builder: PrivatePatternBankBuilder, counter_name: str) -> dict[str, float]:
    counter = getattr(builder, counter_name)
    total = builder.utterance_count
    if counter_name == "turn_count_buckets":
        total = sum(counter.values())
    return counter_rates(counter, total)


def balanced_context_baselines(
    dataset_builders: dict[str, PrivatePatternBankBuilder]
) -> dict[str, Any]:
    contexts = sorted(
        {
            context
            for builder in dataset_builders.values()
            if builder.utterance_count > 0
            for context in builder.context_baselines
        }
    )
    result: dict[str, Any] = {}
    for context in contexts:
        context_builders = [
            builder
            for builder in dataset_builders.values()
            if int(builder.context_baselines.get(context, {}).get("utterance_count", 0)) > 0
        ]
        raw_count = sum(
            int(builder.context_baselines[context]["utterance_count"])
            for builder in context_builders
        )
        result[context] = {
            "utterance_count": raw_count,
            "utterance_count_raw": raw_count,
            "dataset_count": len(context_builders),
            "length_bucket_rates": average_rate_maps(
                counter_rates(
                    builder.context_baselines[context]["length_buckets"],  # type: ignore[arg-type]
                    int(builder.context_baselines[context]["utterance_count"]),
                )
                for builder in context_builders
            ),
            "speech_level_rates": average_rate_maps(
                counter_rates(
                    builder.context_baselines[context]["speech_level_counts"],  # type: ignore[arg-type]
                    int(builder.context_baselines[context]["utterance_count"]),
                )
                for builder in context_builders
            ),
            "act_rates": average_rate_maps(
                counter_rates(
                    builder.context_baselines[context]["act_counts"],  # type: ignore[arg-type]
                    int(builder.context_baselines[context]["utterance_count"]),
                )
                for builder in context_builders
            ),
            "marker_rates": average_rate_maps(
                counter_rates(
                    builder.context_baselines[context]["marker_counts"],  # type: ignore[arg-type]
                    int(builder.context_baselines[context]["utterance_count"]),
                )
                for builder in context_builders
            ),
        }
    return result


def build_balanced_baselines(
    dataset_builders: dict[str, PrivatePatternBankBuilder],
    raw_builder: PrivatePatternBankBuilder,
) -> dict[str, Any]:
    feature_builders = [
        builder for builder in dataset_builders.values() if builder.utterance_count > 0
    ]
    return {
        "dataset_count": len(feature_builders),
        "utterance_count_raw": raw_builder.utterance_count,
        "global_baselines": {
            "dataset_count": len(feature_builders),
            "utterance_count_raw": raw_builder.utterance_count,
            "avg_chars": average_numbers(builder.avg_chars() for builder in feature_builders),
            "max_chars": max((builder.max_chars for builder in feature_builders), default=0),
            "length_bucket_rates": average_rate_maps(
                builder_rate_map(builder, "length_buckets") for builder in feature_builders
            ),
            "turn_count_rates": average_rate_maps(
                builder_rate_map(builder, "turn_count_buckets") for builder in feature_builders
            ),
            "speech_level_rates": average_rate_maps(
                builder_rate_map(builder, "speech_level_counts") for builder in feature_builders
            ),
            "act_rates": average_rate_maps(
                builder_rate_map(builder, "act_counts") for builder in feature_builders
            ),
            "context_rates": average_rate_maps(
                builder_rate_map(builder, "context_counts") for builder in feature_builders
            ),
            "marker_rates": average_rate_maps(
                builder_rate_map(builder, "marker_counts") for builder in feature_builders
            ),
        },
        "context_baselines": balanced_context_baselines(dataset_builders),
    }


def build_private_pattern_bank(
    inventory_path: Path,
    *,
    max_entries_per_zip: int = 0,
) -> dict[str, Any]:
    if max_entries_per_zip < 0:
        raise ValueError("max_entries_per_zip must be 0 or a positive integer")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = Path(inventory["root"]).resolve()
    dataset_builders: dict[str, PrivatePatternBankBuilder] = {}

    for record in inventory.get("files", []):
        relative_path = record.get("path")
        if not relative_path:
            continue
        path = root / relative_path
        dataset = str(record.get("dataset", "unknown"))
        builder = dataset_builders.setdefault(dataset, PrivatePatternBankBuilder())
        builder.add_file_meta(record)
        extension = str(record.get("extension", path.suffix.lower())).lower()
        if extension == ".zip":
            builder.process_zip(path, max_entries_per_zip)
        elif extension == ".json":
            builder.process_json_file(path)
        elif extension in TEXT_LINE_EXTENSIONS:
            builder.process_text_file(path)

    raw_builder = PrivatePatternBankBuilder()
    for builder in dataset_builders.values():
        raw_builder.absorb(builder)

    return raw_builder.to_json(inventory_path, dataset_builders, max_entries_per_zip)


def main() -> int:
    args = parse_args()
    inventory_path = Path(args.inventory).resolve()
    out_path = Path(args.out).resolve()
    bank = build_private_pattern_bank(
        inventory_path,
        max_entries_per_zip=args.max_entries_per_zip,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {out_path} ({bank['coverage']['utterance_count']} utterance features)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

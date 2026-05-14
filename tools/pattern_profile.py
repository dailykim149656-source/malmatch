#!/usr/bin/env python3
"""Build aggregate dialogue-pattern profiles without storing utterance text."""

from __future__ import annotations

import argparse
import json
import math
import posixpath
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


TARGET_DATASETS = {
    "020.주제별 텍스트 일상 대화 데이터",
    "044.페르소나 대화",
    "046.공감형 대화",
    "018.감성대화",
    "한국어 어체 변환 코퍼스",
    "한국어 대화 요약",
    "011.일상대화 한국어 멀티세션 데이터",
    "141.한국어 멀티세션 대화",
}

TEXT_FIELD_NAMES = {
    "text",
    "utterance",
    "user_utterance",
    "system_utterance",
    "summary",
    "sentence",
    "content",
    "body",
    "bad_line",
    "good_line",
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
    "speaker_changeEmotion",
    "listener_behavior",
    "listener_empathy",
    "role",
    "grade",
    "mediatype",
    "medianame",
    "speech_level",
    "source",
}

COLLECTION_FIELD_NAMES = {
    "utterances",
    "dialogue",
    "dialogs",
    "conversation",
    "conversations",
    "data",
}

MAX_JSON_BYTES = 15 * 1024 * 1024
TEXT_LINE_EXTENSIONS = {".txt", ".ban", ".sho", ".yo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create no-source-text aggregate pattern profiles."
    )
    parser.add_argument("--inventory", required=True, help="Inventory JSON path.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument(
        "--max-entries-per-zip",
        type=int,
        default=200,
        help="Max supported entries sampled per zip archive.",
    )
    return parser.parse_args()


def safe_counter(counter: Counter[str], limit: int = 80) -> dict[str, int]:
    return dict(counter.most_common(limit))


def bucket_number(value: int, bounds: Iterable[int]) -> str:
    previous = 0
    for bound in bounds:
        if value <= bound:
            if previous == 0:
                return f"0-{bound}"
            return f"{previous + 1}-{bound}"
        previous = bound
    return f"{previous + 1}+"


def looks_like_label(value: str) -> bool:
    if not value:
        return False
    if len(value) > 40:
        return False
    if "\n" in value or "\r" in value:
        return False
    if any(punctuation in value for punctuation in [".", "?", "!", "。", "…"]):
        return False
    return True


class DatasetProfile:
    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        self.files_considered = 0
        self.zip_entries_seen = 0
        self.entries_sampled = 0
        self.documents_sampled = 0
        self.documents_skipped = 0
        self.errors: Counter[str] = Counter()
        self.splits: Counter[str] = Counter()
        self.data_roles: Counter[str] = Counter()
        self.file_extensions: Counter[str] = Counter()
        self.entry_extensions: Counter[str] = Counter()
        self.label_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.turn_count_buckets: Counter[str] = Counter()
        self.utterance_length_buckets: Counter[str] = Counter()
        self.utterance_count = 0
        self.text_field_hits: Counter[str] = Counter()
        self.parallel_text_line_counts: Counter[str] = Counter()

    def add_file_meta(self, record: dict[str, Any]) -> None:
        self.files_considered += 1
        self.splits[str(record.get("split", "unknown"))] += 1
        self.data_roles[str(record.get("data_role", "unknown"))] += 1
        self.file_extensions[str(record.get("extension", "<none>"))] += 1

    def add_label(self, key: str, value: str) -> None:
        if looks_like_label(value):
            self.label_counts[key][value] += 1

    def add_turn_count(self, count: int) -> None:
        self.turn_count_buckets[bucket_number(count, [1, 3, 5, 10, 20, 40])] += 1

    def add_text_length(self, key: str, text: str) -> None:
        self.text_field_hits[key] += 1
        self.utterance_count += 1
        self.utterance_length_buckets[bucket_number(len(text), [10, 30, 60, 120, 240])] += 1

    def to_json(self) -> dict[str, Any]:
        return {
            "files_considered": self.files_considered,
            "zip_entries_seen": self.zip_entries_seen,
            "entries_sampled": self.entries_sampled,
            "documents_sampled": self.documents_sampled,
            "documents_skipped": self.documents_skipped,
            "splits": dict(sorted(self.splits.items())),
            "data_roles": dict(sorted(self.data_roles.items())),
            "file_extensions": dict(sorted(self.file_extensions.items())),
            "entry_extensions": dict(sorted(self.entry_extensions.items())),
            "label_counts": {
                key: safe_counter(counter)
                for key, counter in sorted(self.label_counts.items())
            },
            "turn_count_buckets": dict(sorted(self.turn_count_buckets.items())),
            "utterance_length_buckets": dict(sorted(self.utterance_length_buckets.items())),
            "utterance_count": self.utterance_count,
            "text_field_hits": dict(sorted(self.text_field_hits.items())),
            "parallel_text_line_counts": dict(sorted(self.parallel_text_line_counts.items())),
            "errors": dict(sorted(self.errors.items())),
        }


def iter_objects(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_objects(child)


def collect_profile_from_json(value: Any, profile: DatasetProfile) -> None:
    profile.documents_sampled += 1

    for item in iter_objects(value):
        if isinstance(item, dict):
            for key, child in item.items():
                normalized_key = str(key)
                lowered_key = normalized_key.lower()
                if lowered_key in LABEL_FIELD_NAMES and isinstance(child, str):
                    profile.add_label(normalized_key, child)
                if lowered_key in TEXT_FIELD_NAMES and isinstance(child, str):
                    profile.add_text_length(normalized_key, child)
                if lowered_key in COLLECTION_FIELD_NAMES and isinstance(child, list):
                    profile.add_turn_count(len(child))
        elif isinstance(item, list):
            if item and all(isinstance(child, dict) for child in item[: min(len(item), 5)]):
                has_textish = any(
                    any(str(key).lower() in TEXT_FIELD_NAMES for key in child.keys())
                    for child in item[: min(len(item), 5)]
                )
                if has_textish:
                    profile.add_turn_count(len(item))


def parse_json_bytes(data: bytes, profile: DatasetProfile) -> None:
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        profile.errors[type(exc).__name__] += 1
        profile.documents_skipped += 1
        return
    collect_profile_from_json(value, profile)


def detect_parallel_variant(entry_name: str) -> str:
    base = posixpath.basename(entry_name).lower()
    if ".ban." in base or base.endswith((".ban", ".ban.txt")):
        return "banmal"
    if ".sho." in base or base.endswith((".sho", ".sho.txt")):
        return "hapsyoche"
    if ".yo." in base or base.endswith((".yo", ".yo.txt")):
        return "haeyoche"
    return "other_text"


def count_text_lines_without_storing(data: bytes) -> int:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp949", errors="ignore")
    return sum(1 for line in text.splitlines() if line.strip())


def process_zip(record: dict[str, Any], root: Path, profile: DatasetProfile, max_entries: int) -> None:
    path = root / record["path"]
    try:
        with zipfile.ZipFile(path) as archive:
            sampled = 0
            for info in archive.infolist():
                if info.is_dir():
                    continue
                profile.zip_entries_seen += 1
                ext = posixpath.splitext(info.filename)[1].lower() or "<none>"
                profile.entry_extensions[ext] += 1
                if ext != ".json" and ext not in TEXT_LINE_EXTENSIONS:
                    continue
                if sampled >= max_entries:
                    continue
                sampled += 1
                profile.entries_sampled += 1
                if info.file_size > MAX_JSON_BYTES and ext == ".json":
                    profile.documents_skipped += 1
                    profile.errors["JsonEntryTooLarge"] += 1
                    continue
                with archive.open(info) as handle:
                    data = handle.read()
                if ext == ".json":
                    parse_json_bytes(data, profile)
                elif ext in TEXT_LINE_EXTENSIONS:
                    variant = detect_parallel_variant(info.filename)
                    profile.parallel_text_line_counts[variant] += count_text_lines_without_storing(data)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        profile.errors[type(exc).__name__] += 1


def process_json_file(record: dict[str, Any], root: Path, profile: DatasetProfile) -> None:
    path = root / record["path"]
    try:
        if path.stat().st_size > MAX_JSON_BYTES:
            profile.documents_skipped += 1
            profile.errors["JsonFileTooLarge"] += 1
            return
        parse_json_bytes(path.read_bytes(), profile)
    except OSError as exc:
        profile.errors[type(exc).__name__] += 1


def main() -> int:
    args = parse_args()
    inventory_path = Path(args.inventory).resolve()
    out_path = Path(args.out).resolve()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    root = Path(inventory["root"]).resolve()

    profiles: dict[str, DatasetProfile] = {
        dataset: DatasetProfile(dataset) for dataset in sorted(TARGET_DATASETS)
    }

    for record in inventory.get("files", []):
        dataset = record.get("dataset")
        if dataset not in profiles:
            continue
        profile = profiles[dataset]
        profile.add_file_meta(record)
        extension = record.get("extension")
        if extension == ".zip":
            process_zip(record, root, profile, args.max_entries_per_zip)
        elif extension == ".json":
            process_json_file(record, root, profile)
        elif extension == ".xlsx":
            profile.entry_extensions["xlsx_sheet"] += len(
                record.get("xlsx", {}).get("sheets", [])
            )

    output = {
        "schema_version": 1,
        "inventory": str(inventory_path),
        "policy": {
            "source_text_values": "omitted",
            "stored_text": False,
            "raw_dialogue_examples": "not_included",
            "sampling_note": "Zip processing samples a bounded number of JSON/TXT entries per archive by default.",
        },
        "datasets": {
            dataset: profile.to_json()
            for dataset, profile in sorted(profiles.items())
            if profile.files_considered
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {out_path} ({len(output['datasets'])} datasets)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

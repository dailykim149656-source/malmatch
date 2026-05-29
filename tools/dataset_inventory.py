#!/usr/bin/env python3
"""Inventory local dataset archives without storing source text values."""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


DATA_EXTENSIONS = {".zip", ".xlsx", ".json"}
DEFAULT_SKIP_DIRS = {".git", ".malmatch", ".omx", "__pycache__", "tools", "docs"}
MAX_JSON_BYTES = 10 * 1024 * 1024
SENSITIVE_VALUE_KEYS = {
    "text",
    "utterance",
    "utterances",
    "user_utterance",
    "system_utterance",
    "dialogue",
    "summary",
    "sentence",
    "content",
    "body",
    "발화",
    "문장",
    "대화",
    "요약",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a no-source-text inventory of local dataset files."
    )
    parser.add_argument("--root", default=".", help="Workspace root to scan.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument(
        "--max-json-samples",
        type=int,
        default=3,
        help="Max JSON files to sample per zip archive.",
    )
    return parser.parse_args()


def relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def should_skip(path: Path, root: Path, out_path: Path) -> bool:
    if path.resolve() == out_path.resolve():
        return True
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    parts = set(relative.parts)
    return bool(parts & DEFAULT_SKIP_DIRS)


def infer_split(path: str) -> str:
    lowered = path.lower()
    if any(token in lowered for token in ["validation", "valid", "/vl_", "[라벨]한국어대화요약_valid"]):
        return "validation"
    if any(token in lowered for token in ["training", "train", "/tl_", "[라벨]한국어대화요약_train"]):
        return "training"
    if "test" in lowered:
        return "test"
    if "dev" in lowered:
        return "dev"
    return "unknown"


def infer_data_role(path: str) -> str:
    lowered = path.lower()
    if any(token in lowered for token in ["라벨링", "[라벨]", "label", "/vl_", "/tl_"]):
        return "label"
    if any(token in lowered for token in ["원천", "원시", "source", "/vs_", "/ts_"]):
        return "source"
    return "unknown"


def top_dataset_name(path: Path, root: Path) -> str:
    relative = path.resolve().relative_to(root.resolve())
    if len(relative.parts) > 1:
        return relative.parts[0]
    return path.stem


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def describe_json(value: Any, depth: int = 0, max_depth: int = 4) -> dict[str, Any]:
    """Describe JSON shape without storing scalar values."""
    value_type = json_type_name(value)
    result: dict[str, Any] = {"type": value_type}
    if depth >= max_depth:
        return result

    if isinstance(value, dict):
        keys = sorted(str(key) for key in value.keys())
        result["keys"] = keys
        children: dict[str, Any] = {}
        for key in keys[:80]:
            child = value.get(key)
            if str(key).lower() in SENSITIVE_VALUE_KEYS:
                children[str(key)] = {"type": json_type_name(child), "value": "omitted"}
            else:
                children[str(key)] = describe_json(child, depth + 1, max_depth)
        result["children"] = children
    elif isinstance(value, list):
        result["length"] = len(value)
        if value:
            result["item"] = describe_json(value[0], depth + 1, max_depth)
    elif isinstance(value, str):
        result["value"] = "omitted"
    return result


def read_json_shape_from_bytes(data: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__}
    return describe_json(parsed)


def inspect_zip(path: Path, max_json_samples: int) -> dict[str, Any]:
    extension_counts: Counter[str] = Counter()
    json_samples: list[dict[str, Any]] = []
    entry_count = 0
    file_count = 0
    total_uncompressed = 0
    largest_entries: list[dict[str, Any]] = []

    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            entry_count += 1
            if info.is_dir():
                continue
            file_count += 1
            total_uncompressed += info.file_size
            ext = posixpath.splitext(info.filename)[1].lower() or "<none>"
            extension_counts[ext] += 1
            largest_entries.append(
                {
                    "name": info.filename,
                    "size_bytes": info.file_size,
                    "extension": ext,
                }
            )
            if ext == ".json" and len(json_samples) < max_json_samples:
                if info.file_size <= MAX_JSON_BYTES:
                    with archive.open(info) as handle:
                        data = handle.read()
                    json_samples.append(
                        {
                            "entry": info.filename,
                            "size_bytes": info.file_size,
                            "shape": read_json_shape_from_bytes(data),
                        }
                    )
                else:
                    json_samples.append(
                        {
                            "entry": info.filename,
                            "size_bytes": info.file_size,
                            "shape": {"skipped": "json entry exceeds sample byte limit"},
                        }
                    )

    largest_entries = sorted(
        largest_entries, key=lambda item: item["size_bytes"], reverse=True
    )[:10]
    return {
        "entry_count": entry_count,
        "file_count": file_count,
        "total_uncompressed_bytes": total_uncompressed,
        "extension_counts": dict(sorted(extension_counts.items())),
        "largest_entries": largest_entries,
        "json_samples": json_samples,
    }


def inspect_json_file(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if size > MAX_JSON_BYTES:
        return {"skipped": "json file exceeds sample byte limit", "size_bytes": size}
    data = path.read_bytes()
    return read_json_shape_from_bytes(data)


def parse_sheet_dimension(xml_bytes: bytes) -> str | None:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return None
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    dimension = root.find("main:dimension", namespace)
    if dimension is not None:
        return dimension.attrib.get("ref")
    return None


def inspect_xlsx(path: Path) -> dict[str, Any]:
    sheets: list[dict[str, Any]] = []
    extension_counts: Counter[str] = Counter()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            ext = posixpath.splitext(name)[1].lower() or "<none>"
            extension_counts[ext] += 1
        worksheet_names = [
            name for name in names if name.startswith("xl/worksheets/") and name.endswith(".xml")
        ]
        for name in worksheet_names:
            with archive.open(name) as handle:
                dimension = parse_sheet_dimension(handle.read(256 * 1024))
            sheets.append({"entry": name, "dimension": dimension})
    return {
        "zip_entry_count": len(extension_counts),
        "extension_counts": dict(sorted(extension_counts.items())),
        "sheets": sheets,
    }


def inspect_file(path: Path, root: Path, max_json_samples: int) -> dict[str, Any]:
    path_string = relpath(path, root)
    base: dict[str, Any] = {
        "path": path_string,
        "dataset": top_dataset_name(path, root),
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "split": infer_split(path_string),
        "data_role": infer_data_role(path_string),
    }
    try:
        if path.suffix.lower() == ".zip":
            base["archive"] = inspect_zip(path, max_json_samples)
        elif path.suffix.lower() == ".json":
            base["json_shape"] = inspect_json_file(path)
        elif path.suffix.lower() == ".xlsx":
            base["xlsx"] = inspect_xlsx(path)
    except (OSError, zipfile.BadZipFile, RuntimeError, UnicodeDecodeError) as exc:
        base["error"] = type(exc).__name__
        base["error_message"] = str(exc)
    return base


def find_dataset_files(root: Path, out_path: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames[:] = [
            dirname for dirname in dirnames if dirname not in DEFAULT_SKIP_DIRS
        ]
        for filename in filenames:
            path = current_path / filename
            if path.suffix.lower() not in DATA_EXTENSIONS:
                continue
            if should_skip(path, root, out_path):
                continue
            files.append(path)
    return sorted(files, key=lambda item: relpath(item, root))


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_path = Path(args.out).resolve()
    files = find_dataset_files(root, out_path)
    records = [inspect_file(path, root, args.max_json_samples) for path in files]

    by_dataset = Counter(record["dataset"] for record in records)
    by_extension = Counter(record["extension"] for record in records)
    output = {
        "schema_version": 1,
        "root": str(root),
        "policy": {
            "source_text_values": "omitted",
            "json_scalar_values": "omitted",
            "zip_extraction": "not_performed",
        },
        "summary": {
            "file_count": len(records),
            "datasets": dict(sorted(by_dataset.items())),
            "extensions": dict(sorted(by_extension.items())),
        },
        "files": records,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {out_path} ({len(records)} files)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

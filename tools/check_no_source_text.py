#!/usr/bin/env python3
"""Check public artifacts for likely copied source text fields."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TEXT_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".txt"}
FORBIDDEN_FIELD_RE = re.compile(
    r"^\s*(text|utterance|utterances|raw_text|source_text|original_text|"
    r"dialogue|conversation|summary|발화|원문|요약)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
ALLOWED_EMPTY_VALUES = {"", "|", ">", "[]", "{}", "omitted", "not_included"}
REQUIRED_EXAMPLE_KEYS = {
    "id",
    "category",
    "scene",
    "character_context",
    "relationship_context",
    "bad_line",
    "good_line",
    "why_bad",
    "why_good",
    "risk_tags",
    "source_basis",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan public files for forbidden source-text-like fields."
    )
    parser.add_argument("--paths", nargs="+", required=True, help="Files or directories to scan.")
    return parser.parse_args()


def iter_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            files.append(path)
            continue
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in TEXT_EXTENSIONS:
                    files.append(child)
    return sorted(set(files))


def is_forbidden_scalar(value: str) -> bool:
    cleaned = value.strip().strip("'\"")
    if cleaned in ALLOWED_EMPTY_VALUES:
        return False
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return False
    return bool(cleaned)


def scan_file(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        issues.append(f"{path}: cannot decode as utf-8")
        return issues

    for lineno, line in enumerate(lines, 1):
        match = FORBIDDEN_FIELD_RE.match(line)
        if match and is_forbidden_scalar(match.group(2)):
            issues.append(f"{path}:{lineno}: forbidden source-like field `{match.group(1)}`")
    return issues


def parse_example_blocks(path: Path) -> list[tuple[int, set[str]]]:
    if not path.exists():
        return []
    blocks: list[tuple[int, set[str]]] = []
    current_line = 0
    current_keys: set[str] | None = None
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("- id:"):
            if current_keys is not None:
                blocks.append((current_line, current_keys))
            current_line = lineno
            current_keys = {"id"}
            continue
        if current_keys is not None:
            match = re.match(r"^\s+([A-Za-z_]+):", line)
            if match:
                current_keys.add(match.group(1))
    if current_keys is not None:
        blocks.append((current_line, current_keys))
    return blocks


def validate_examples() -> list[str]:
    path = Path("examples/good_bad_pairs.yaml")
    blocks = parse_example_blocks(path)
    issues: list[str] = []
    if len(blocks) != 30:
        issues.append(f"{path}: expected 30 examples, found {len(blocks)}")
    for line, keys in blocks:
        missing = REQUIRED_EXAMPLE_KEYS - keys
        if missing:
            issues.append(f"{path}:{line}: missing keys {sorted(missing)}")
    return issues


def main() -> int:
    args = parse_args()
    issues: list[str] = []
    files = iter_files(args.paths)
    for path in files:
        issues.extend(scan_file(path))
    issues.extend(validate_examples())

    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    print(f"Checked {len(files)} files; no forbidden source-text fields found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

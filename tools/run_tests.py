#!/usr/bin/env python3
"""Run the focused Malmatch verification suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TEST_SCRIPTS = [
    "tools/test_text_metrics.py",
    "tools/test_calibration_hints.py",
    "tools/test_korean_naturalness_hints.py",
    "tools/test_dataset_guidance.py",
    "tools/test_private_pattern_bank.py",
    "tools/test_mcp_stdio.py",
]


def run(command: list[str], label: str) -> int:
    print(f"==> {label}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


def main() -> int:
    for script in TEST_SCRIPTS:
        returncode = run([sys.executable, str(ROOT / script)], script)
        if returncode:
            return returncode

    import_check = (
        "from tools.korean_character_voice_mcp import main; "
        "assert callable(main); "
        "print('Package import check passed.')"
    )
    returncode = run([sys.executable, "-c", import_check], "package import check")
    if returncode:
        return returncode

    print("All Malmatch tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

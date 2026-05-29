#!/usr/bin/env python3
"""Local stdio MCP server for 말매치 Malmatch."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .calibration_hints import build_calibration_hints
    from .dataset_guidance import build_dataset_guidance
    from .korean_naturalness_hints import build_korean_naturalness_hints
    from .text_metrics import build_text_metrics
except ImportError:  # pragma: no cover - direct script execution
    from calibration_hints import build_calibration_hints
    from dataset_guidance import build_dataset_guidance
    from korean_naturalness_hints import build_korean_naturalness_hints
    from text_metrics import build_text_metrics


PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "malmatch"
SERVER_VERSION = "0.1.0"
CODE_ROOT = Path(__file__).resolve().parents[1]


def resolve_public_root() -> Path:
    candidates = [
        CODE_ROOT,
        Path(sys.prefix) / "share" / "malmatch",
        Path(sys.base_prefix) / "share" / "malmatch",
    ]
    for candidate in candidates:
        if (candidate / "README.md").exists() and (candidate / "docs").is_dir():
            return candidate.resolve()
    return CODE_ROOT


ROOT = resolve_public_root()

RESOURCE_FILES = {
    "malmatch://README": ("README", "README.md", "text/markdown"),
    "malmatch://docs/evaluation_rubric": (
        "Evaluation Rubric",
        "docs/evaluation_rubric.md",
        "text/markdown",
    ),
    "malmatch://docs/usage": ("Usage", "docs/usage.md", "text/markdown"),
    "malmatch://schemas/voice_profile": (
        "Voice Profile Schema",
        "schemas/voice_profile.schema.yaml",
        "text/yaml",
    ),
    "malmatch://schemas/dialogue_item": (
        "Dialogue Item Schema",
        "schemas/dialogue_item.schema.yaml",
        "text/yaml",
    ),
    "malmatch://schemas/relationship_boundary": (
        "Relationship Boundary Schema",
        "schemas/relationship_boundary.schema.yaml",
        "text/yaml",
    ),
    "malmatch://schemas/evaluation_result": (
        "Evaluation Result Schema",
        "schemas/evaluation_result.schema.yaml",
        "text/yaml",
    ),
    "malmatch://schemas/calibration_hint": (
        "Calibration Hint Schema",
        "schemas/calibration_hint.schema.yaml",
        "text/yaml",
    ),
    "malmatch://schemas/korean_naturalness_hint": (
        "Korean Naturalness Hint Schema",
        "schemas/korean_naturalness_hint.schema.yaml",
        "text/yaml",
    ),
    "malmatch://schemas/text_metrics": (
        "Text Metrics Schema",
        "schemas/text_metrics.schema.yaml",
        "text/yaml",
    ),
    "malmatch://schemas/dataset_guidance": (
        "Dataset Guidance Schema",
        "schemas/dataset_guidance.schema.yaml",
        "text/yaml",
    ),
    "malmatch://examples/good_bad_pairs": (
        "Synthetic Good/Bad Pairs",
        "examples/good_bad_pairs.yaml",
        "text/yaml",
    ),
}

PROMPT_FILES = {
    "dialogue_audit": ("Dialogue Audit", "prompts/dialogue_audit.md"),
    "humor_pass": ("Humor Pass", "prompts/humor_pass.md"),
    "rewrite_lightly": ("Rewrite Lightly", "prompts/rewrite_lightly.md"),
    "character_voice_check": ("Character Voice Check", "prompts/character_voice_check.md"),
    "speech_level_check": ("Speech Level Check", "prompts/speech_level_check.md"),
    "korean_naturalness_check": (
        "Korean Naturalness Check",
        "prompts/korean_naturalness_check.md",
    ),
    "cringe_risk_check": ("Cringe Risk Check", "prompts/cringe_risk_check.md"),
}

RUBRIC_AXES = [
    "naturalness",
    "character_fit",
    "relationship_fit",
    "speech_level_consistency",
    "humor_timing",
    "cringe_risk",
    "anachronism_risk",
    "genre_fit",
]

EXAMPLE_CATEGORIES = [
    "naturalness",
    "character_drift",
    "relationship_empathy_boundary",
    "speech_level",
    "humor_timing",
    "anachronism_genre",
]


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def read_text(relative_path: str) -> str:
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents and path != ROOT:
        raise JsonRpcError(-32602, f"Refusing to read outside skill pack: {relative_path}")
    if not path.exists():
        raise JsonRpcError(-32602, f"Missing resource file: {relative_path}")
    return path.read_text(encoding="utf-8")


def local_state_file(name: str) -> Path:
    for root in [Path.cwd().resolve(), ROOT]:
        for directory in [root / ".malmatch", root / ".omx"]:
            candidate = directory / name
            if candidate.exists():
                return candidate
    return ROOT / ".malmatch" / name


def write_response(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_result(structured: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    result = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(structured, ensure_ascii=False, indent=2),
            }
        ],
        "structuredContent": structured,
    }
    if is_error:
        result["isError"] = True
    return result


def initialize_result() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"listChanged": False},
            "prompts": {"listChanged": False},
        },
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": (
            "Use Malmatch when Korean character dialogue needs audit context, "
            "rubrics, prompt templates, speech-level guidance, or synthetic examples."
        ),
    }


def tools_list_result() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "get_skillpack_overview",
                "title": "Get Skillpack Overview",
                "description": "Use this first to understand the Malmatch Korean character dialogue audit workflow.",
                "inputSchema": {"type": "object", "additionalProperties": False},
            },
            {
                "name": "get_rubric",
                "title": "Get Evaluation Rubric",
                "description": "Use this when scoring Korean dialogue across the eight Malmatch rubric axes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"include_full_text": {"type": "boolean", "default": False}},
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_prompt_template",
                "title": "Get Prompt Template",
                "description": "Use this to retrieve one reusable prompt template by name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "enum": list(PROMPT_FILES)}},
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_examples",
                "title": "Get Synthetic Examples",
                "description": "Use this to fetch synthetic good/bad pairs filtered by category. Never cite them as corpus excerpts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": EXAMPLE_CATEGORIES},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 5},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_calibration_hints",
                "title": "Get Calibration Hints",
                "description": "Use this to get local, source-text-free soft signals for length, speech-level, relationship, and Korean politeness risks.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "scene": {"type": "string"},
                        "medium": {"type": "string"},
                        "genre": {"type": "string"},
                        "character_profiles": {"type": ["string", "array", "object"]},
                        "relationship_boundaries": {"type": ["string", "array", "object"]},
                        "lines_to_review": {"type": ["string", "array"]},
                    },
                    "required": ["lines_to_review"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_korean_naturalness_hints",
                "title": "Get Korean Naturalness Hints",
                "description": "Use this to get source-text-free hints for Korean grammar, idiom, translationese/post-editese, and spoken rhythm.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "lines_to_review": {"type": ["string", "array"]},
                    },
                    "required": ["lines_to_review"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_text_metrics",
                "title": "Get Text Metrics",
                "description": "Use this to get deterministic, source-text-free Korean dialogue length and byte metrics.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "lines_to_review": {"type": ["string", "array", "object"]},
                        "strip_speakers": {"type": "boolean", "default": True},
                    },
                    "required": ["lines_to_review"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_dataset_guidance",
                "title": "Get Dataset Guidance",
                "description": "Use this to get source-text-free guidance from the local private pattern bank.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "scene": {"type": "string"},
                        "medium": {"type": "string"},
                        "genre": {"type": "string"},
                        "character_profiles": {"type": ["string", "array", "object"]},
                        "relationship_boundaries": {"type": ["string", "array", "object"]},
                        "lines_to_review": {"type": ["string", "array"]},
                        "baseline_mode": {
                            "type": "string",
                            "enum": ["balanced", "raw"],
                            "default": "balanced",
                        },
                    },
                    "required": ["lines_to_review"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "prepare_dialogue_audit",
                "title": "Prepare Dialogue Audit",
                "description": "Use this to package user-provided scene, character, relationship, and lines with the Malmatch rubric.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "scene": {"type": "string"},
                        "medium": {"type": "string"},
                        "genre": {"type": "string"},
                        "character_profiles": {"type": ["string", "array", "object"]},
                        "relationship_boundaries": {"type": ["string", "array", "object"]},
                        "lines_to_review": {"type": ["string", "array"]},
                        "baseline_mode": {
                            "type": "string",
                            "enum": ["balanced", "raw"],
                            "default": "balanced",
                        },
                    },
                    "required": ["scene", "lines_to_review"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "validate_skillpack",
                "title": "Validate Skillpack",
                "description": "Use this to run read-only local checks for source-text field leakage and example shape.",
                "inputSchema": {"type": "object", "additionalProperties": False},
            },
        ]
    }


def resources_list_result() -> dict[str, Any]:
    resources = []
    for uri, (title, relative_path, mime_type) in RESOURCE_FILES.items():
        resources.append(
            {
                "uri": uri,
                "name": uri.removeprefix("malmatch://").replace("/", "."),
                "title": title,
                "description": f"Read-only skill-pack resource from {relative_path}.",
                "mimeType": mime_type,
            }
        )
    return {"resources": resources}


def resources_read_result(params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if uri not in RESOURCE_FILES:
        raise JsonRpcError(-32602, f"Unknown resource: {uri}")
    title, relative_path, mime_type = RESOURCE_FILES[uri]
    return {
        "contents": [
            {
                "uri": uri,
                "name": title,
                "mimeType": mime_type,
                "text": read_text(relative_path),
            }
        ]
    }


def prompts_list_result() -> dict[str, Any]:
    prompts = []
    for name, (title, _) in PROMPT_FILES.items():
        prompts.append(
            {
                "name": name,
                "title": title,
                "description": f"Template for {title.lower()} in Malmatch dialogue audits.",
                "arguments": [],
            }
        )
    return {"prompts": prompts}


def prompts_get_result(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    if name not in PROMPT_FILES:
        raise JsonRpcError(-32602, f"Unknown prompt: {name}")
    title, relative_path = PROMPT_FILES[name]
    return {
        "description": f"{title} prompt template.",
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": read_text(relative_path)},
            }
        ],
    }


def get_overview() -> dict[str, Any]:
    return {
        "name": SERVER_NAME,
        "version": SERVER_VERSION,
        "purpose": "Malmatch Korean character dialogue audit context provider for local MCP clients.",
        "workflow": [
            "Load character voice and relationship boundary context.",
            "Select the relevant prompt template.",
            "Apply the eight-axis rubric.",
            "Use balanced private pattern bank guidance when available.",
            "Use deterministic text metrics for line length and byte-budget checks.",
            "Use calibration hints for Korean politeness, relationship boundaries, and speech-level risk.",
            "Use synthetic examples only as compact pattern references.",
            "Return minimal rewrites that preserve meaning and character function.",
        ],
        "recommended_tools": [
            "get_rubric",
            "get_prompt_template",
            "prepare_dialogue_audit",
            "get_dataset_guidance",
            "get_text_metrics",
            "get_calibration_hints",
            "get_korean_naturalness_hints",
            "get_examples",
        ],
    }


def get_rubric(arguments: dict[str, Any]) -> dict[str, Any]:
    structured = {
        "score_range": {"min": 1, "max": 5},
        "axes": RUBRIC_AXES,
        "data_informed_defaults": [
            "Treat overly dense single-turn exposition as a naturalness and genre-fit risk.",
            "Evaluate character voice over a short scene, not only one isolated line.",
            "Use banmal, haeyoche, and hapsyoche as the primary speech-level axes.",
            "In Korean politeness contexts, check apology, acknowledgement, request softening, and power distance.",
            "Separate empathy from advice, overpromising, and relationship boundary crossing.",
        ],
        "resource_uri": "malmatch://docs/evaluation_rubric",
    }
    if arguments.get("include_full_text"):
        structured["full_text"] = read_text("docs/evaluation_rubric.md")
    return structured


def get_prompt_template(arguments: dict[str, Any]) -> dict[str, Any]:
    name = arguments.get("name")
    if name not in PROMPT_FILES:
        return {"error": f"Unknown prompt template: {name}", "allowed": list(PROMPT_FILES)}
    title, relative_path = PROMPT_FILES[name]
    return {"name": name, "title": title, "template": read_text(relative_path)}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("'\"") for part in inner.split(",")]
    return value


def load_examples() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in read_text("examples/good_bad_pairs.yaml").splitlines():
        if line.lstrip().startswith("- id:"):
            if current:
                examples.append(current)
            current = {"id": parse_scalar(line.split(":", 1)[1])}
            continue
        if current is None:
            continue
        match = re.match(r"^\s+([A-Za-z_]+):\s*(.*)$", line)
        if match:
            current[match.group(1)] = parse_scalar(match.group(2))
    if current:
        examples.append(current)
    return examples


def get_examples(arguments: dict[str, Any]) -> dict[str, Any]:
    category = arguments.get("category")
    limit = int(arguments.get("limit", 5))
    limit = max(1, min(limit, 30))
    examples = load_examples()
    if category:
        if category not in EXAMPLE_CATEGORIES:
            return {"error": f"Unknown category: {category}", "allowed": EXAMPLE_CATEGORIES}
        examples = [item for item in examples if item.get("category") == category]
    return {
        "count": min(limit, len(examples)),
        "total_matching": len(examples),
        "examples": examples[:limit],
        "notice": "Examples are synthetic pattern references.",
    }


def get_calibration_hints(arguments: dict[str, Any]) -> dict[str, Any]:
    lines_to_review = arguments.get("lines_to_review")
    if not lines_to_review:
        return {
            "error": "`lines_to_review` is required.",
            "required": ["lines_to_review"],
        }
    return build_calibration_hints(
        lines_to_review,
        profile_path=local_state_file("pattern_profile.json"),
        scene=str(arguments.get("scene", "")),
        medium=str(arguments.get("medium", "")),
        genre=str(arguments.get("genre", "")),
        character_profiles=arguments.get("character_profiles", ""),
        relationship_boundaries=arguments.get("relationship_boundaries", ""),
    )


def get_korean_naturalness_hints(arguments: dict[str, Any]) -> dict[str, Any]:
    lines_to_review = arguments.get("lines_to_review")
    if not lines_to_review:
        return {
            "error": "`lines_to_review` is required.",
            "required": ["lines_to_review"],
        }
    return build_korean_naturalness_hints(lines_to_review)


def get_text_metrics(arguments: dict[str, Any]) -> dict[str, Any]:
    lines_to_review = arguments.get("lines_to_review")
    if not lines_to_review:
        return {
            "error": "`lines_to_review` is required.",
            "required": ["lines_to_review"],
        }
    return build_text_metrics(
        lines_to_review,
        strip_speakers=bool(arguments.get("strip_speakers", True)),
    )


def get_dataset_guidance(arguments: dict[str, Any]) -> dict[str, Any]:
    lines_to_review = arguments.get("lines_to_review")
    if not lines_to_review:
        return {
            "error": "`lines_to_review` is required.",
            "required": ["lines_to_review"],
        }
    return build_dataset_guidance(
        bank_path=local_state_file("private_pattern_bank.json"),
        scene=str(arguments.get("scene", "")),
        medium=str(arguments.get("medium", "")),
        genre=str(arguments.get("genre", "")),
        character_profiles=arguments.get("character_profiles", ""),
        relationship_boundaries=arguments.get("relationship_boundaries", ""),
        lines_to_review=lines_to_review,
        baseline_mode=str(arguments.get("baseline_mode", "balanced")),
    )


def prepare_dialogue_audit(arguments: dict[str, Any]) -> dict[str, Any]:
    scene = arguments.get("scene")
    lines_to_review = arguments.get("lines_to_review")
    if not scene or not lines_to_review:
        return {
            "error": "Both `scene` and `lines_to_review` are required.",
            "required": ["scene", "lines_to_review"],
        }
    text_metrics = get_text_metrics({"lines_to_review": lines_to_review})
    calibration_hints = get_calibration_hints(arguments)
    korean_naturalness_hints = get_korean_naturalness_hints(arguments)
    dataset_guidance = get_dataset_guidance(arguments)
    return {
        "task": "korean_dialogue_audit",
        "provided_input": {
            "scene": scene,
            "medium": arguments.get("medium", "unspecified"),
            "genre": arguments.get("genre", "unspecified"),
            "character_profiles": arguments.get("character_profiles", ""),
            "relationship_boundaries": arguments.get("relationship_boundaries", ""),
            "lines_to_review": lines_to_review,
        },
        "rubric_axes": RUBRIC_AXES,
        "recommended_prompt": "dialogue_audit",
        "prompt_template": read_text("prompts/dialogue_audit.md"),
        "output_schema_uri": "malmatch://schemas/evaluation_result",
        "calibration_schema_uri": "malmatch://schemas/calibration_hint",
        "korean_naturalness_schema_uri": "malmatch://schemas/korean_naturalness_hint",
        "text_metrics_schema_uri": "malmatch://schemas/text_metrics",
        "dataset_guidance_schema_uri": "malmatch://schemas/dataset_guidance",
        "text_metrics": text_metrics,
        "dataset_guidance": dataset_guidance,
        "calibration_hints": calibration_hints,
        "korean_naturalness_hints": korean_naturalness_hints,
        "guidance": [
            "Score all eight axes from 1 to 5.",
            "Use dataset guidance as the first source of private-bank baseline context when bank_loaded is true.",
            "Use Korean naturalness hints to inspect grammar, native idiom, and spoken rhythm under naturalness.",
            "Use calibration hints to inspect Korean politeness buffers, directness, and power distance under relationship_fit.",
            "Identify only issues grounded in the provided user lines and skill-pack rubric.",
            "Suggest minimal rewrites that preserve meaning, role, and relationship.",
            "Treat calibration hints as soft signals, not final scores.",
            "Use synthetic examples only as compact pattern references.",
        ],
    }


def validate_skillpack() -> dict[str, Any]:
    command = [
        sys.executable,
        str(CODE_ROOT / "tools" / "check_no_source_text.py"),
        "--paths",
        "README.md",
        "docs/evaluation_rubric.md",
        "docs/usage.md",
        "docs/mcp_usage.md",
        "skills",
        "prompts",
        "schemas",
        "examples",
        "sample_project",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    examples = load_examples()
    rubric_text = read_text("docs/evaluation_rubric.md")
    missing_axes = [
        axis
        for axis in [
            "Naturalness",
            "Character Fit",
            "Relationship Fit",
            "Speech Level Consistency",
            "Humor Timing",
            "Cringe Risk",
            "Anachronism Risk",
            "Genre Fit",
        ]
        if axis not in rubric_text
    ]
    ok = completed.returncode == 0 and len(examples) == 30 and not missing_axes
    return {
        "ok": ok,
        "source_text_check_returncode": completed.returncode,
        "source_text_check_stdout": completed.stdout.strip(),
        "source_text_check_stderr": completed.stderr.strip(),
        "example_count": len(examples),
        "missing_rubric_axes": missing_axes,
    }


TOOL_HANDLERS = {
    "get_skillpack_overview": lambda args: get_overview(),
    "get_rubric": get_rubric,
    "get_prompt_template": get_prompt_template,
    "get_examples": get_examples,
    "get_calibration_hints": get_calibration_hints,
    "get_korean_naturalness_hints": get_korean_naturalness_hints,
    "get_text_metrics": get_text_metrics,
    "get_dataset_guidance": get_dataset_guidance,
    "prepare_dialogue_audit": prepare_dialogue_audit,
    "validate_skillpack": lambda args: validate_skillpack(),
}


def call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if name not in TOOL_HANDLERS:
        raise JsonRpcError(-32602, f"Unknown tool: {name}")
    if not isinstance(arguments, dict):
        return tool_result({"error": "`arguments` must be an object."}, is_error=True)
    structured = TOOL_HANDLERS[name](arguments)
    is_error = isinstance(structured, dict) and "error" in structured
    return tool_result(structured, is_error=is_error)


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(params, dict):
        raise JsonRpcError(-32602, "`params` must be an object when provided.")

    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return success(request_id, initialize_result())
    if method == "ping":
        return success(request_id, {})
    if method == "tools/list":
        return success(request_id, tools_list_result())
    if method == "tools/call":
        return success(request_id, call_tool(params))
    if method == "resources/list":
        return success(request_id, resources_list_result())
    if method == "resources/templates/list":
        return success(request_id, {"resourceTemplates": []})
    if method == "resources/read":
        return success(request_id, resources_read_result(params))
    if method == "prompts/list":
        return success(request_id, prompts_list_result())
    if method == "prompts/get":
        return success(request_id, prompts_get_result(params))

    raise JsonRpcError(-32601, f"Method not found: {method}")


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        request_id: Any = None
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise JsonRpcError(-32600, "Request must be a JSON object.")
            request_id = message.get("id")
            response = handle_request(message)
            if response is not None and request_id is not None:
                write_response(response)
        except json.JSONDecodeError as exc:
            write_response(error_response(request_id, -32700, f"Parse error: {exc.msg}"))
        except JsonRpcError as exc:
            write_response(error_response(request_id, exc.code, exc.message))
        except Exception as exc:  # pragma: no cover - defensive server boundary
            print(f"Unexpected MCP server error: {exc}", file=sys.stderr)
            write_response(error_response(request_id, -32603, "Internal error"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

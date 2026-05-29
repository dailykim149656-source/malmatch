#!/usr/bin/env python3
"""Smoke tests for the local stdio MCP server."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "tools" / "korean_character_voice_mcp.py"
BANK = ROOT / ".malmatch" / "private_pattern_bank.json"
LEGACY_BANK = ROOT / ".omx" / "private_pattern_bank.json"


FIXTURE_BANK = {
    "schema": "private_pattern_bank",
    "version": "0.1",
    "policy": {"stored_text": False, "source_text_values": "omitted"},
    "coverage": {"utterance_count": 100},
    "global_baselines": {"avg_chars": 24.0, "max_chars": 140},
    "context_baselines": {
        "customer_complaint": {
            "utterance_count": 40,
            "marker_rates": {"apology": 0.35, "polite_buffer": 0.45},
        },
        "formal_first_meeting": {
            "utterance_count": 30,
            "marker_rates": {"polite_buffer": 0.4},
        },
    },
    "raw_global_baselines": {"avg_chars": 24.0, "max_chars": 140},
    "raw_context_baselines": {
        "customer_complaint": {
            "utterance_count": 40,
            "marker_rates": {"apology": 0.35, "polite_buffer": 0.45},
        },
        "formal_first_meeting": {
            "utterance_count": 30,
            "marker_rates": {"polite_buffer": 0.4},
        },
    },
    "balanced_baselines": {
        "dataset_count": 2,
        "utterance_count_raw": 100,
        "global_baselines": {"avg_chars": 18.0, "max_chars": 120},
        "context_baselines": {
            "customer_complaint": {
                "utterance_count": 40,
                "dataset_count": 2,
                "marker_rates": {"apology": 0.5, "polite_buffer": 0.6},
            },
            "formal_first_meeting": {
                "utterance_count": 30,
                "dataset_count": 2,
                "marker_rates": {"polite_buffer": 0.55},
            },
        },
    },
}


class McpClient:
    def __init__(self) -> None:
        self.next_id = 1
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.process.stdin or not self.process.stdout:
            raise RuntimeError("MCP server pipes are not available")
        request_id = self.next_id
        self.next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise AssertionError(f"No response from MCP server. stderr={stderr!r}")
        response = json.loads(line)
        assert response.get("id") == request_id, response
        return response

    def request_raw(self, raw_line: str) -> dict[str, Any]:
        if not self.process.stdin or not self.process.stdout:
            raise RuntimeError("MCP server pipes are not available")
        self.process.stdin.write(raw_line + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise AssertionError(f"No response from MCP server. stderr={stderr!r}")
        return json.loads(line)


def assert_result(response: dict[str, Any]) -> dict[str, Any]:
    assert "error" not in response, response
    assert "result" in response, response
    return response["result"]


def assert_error(response: dict[str, Any], code: int) -> None:
    assert response.get("error", {}).get("code") == code, response


def call_tool(client: McpClient, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    result = assert_result(
        client.request("tools/call", {"name": name, "arguments": arguments or {}})
    )
    assert "structuredContent" in result, result
    return result["structuredContent"]


def remove_bank_for_missing_case() -> dict[Path, str | None]:
    backups: dict[Path, str | None] = {}
    for path in [BANK, LEGACY_BANK]:
        if path.exists():
            backups[path] = path.read_text(encoding="utf-8")
            path.unlink()
        else:
            backups[path] = None
    return backups


def write_fixture_bank() -> None:
    BANK.parent.mkdir(parents=True, exist_ok=True)
    BANK.write_text(json.dumps(FIXTURE_BANK, ensure_ascii=False), encoding="utf-8")


def restore_bank(backups: dict[Path, str | None]) -> None:
    for path, backup in backups.items():
        if backup is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(backup, encoding="utf-8")


def main() -> int:
    bank_backup = remove_bank_for_missing_case()
    client = McpClient()
    try:
        init = assert_result(
            client.request(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "stdio-smoke-test", "version": "0.1"},
                },
            )
        )
        assert init["protocolVersion"] == "2025-11-25"
        assert init["serverInfo"]["name"] == "malmatch"
        assert set(init["capabilities"]) >= {"tools", "resources", "prompts"}

        tools = assert_result(client.request("tools/list"))["tools"]
        tool_names = {tool["name"] for tool in tools}
        assert "get_rubric" in tool_names
        assert "get_calibration_hints" in tool_names
        assert "get_korean_naturalness_hints" in tool_names
        assert "get_text_metrics" in tool_names
        assert "get_dataset_guidance" in tool_names
        assert "prepare_dialogue_audit" in tool_names

        rubric = call_tool(client, "get_rubric")
        assert "naturalness" in rubric["axes"]

        resources = assert_result(client.request("resources/list"))["resources"]
        resource_uris = {resource["uri"] for resource in resources}
        assert "malmatch://docs/evaluation_rubric" in resource_uris
        assert "malmatch://schemas/evaluation_result" in resource_uris
        assert "malmatch://schemas/calibration_hint" in resource_uris
        assert "malmatch://schemas/korean_naturalness_hint" in resource_uris
        assert "malmatch://schemas/text_metrics" in resource_uris
        assert "malmatch://schemas/dataset_guidance" in resource_uris

        resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/evaluation_result"})
        )
        assert "contents" in resource
        evaluation_schema_text = resource["contents"][0]["text"]
        assert "evaluation_result" in evaluation_schema_text
        for field_name in ["category", "severity", "scope", "source", "signal_ids"]:
            assert field_name in evaluation_schema_text

        calibration_resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/calibration_hint"})
        )
        assert "calibration_hints" in calibration_resource["contents"][0]["text"]

        naturalness_resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/korean_naturalness_hint"})
        )
        assert "korean_naturalness_hints" in naturalness_resource["contents"][0]["text"]

        text_metrics_resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/text_metrics"})
        )
        assert "text_metrics" in text_metrics_resource["contents"][0]["text"]

        dataset_guidance_resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/dataset_guidance"})
        )
        assert "dataset_guidance" in dataset_guidance_resource["contents"][0]["text"]

        prompts = assert_result(client.request("prompts/list"))["prompts"]
        prompt_names = {prompt["name"] for prompt in prompts}
        assert "dialogue_audit" in prompt_names

        prompt = assert_result(client.request("prompts/get", {"name": "dialogue_audit"}))
        assert prompt["messages"][0]["content"]["type"] == "text"

        calibration = call_tool(
            client,
            "get_calibration_hints",
            {
                "scene": "Synthetic formal customer scene",
                "relationship_boundaries": "formal first meeting",
                "lines_to_review": [
                    "A: 고객님, 지금 처리하겠습니다.",
                    "B: 야, 너 진짜 운명이야.",
                ],
            },
        )
        assert calibration["schema"] == "calibration_hints"
        assert calibration["basis"]["stored_text"] is False
        assert "hints" in calibration
        assert "signal_catalog" in calibration

        text_metrics = call_tool(
            client,
            "get_text_metrics",
            {"lines_to_review": ["A: 비공개 원문 조각입니다"]},
        )
        assert text_metrics["schema"] == "text_metrics"
        assert text_metrics["basis"]["stored_text"] is False
        assert text_metrics["total_utf8_bytes"] > 0
        assert "비공개 원문" not in json.dumps(text_metrics, ensure_ascii=False)

        korean_naturalness = call_tool(
            client,
            "get_korean_naturalness_hints",
            {
                "lines_to_review": [
                    "A: 저는 그것은 좋은 결정이라고 생각합니다.",
                    "B: 그리고 그리고 좋은 시간을 보내.",
                ],
            },
        )
        assert korean_naturalness["schema"] == "korean_naturalness_hints"
        assert korean_naturalness["basis"]["stored_text"] is False
        assert "native_korean_idiom" in {
            hint["axis"] for hint in korean_naturalness["hints"]
        }
        assert "duplicate_connective" in korean_naturalness["signal_catalog"]
        assert korean_naturalness["input_metrics"]["text_metrics"]["schema"] == "text_metrics"

        missing_dataset_guidance = call_tool(
            client,
            "get_dataset_guidance",
            {
                "scene": "고객이 환불 문제로 항의하는 상황",
                "relationship_boundaries": "초면, 공식, 고객",
                "lines_to_review": ["A: 안됩니다."],
            },
        )
        assert missing_dataset_guidance["schema"] == "dataset_guidance"
        assert missing_dataset_guidance["bank_loaded"] is False

        write_fixture_bank()
        dataset_guidance = call_tool(
            client,
            "get_dataset_guidance",
            {
                "scene": "고객이 환불 문제로 항의하는 상황",
                "relationship_boundaries": "초면, 공식, 고객",
                "lines_to_review": ["A: 안됩니다."],
            },
        )
        assert dataset_guidance["bank_loaded"] is True
        assert dataset_guidance["baseline_mode"] == "balanced"
        assert dataset_guidance["baseline_source"] == "balanced_baselines"
        assert "customer_complaint_refusal" in {
            item["signal"] for item in dataset_guidance["guidance"]
        }

        audit_package = call_tool(
            client,
            "prepare_dialogue_audit",
            {
                "scene": "Synthetic test scene",
                "medium": "game_dialogue",
                "genre": "mystery",
                "character_profiles": "calm observer",
                "relationship_boundaries": "growing friends",
                "lines_to_review": ["A: 너무 길게 설명하는 대사입니다."],
            },
        )
        assert audit_package["provided_input"]["scene"] == "Synthetic test scene"
        assert audit_package["recommended_prompt"] == "dialogue_audit"
        assert "naturalness" in audit_package["rubric_axes"]
        assert audit_package["calibration_schema_uri"] == "malmatch://schemas/calibration_hint"
        assert (
            audit_package["korean_naturalness_schema_uri"]
            == "malmatch://schemas/korean_naturalness_hint"
        )
        assert audit_package["text_metrics_schema_uri"] == "malmatch://schemas/text_metrics"
        assert audit_package["text_metrics"]["schema"] == "text_metrics"
        assert audit_package["calibration_hints"]["schema"] == "calibration_hints"
        assert audit_package["korean_naturalness_hints"]["schema"] == "korean_naturalness_hints"
        assert audit_package["dataset_guidance"]["schema"] == "dataset_guidance"
        assert audit_package["dataset_guidance"]["bank_loaded"] is True
        assert audit_package["dataset_guidance"]["baseline_mode"] == "balanced"

        validation = call_tool(client, "validate_skillpack")
        assert validation["ok"] is True, validation

        assert_error(client.request("unknown/method"), -32601)
        assert_error(
            client.request("resources/read", {"uri": "malmatch://missing/resource"}), -32602
        )
        assert_error(
            client.request("tools/call", {"name": "missing_tool", "arguments": {}}), -32602
        )

        non_object = client.request_raw("[1, 2, 3]")
        assert_error(non_object, -32600)
        assert non_object.get("id") is None, non_object
    finally:
        client.close()
        restore_bank(bank_backup)

    print("MCP stdio smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


def main() -> int:
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
        assert "prepare_dialogue_audit" in tool_names

        rubric = call_tool(client, "get_rubric")
        assert "naturalness" in rubric["axes"]

        resources = assert_result(client.request("resources/list"))["resources"]
        resource_uris = {resource["uri"] for resource in resources}
        assert "malmatch://docs/evaluation_rubric" in resource_uris
        assert "malmatch://schemas/calibration_hint" in resource_uris
        assert "malmatch://schemas/korean_naturalness_hint" in resource_uris

        resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/evaluation_result"})
        )
        assert "contents" in resource
        assert "evaluation_result" in resource["contents"][0]["text"]

        calibration_resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/calibration_hint"})
        )
        assert "calibration_hints" in calibration_resource["contents"][0]["text"]

        naturalness_resource = assert_result(
            client.request("resources/read", {"uri": "malmatch://schemas/korean_naturalness_hint"})
        )
        assert "korean_naturalness_hints" in naturalness_resource["contents"][0]["text"]

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

        korean_naturalness = call_tool(
            client,
            "get_korean_naturalness_hints",
            {
                "lines_to_review": [
                    "A: 나는은 이것은 좋은 결정이라고 생각한다.",
                    "B: 좋은 시간을 보내.",
                ],
            },
        )
        assert korean_naturalness["schema"] == "korean_naturalness_hints"
        assert korean_naturalness["basis"]["stored_text"] is False
        assert "native_korean_idiom" in {
            hint["axis"] for hint in korean_naturalness["hints"]
        }
        assert "duplicate_particle_sequence" in korean_naturalness["signal_catalog"]

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
        assert audit_package["calibration_hints"]["schema"] == "calibration_hints"
        assert audit_package["korean_naturalness_hints"]["schema"] == "korean_naturalness_hints"

        validation = call_tool(client, "validate_skillpack")
        assert validation["ok"] is True, validation

        assert_error(client.request("unknown/method"), -32601)
        assert_error(
            client.request("resources/read", {"uri": "malmatch://missing/resource"}), -32602
        )
        assert_error(
            client.request("tools/call", {"name": "missing_tool", "arguments": {}}), -32602
        )
    finally:
        client.close()

    print("MCP stdio smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

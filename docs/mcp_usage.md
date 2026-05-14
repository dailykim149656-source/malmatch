# Malmatch Local MCP Usage

말매치 Malmatch includes a local stdio MCP server for Codex, Claude Code, and other MCP clients that can launch a subprocess.

## What The Server Does

- Exposes the Malmatch Korean character dialogue rubric as a tool and resource.
- Exposes prompt templates from `prompts/`.
- Exposes schemas and synthetic examples as read-only resources.
- Packages user-provided scene, character, relationship, and dialogue lines into an audit context.
- Runs a read-only validation check for public-source-text leakage.

The server does not call an LLM, score dialogue by itself, or expose raw AI Hub/NIKL dataset folders.

## Run Directly

```bash
python <REPO_PATH>/tools/korean_character_voice_mcp.py
```

The process expects newline-delimited JSON-RPC messages on stdin and writes JSON-RPC responses to stdout.

## MCP Client Configuration

Use this command and args in a local MCP client:

```json
{
  "mcpServers": {
    "malmatch": {
      "command": "python",
      "args": [
        "<REPO_PATH>\\tools\\korean_character_voice_mcp.py"
      ]
    }
  }
}
```

## Recommended Tool Flow

1. Call `get_skillpack_overview`.
2. Call `get_rubric`.
3. Call `get_prompt_template` with `dialogue_audit` or a narrower template.
4. Call `get_calibration_hints` when you need length, speech-level, relationship, or Korean politeness-context signals.
5. Call `get_korean_naturalness_hints` when you need grammar, translationese, or spoken-rhythm signals.
6. Call `prepare_dialogue_audit` with the user-provided scene and lines.
7. Optionally call `get_examples` for synthetic pattern references.

## Available Tools

- `get_skillpack_overview`
- `get_rubric`
- `get_prompt_template`
- `get_examples`
- `get_calibration_hints`
- `get_korean_naturalness_hints`
- `prepare_dialogue_audit`
- `validate_skillpack`

## Smoke Test

```bash
python tools/test_mcp_stdio.py
```

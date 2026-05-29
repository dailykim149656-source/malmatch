# Malmatch Local MCP Usage

말매치 Malmatch includes a local stdio MCP server for Codex, Claude Code, and other MCP clients that can launch a subprocess.

The examples below use `python`. On macOS and most Linux distributions only `python3` exists, so substitute `python3` for `python` in both the shell commands and the MCP client `command` field. Path separators are written with `/`, which works on Windows and macOS/Linux alike.

## What The Server Does

- Exposes the Malmatch Korean character dialogue rubric as a tool and resource.
- Exposes prompt templates from `prompts/`.
- Exposes schemas and synthetic examples as read-only resources.
- Reads `.malmatch/private_pattern_bank.json` when present and returns source-text-free dataset guidance.
- Returns deterministic local text metrics for NFC character counts, whitespace-free counts, UTF-8 bytes, and NEIS-style bytes.
- Packages user-provided scene, character, relationship, and dialogue lines into an audit context.
- Runs a read-only validation check for public-source-text leakage.

The server does not call an LLM, score dialogue by itself, expose raw AI Hub/NIKL dataset folders, or expose the private pattern bank as an MCP resource.

## Run Directly

```bash
python <REPO_PATH>/tools/korean_character_voice_mcp.py
```

The process expects newline-delimited JSON-RPC messages on stdin and writes JSON-RPC responses to stdout.

## Optional Editable Install

For local development or a local MCP client, install the repository in editable mode:

```bash
python -m pip install -e <REPO_PATH>
```

Then use the console entry point:

```bash
malmatch-mcp
```

The direct script path remains supported and is the most explicit option for clients that prefer absolute Python script paths.

## MCP Client Configuration

Use this command and args in a local MCP client:

```json
{
  "mcpServers": {
    "malmatch": {
      "command": "python",
      "args": [
        "<REPO_PATH>/tools/korean_character_voice_mcp.py"
      ]
    }
  }
}
```

After editable install, this shorter form is also available:

```json
{
  "mcpServers": {
    "malmatch": {
      "command": "malmatch-mcp",
      "args": []
    }
  }
}
```

## Recommended Tool Flow

1. Call `get_skillpack_overview`.
2. Call `get_rubric`.
3. Call `get_prompt_template` with `dialogue_audit` or a narrower template.
4. Call `get_dataset_guidance` when `.malmatch/private_pattern_bank.json` exists and you need dataset-informed context. The default `baseline_mode` is `balanced`; use `raw` only when you want unweighted aggregate frequencies.
5. Call `get_text_metrics` when you need a stable local line-length or byte-budget contract.
6. Call `get_calibration_hints` when you need length, speech-level, relationship, or Korean politeness-context signals.
7. Call `get_korean_naturalness_hints` when you need grammar, spelling/spacing, translationese/post-editese, or spoken-rhythm signals.
   Use `signal_metadata` to prioritize triggered signals by category, severity, and line/scene scope.
8. Call `prepare_dialogue_audit` with the user-provided scene and lines.
   In the final `evaluation_result`, copy only signal IDs and optional `category`, `severity`, `scope`, `source` metadata into findings; do not copy source lines into metadata.
9. Optionally call `get_examples` for compact synthetic pattern references.

## Private Pattern Bank

Create the local bank before using dataset guidance:

```bash
python tools/dataset_inventory.py --root . --out .malmatch/data_inventory.json
python tools/build_private_pattern_bank.py --inventory .malmatch/data_inventory.json --out .malmatch/private_pattern_bank.json
```

The default builder performs a full zip-entry scan. For a faster smoke run, add `--max-entries-per-zip 500`.
The generated bank stays local under `.malmatch/` and is not exposed as an MCP resource.
Do not publish raw datasets, `.malmatch/data_inventory.json`, `.malmatch/pattern_profile.json`, or `.malmatch/private_pattern_bank.json`; see [Dataset Distribution](dataset_distribution.md).

## Available Tools

- `get_skillpack_overview`
- `get_rubric`
- `get_prompt_template`
- `get_examples`
- `get_dataset_guidance`
- `get_text_metrics`
- `get_calibration_hints`
- `get_korean_naturalness_hints`
- `prepare_dialogue_audit`
- `validate_skillpack`

## Smoke Test

```bash
python tools/run_tests.py
```

For only the stdio MCP smoke test:

```bash
python tools/test_mcp_stdio.py
```

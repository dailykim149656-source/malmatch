# Dialogue Audit Prompt

아래 입력을 기준으로 한국어 캐릭터 대사를 검수하세요.
원문의 의미는 유지하고, 수정은 필요한 부분만 제안하세요.

## Input

- Scene:
- Medium:
- Genre:
- Character profiles:
- Relationship boundaries:
- Lines to review:

## Output Format

- Scores:
  - naturalness:
  - character_fit:
  - relationship_fit:
  - speech_level_consistency:
  - humor_timing:
  - cringe_risk:
  - anachronism_risk:
  - genre_fit:
- Findings:
  - line_ref:
    category:
    severity:
    scope:
    source:
    signal_ids:
    issue:
    reason:
    risk_tags:
    suggested_action:
  - Dataset guidance:
    - matched_contexts:
    - dataset_signals:
  - Korean naturalness:
    - grammar_acceptability:
    - native_korean_idiom:
    - spoken_korean_rhythm:
  - Korean politeness context:
    - politeness_buffer:
    - directness:
    - power_distance:
- Rewrite suggestion:
- Keep unchanged:

## Finding Metadata

- `category`, `severity`, `scope`, `source`, `signal_ids`는 선택 필드입니다.
- MCP 힌트의 `signal_metadata`가 있으면 같은 `category`, `severity`, `scope`를 재사용하세요.
- `signal_ids`에는 트리거된 신호 ID만 넣고, 원문 문장이나 교정문 전문은 복사하지 마세요.

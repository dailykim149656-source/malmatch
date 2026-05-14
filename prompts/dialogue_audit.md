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

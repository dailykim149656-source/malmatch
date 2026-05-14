# Malmatch Usage

말매치 Malmatch는 한국어 캐릭터 대사의 말맛, 관계성, 어체를 점검하는 로컬 MCP 스킬팩입니다.

## 1. 캐릭터와 관계를 먼저 고정한다

`schemas/voice_profile.schema.yaml`과 `schemas/relationship_boundary.schema.yaml`을 참고해
캐릭터의 기본 어체, 말 길이, 감정 노출 정도, 관계 허용선을 적습니다.

## 2. 장면 단위로 검사한다

한 줄만 보지 말고 6턴에서 20턴 정도의 짧은 장면을 기준으로 봅니다.
페르소나와 공감형 대화의 집계가 이 범위의 반복 패턴을 많이 포함했기 때문입니다.

## 3. 프롬프트를 고른다

- 전체 대사 검수: `prompts/dialogue_audit.md`
- 한국어 자연스러움: `prompts/korean_naturalness_check.md`
- 농담 적합성: `prompts/humor_pass.md`
- 가벼운 수정: `prompts/rewrite_lightly.md`
- 캐릭터 drift: `prompts/character_voice_check.md`
- 어체 일관성: `prompts/speech_level_check.md`
- 오글거림 위험: `prompts/cringe_risk_check.md`

## 4. 결과를 스키마에 맞춘다

검수 결과는 `schemas/evaluation_result.schema.yaml`의 필드를 사용합니다.
점수는 1점에서 5점 사이 정수로 쓰고, 수정 제안은 원문의 의미를 크게 바꾸지 않는 범위로 제한합니다.

## 5. 보정 힌트는 참고 신호로만 쓴다

MCP의 `prepare_dialogue_audit`, `get_calibration_hints`, `get_korean_naturalness_hints`는
길이, 어체 혼합, 관계선, 예의 맥락, 문법성, 번역투, 구어 리듬 위험 같은 로컬 보정 힌트를 함께 반환할 수 있습니다.
이 힌트는 최종 점수가 아니라 검토 우선순위를 잡기 위한 참고 신호입니다.

## 6. 예시는 직접 확장한다

`examples/good_bad_pairs.yaml`은 합성 예시입니다.
프로젝트에서 추가할 때도 같은 필드를 유지하고, 원문 데이터셋 문장을 복사하지 않습니다.

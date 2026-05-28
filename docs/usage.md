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
각 finding에는 선택적으로 `category`, `severity`, `scope`, `source`, `signal_ids`를 붙일 수 있습니다.
MCP 힌트가 제공한 `signal_metadata`가 있으면 같은 분류를 재사용해 검토 우선순위를 맞추고, 이 메타데이터에도 원문 문장이나 교정문 전문은 넣지 않습니다.

## 5. 보정 힌트는 참고 신호로만 쓴다

MCP의 `prepare_dialogue_audit`, `get_dataset_guidance`, `get_text_metrics`, `get_calibration_hints`, `get_korean_naturalness_hints`는
데이터셋 기준, NFC 문자 수, UTF-8/NEIS식 바이트, 어체 혼합, 관계선, 예의 맥락, 문법성, 맞춤법/띄어쓰기 후보, 번역투/post-editese, 구어 리듬 위험 같은 로컬 보정 힌트를 함께 반환할 수 있습니다.
이 힌트는 최종 점수가 아니라 검토 우선순위를 잡기 위한 참고 신호입니다.

길이 판단은 단순 `len()` 추정이 아니라 `schemas/text_metrics.schema.yaml`의 계약을 따릅니다.
맞춤법/문법 힌트는 외부 검사기 없이 로컬 규칙으로 후보만 표시하며, 원문과 교정문 전문을 응답 산출물에 저장하지 않습니다.
번역투/post-editese 힌트도 대명사 직역, 이중 피동, 이중 조사, 긴 관형절, 반복 진행형, 결산 접속 표지 같은 신호의 ID와 라인 번호만 반환합니다.
트리거된 신호의 `signal_metadata`에는 category, severity, scope가 들어 있어 클라이언트가 먼저 볼 항목을 정렬할 수 있습니다.

`get_examples`는 작은 합성 패턴 카드로만 사용합니다. 많은 예시를 추가하기보다
로컬 데이터셋에서 `.malmatch/private_pattern_bank.json`을 만들고 `get_dataset_guidance`를 우선 사용합니다.
기본 보정 기준은 `balanced`이며, 데이터셋별 통계를 같은 가중치로 평균 내 큰 데이터셋 편향을 줄입니다.
전체 raw 빈도 자체가 필요할 때만 `baseline_mode: "raw"`를 사용합니다.

## 6. 예시는 직접 확장한다

`examples/good_bad_pairs.yaml`은 합성 예시입니다.
프로젝트에서 추가할 때도 같은 필드를 유지하고, 원문 데이터셋 문장을 복사하지 않습니다.

## 7. 데이터셋 산출물은 로컬에만 둔다

AI Hub 등에서 받은 원본 데이터와 `.malmatch/*.json` 내부 분석 산출물은 공개 repo, 릴리스, 패키지에 포함하지 않습니다.
데이터셋 기반 설계의 공개 배포 기준은 [데이터셋 사용과 공개 배포 원칙](dataset_distribution.md)을 따릅니다.

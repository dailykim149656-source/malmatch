# Sample Audit Result

## Scores

- naturalness: 4
- character_fit: 5
- relationship_fit: 4
- speech_level_consistency: 4
- humor_timing: 4
- cringe_risk: 5
- anachronism_risk: 5
- genre_fit: 4

## Findings

- line_ref: 1-5
  category: character_fit
  severity: low
  scope: scene
  source: rubric
  signal_ids: []
  issue: `calm_student`는 짧고 관찰 중심으로 말해 프로필과 맞는다.
  reason: 감정 설명보다 상황 관찰을 우선하는 보이스가 유지된다.
  risk_tags: []
  suggested_action: 유지한다.
- line_ref: 1-5
  category: relationship_fit
  severity: low
  scope: scene
  source: rubric
  signal_ids: []
  issue: 두 인물의 어체 차이가 관계 설정상 의도된 대비로 보인다.
  reason: 거리감과 친밀감의 차이가 장면 기능을 해치지 않는다.
  risk_tags: []
  suggested_action: 유지하되 다음 장면에서 급격한 호칭 변화만 확인한다.
- line_ref: 1-5
  category: humor_timing
  severity: medium
  scope: scene
  source: rubric
  signal_ids: []
  issue: 장면이 단서 확인 중심이라 농담을 더 넣으면 긴장이 풀릴 수 있다.
  reason: 정보 확인 턴에서는 반응보다 단서 전달의 밀도가 우선이다.
  risk_tags: [tone_drift]
  suggested_action: 농담 추가 없이 현재 리듬을 유지한다.

## Rewrite Suggestion

현재 장면은 큰 수정 없이 유지한다.
다음 턴에서 설명이 길어지면 단서를 두 문장으로 나누는 것이 좋다.

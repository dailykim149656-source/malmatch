# Korean Dialogue Audit

## Purpose

AI가 만든 한국어 대사가 장면, 캐릭터, 관계, 매체에 맞는지 평가합니다.

## Inputs

- 장면 설명
- 캐릭터 보이스 프로필
- 관계 경계
- 검수할 대사 목록
- 장르와 매체

## Checks

- Naturalness: 문법성, 한국어다운 표현, 구어 리듬, 설명 과잉
- Character Fit: 말 길이, 감정 노출, 단어 선택
- Relationship Fit: 친밀도, 권력 거리, 장난 허용선
- Speech Level Consistency: 반말, 해요체, 합쇼체, 반존대
- Humor Timing: 긴장감과 반응 타이밍
- Cringe Risk: 자기 설명, 과장, 작위성
- Anachronism Risk: 시대감과 세계관 충돌
- Genre Fit: 게임 선택지, 말풍선, 챗봇 턴 밀도

## Output

`schemas/evaluation_result.schema.yaml` 형식으로 점수와 근거, 수정 제안을 반환합니다.
MCP 힌트나 루브릭 축이 근거가 되는 finding에는 `category`, `severity`, `scope`, `source`, `signal_ids`를 선택적으로 붙입니다.
원문 문장이나 교정문 전문은 메타데이터에 복사하지 않습니다.

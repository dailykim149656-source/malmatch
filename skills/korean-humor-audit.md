# Korean Humor Audit

## Purpose

농담을 더 많이 만들기보다, 지금 농담이 장면과 관계에 맞는지 판단합니다.

## Checks

- 이 캐릭터가 할 법한 농담인가
- 이 관계에서 허용되는 강도인가
- 감정 장면을 가볍게 덮지 않는가
- 설명보다 반응으로 처리하는 편이 나은가
- 최신 밈이나 특정 플랫폼 말투에 기대지 않는가

## Decision Labels

- `keep`: 그대로 둔다
- `soften`: 강도를 낮춘다
- `remove`: 농담을 제거한다
- `replace_with_reaction`: 농담 대신 짧은 반응으로 바꾼다


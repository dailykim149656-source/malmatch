![말매치 Malmatch logo](./assets/malmatch-logo.png)

# 말매치 Malmatch

말매치 Malmatch는 한국어 캐릭터 대사를 검수하기 위한 로컬 MCP 스킬팩입니다.
대사를 생성하는 모델이 아니라, Codex, Claude Code, Claude Desktop 같은 MCP 클라이언트가 참고할 루브릭, 프롬프트, 스키마, 합성 예시, 보정 힌트를 제공합니다.

## 언제 쓰나요

- 캐릭터 말투가 장면마다 흔들리는지 확인할 때
- 반말, 존댓말, 반존대가 관계와 상황에 맞는지 볼 때
- 초면, 고객 응대, 상하 관계에서 사과, 양해, 부탁의 예의 맥락이 맞는지 볼 때
- 문법 오류, 번역투, 한국인답지 않은 구어 표현을 잡고 싶을 때
- 위로, 조언, 농담, 고백, 갈등 대사가 과하거나 어색한지 점검할 때
- 게임, 웹툰, 챗봇, 소설 대사의 길이와 밀도를 다듬을 때

## 타겟 이용자

- 게임, 웹툰, 웹소설, 인터랙티브 스토리의 작가와 내러티브 디자이너
- AI NPC, 캐릭터 챗봇, 롤플레잉 에이전트를 만드는 개발자
- 한국어 로컬라이제이션, 대사 QA, 콘텐츠 운영을 맡는 에디터
- 브랜드 캐릭터나 상담형 캐릭터의 말투 일관성을 관리하는 팀
- Codex, Claude Code, Claude Desktop에서 한국어 대사 검수 워크플로를 자동화하려는 사용자

## 빠른 시작

Python 3.11 이상이 필요합니다.

```bash
python tools/test_mcp_stdio.py
```

MCP 클라이언트 설정에서 `<REPO_PATH>`를 이 저장소의 절대 경로로 바꿔 등록합니다.

Codex:

```toml
[mcp_servers.malmatch]
command = "python"
args = ["<REPO_PATH>\\tools\\korean_character_voice_mcp.py"]
enabled = true
startup_timeout_sec = 5
tool_timeout_sec = 30
```

Claude Code:

```powershell
claude mcp add-json malmatch '{"type":"stdio","command":"python","args":["<REPO_PATH>\\tools\\korean_character_voice_mcp.py"]}'
```

Claude Desktop 또는 일반 MCP 클라이언트:

```json
{
  "mcpServers": {
    "malmatch": {
      "command": "python",
      "args": ["<REPO_PATH>\\tools\\korean_character_voice_mcp.py"]
    }
  }
}
```

## 사용 예시

MCP를 연결한 뒤 모델에게 이렇게 요청합니다.

```text
말매치 MCP를 사용해서 아래 한국어 캐릭터 대사를 검수해줘.
get_rubric과 prepare_dialogue_audit 기준으로 평가하고, 필요한 경우 최소 수정안을 제안해줘.

장면:
캐릭터:
관계:
검수할 대사:
```

## 제공 도구

| 도구 | 용도 |
|---|---|
| `get_skillpack_overview` | 스킬팩 사용 흐름 확인 |
| `get_rubric` | 8개 평가 축 불러오기 |
| `get_prompt_template` | 검수, 리라이트, 농담, 어체 체크 프롬프트 불러오기 |
| `get_examples` | 합성 good/bad 예시 조회 |
| `get_calibration_hints` | 길이, 어체, 관계선, 한국어 예의 맥락 위험에 대한 로컬 보정 힌트 생성 |
| `get_korean_naturalness_hints` | 문법성, 번역투, 한국어 구어 리듬 힌트 생성 |
| `prepare_dialogue_audit` | 장면, 캐릭터, 관계, 대사를 검수 패키지로 조립 |
| `validate_skillpack` | 로컬 파일과 예시 구조 기본 검증 |

## 평가 축

| 축 | 확인할 것 |
|---|---|
| `naturalness` | 문법성, 한국어다운 표현, 구어 리듬이 자연스러운가 |
| `character_fit` | 이 캐릭터가 할 법한 말인가 |
| `relationship_fit` | 두 인물의 친밀도, 권력 거리, 예의 맥락에 맞는가 |
| `speech_level_consistency` | 반말, 해요체, 합쇼체, 반존대가 일관적인가 |
| `humor_timing` | 농담이 장면의 흐름을 해치지 않는가 |
| `cringe_risk` | 작위적이거나 오글거리는 표현이 있는가 |
| `anachronism_risk` | 세계관, 시대감, 장르와 충돌하는 표현이 있는가 |
| `genre_fit` | 게임, 웹툰, 챗봇, 소설 등 매체에 맞는 밀도인가 |

## 파일 구성

- `tools/korean_character_voice_mcp.py`: 로컬 stdio MCP 서버
- `tools/calibration_hints.py`: 원문을 저장하지 않는 로컬 보정 힌트 엔진
- `tools/korean_naturalness_hints.py`: 문법성, 번역투, 한국어 구어 리듬 힌트 엔진
- `docs/evaluation_rubric.md`: 평가 루브릭
- `docs/usage.md`: 기본 사용법
- `docs/mcp_usage.md`: MCP 연결 참고
- `prompts/`: 복사해 쓸 수 있는 프롬프트 템플릿
- `schemas/`: 입력과 평가 결과 스키마
- `examples/good_bad_pairs.yaml`: 합성 good/bad 예시

## 참고

- 이 서버는 로컬 stdio MCP 서버입니다. ChatGPT나 Claude.ai의 클라우드 connector에서 쓰려면 별도 원격 MCP 서버로 감싸야 합니다.
- 예시는 직접 작성한 합성 패턴 예시입니다.

## 출처

현재 v0.1에서 실제 프로파일링에 사용한 데이터는 AI Hub 데이터셋입니다.
평가 축과 예시 구조는 해당 데이터셋의 구조, 라벨, 길이, 턴 수, 어체 분포를 참고해 설계했습니다.

- [AI Hub](https://www.aihub.or.kr/): 주제별 텍스트 일상 대화 데이터, 페르소나 대화, 공감형 대화, 감성 대화 말뭉치, 한국어 어체 변환 데이터셋, 한국어 대화 요약, 생성형AI 일상대화 한국어 멀티세션 데이터, 한국어 멀티세션 대화

향후 개선 후보:

- [국립국어원 모두의 말뭉치](https://kli.korean.go.kr/main/requestMain.do?lang=ko): 일상 대화, 협력적 대화 요약, 대화 맥락 추론, 요약 평가 계열 말뭉치 도입 예정
- [KoDialogBench](https://github.com/sb-jang/kodialogbench): 한국어 대화 평가 벤치마크 도입 예정

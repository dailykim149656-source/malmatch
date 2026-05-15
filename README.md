![말매치 Malmatch logo](./assets/malmatch-logo.png)

# 말매치 Malmatch

말매치 Malmatch는 한국어 캐릭터 대사를 검수하기 위한 로컬 MCP 스킬팩입니다.
대사를 대신 생성하는 모델이 아니라, Codex, Claude Code, Claude Desktop 같은 MCP 클라이언트가 참고할 루브릭, 프롬프트, 스키마, 합성 예시, 로컬 보정 힌트를 제공합니다.

핵심 목표는 간단합니다. 한국어 대사가 캐릭터, 관계, 장면, 예의 맥락에 맞는지 더 안정적으로 점검하게 돕는 것입니다.

## 언제 쓰나요

- 캐릭터 말투가 장면마다 흔들리는지 확인할 때
- 반말, 존댓말, 반존대가 관계와 상황에 맞는지 볼 때
- 초면, 고객 응대, 상하 관계에서 사과, 양해, 부탁의 예의 맥락을 점검할 때
- 문법 오류, 맞춤법/띄어쓰기 후보, 번역투, 어색한 구어 표현을 잡고 싶을 때
- 위로, 조언, 농담, 고백, 갈등 대사가 과하거나 작위적으로 들리는지 확인할 때
- 게임, 웹툰, 챗봇, 소설 대사의 길이와 밀도를 다듬을 때

## 대상 사용자

- 게임, 웹툰, 웹소설, 인터랙티브 스토리의 작가와 내러티브 디자이너
- AI NPC, 캐릭터 챗봇, 롤플레잉 에이전트를 만드는 개발자
- 한국어 로컬라이제이션, 대사 QA, 콘텐츠 운영을 맡는 에디터
- 브랜드 캐릭터나 상담형 캐릭터의 말투 일관성을 관리하는 팀
- Codex, Claude Code, Claude Desktop에서 한국어 대사 검수 흐름을 자동화하려는 사용자

## 빠른 시작

Python 3.11 이상이 필요합니다. 먼저 MCP 서버가 정상 동작하는지 확인합니다.

```bash
python tools/test_mcp_stdio.py
```

MCP 클라이언트 설정에서는 `<REPO_PATH>`를 이 저장소의 절대 경로로 바꿔 등록합니다.

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
| `get_skillpack_overview` | 말매치 사용 흐름 확인 |
| `get_rubric` | 8개 평가 축 불러오기 |
| `get_prompt_template` | 검수, 리라이트, 농담, 어체 체크 프롬프트 불러오기 |
| `prepare_dialogue_audit` | 장면, 캐릭터, 관계, 대사를 검수 패키지로 조립 |
| `get_dataset_guidance` | 로컬 비공개 패턴 뱅크 기반 상황별 힌트 생성 |
| `get_text_metrics` | NFC 문자 수, 공백 제외 문자 수, UTF-8 바이트, NEIS식 바이트 지표 계산 |
| `get_calibration_hints` | 길이, 어체, 관계선, 한국어 예의 맥락 위험 힌트 생성 |
| `get_korean_naturalness_hints` | 문법성, 맞춤법/띄어쓰기 후보, 번역투, 구어 리듬 힌트 생성 |
| `get_examples` | 작은 합성 good/bad 패턴 카드 조회 |
| `validate_skillpack` | 공개 파일과 예시 구조 기본 검증 |

`get_examples`는 짧은 참고 카드입니다. 기준 보정은 예시를 계속 늘리는 방식보다 `get_dataset_guidance`와 로컬 패턴 뱅크를 우선 사용합니다.

## 평가 축

| 축 | 확인할 것 |
|---|---|
| `naturalness` | 문법성, 한국어다운 표현, 구어 리듬이 자연스러운가 |
| `character_fit` | 이 캐릭터가 할 법한 말인가 |
| `relationship_fit` | 친밀도, 권력 거리, 예의 맥락에 맞는가 |
| `speech_level_consistency` | 반말, 해요체, 합쇼체, 반존대가 일관적인가 |
| `humor_timing` | 농담이 장면의 흐름을 해치지 않는가 |
| `cringe_risk` | 작위적이거나 오글거리는 표현이 있는가 |
| `anachronism_risk` | 세계관, 시대감, 장르와 충돌하는 표현이 있는가 |
| `genre_fit` | 게임, 웹툰, 챗봇, 소설 등 매체에 맞는 밀도인가 |

## 로컬 보정과 데이터

말매치는 원본 데이터셋 문장, 대화 전문, 요약문을 공개 산출물이나 MCP 리소스로 노출하지 않습니다.
로컬 데이터셋은 구조, 라벨, 길이, 턴 수, 어체 분포 같은 집계 기준으로만 변환해 사용합니다.

비공개 패턴 뱅크 생성:

```bash
python tools/dataset_inventory.py --root . --out .malmatch/data_inventory.json
python tools/build_private_pattern_bank.py --inventory .malmatch/data_inventory.json --out .malmatch/private_pattern_bank.json
```

기본 생성은 zip 내부의 지원 엔트리를 끝까지 읽는 전체 스캔입니다. 빠르게 동작만 확인하려면 샘플 제한을 둘 수 있습니다.

```bash
python tools/build_private_pattern_bank.py --inventory .malmatch/data_inventory.json --out .malmatch/private_pattern_bank.json --max-entries-per-zip 500
```

`get_dataset_guidance`와 `prepare_dialogue_audit`는 기본적으로 `balanced` 기준을 사용합니다.
이 기준은 큰 데이터셋 하나가 전체 판단을 압도하지 않도록 데이터셋별 통계를 같은 가중치로 평균 냅니다.
전체 raw 빈도가 필요할 때만 `baseline_mode: "raw"`를 사용합니다.

## 보안과 배포 범위

- 이 서버는 로컬 stdio MCP 서버입니다. ChatGPT나 Claude.ai의 클라우드 connector에서 쓰려면 별도 원격 MCP 서버로 감싸야 합니다.
- 개인 서버 LLM, 사내 LLM, 로컬 모델을 쓰는 MCP 클라이언트와 함께 사용할 수 있습니다.
- 외부 맞춤법 검사기나 웹 API는 사용하지 않습니다.
- `.malmatch/*.json` 내부 분석 산출물과 원본 데이터셋은 git, 릴리스, 패키지에 포함하지 않습니다.
- 데이터셋 기반 설계의 공개 배포 원칙은 [데이터셋 사용과 공개 배포 원칙](docs/dataset_distribution.md)을 따릅니다.

## 파일 구성

- `tools/korean_character_voice_mcp.py`: 로컬 stdio MCP 서버
- `tools/build_private_pattern_bank.py`: 로컬 AI Hub 데이터셋을 원문 없는 비공개 패턴 뱅크로 변환
- `tools/dataset_guidance.py`: 비공개 패턴 뱅크 기반 상황별 보정 힌트 엔진
- `tools/text_metrics.py`: 원문을 저장하지 않는 로컬 문자 수와 바이트 지표 엔진
- `tools/calibration_hints.py`: 길이, 어체, 관계선, 예의 맥락 보정 힌트 엔진
- `tools/korean_naturalness_hints.py`: 문법성, 맞춤법/띄어쓰기, 번역투, 구어 리듬 힌트 엔진
- `docs/evaluation_rubric.md`: 평가 루브릭
- `docs/usage.md`: 기본 사용법
- `docs/mcp_usage.md`: MCP 연결 참고
- `prompts/`: 복사해 쓸 수 있는 프롬프트 템플릿
- `schemas/`: 입력과 평가 결과 스키마
- `examples/good_bad_pairs.yaml`: 합성 good/bad 예시

## 출처

현재 v0.1에서 실제 프로파일링에 사용한 데이터는 AI Hub 데이터셋입니다.
평가 축과 예시 구조는 해당 데이터셋의 구조, 라벨, 길이, 턴 수, 어체 분포를 참고해 설계했습니다.

- [AI Hub](https://www.aihub.or.kr/): 주제별 텍스트 일상 대화 데이터, 페르소나 대화, 공감형 대화, 감성 대화 말뭉치, 한국어 어체 변환 데이터셋, 한국어 대화 요약, 생성형AI 일상대화 한국어 멀티세션 데이터, 한국어 멀티세션 대화

향후 개선 후보:

- [국립국어원 모두의 말뭉치](https://kli.korean.go.kr/main/requestMain.do?lang=ko): 일상 대화, 협력적 대화 요약, 대화 맥락 추론, 요약 평가 계열 말뭉치 도입 예정
- [KoDialogBench](https://github.com/sb-jang/kodialogbench): 한국어 대화 평가 벤치마크 도입 예정

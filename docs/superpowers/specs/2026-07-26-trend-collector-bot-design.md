# 트렌드 수집봇 설계

## 목적

네이버 데이터랩(검색량 추이), 공식 RSS 피드(버티컬 미디어/브랜드 블로그 신규 글), 유튜브 데이터 API v3(급상승 키워드)를 매일 자동 수집해 노션 DB에 기록하고, AI로 한국어 트렌드 리포트를 생성한다. GitHub Actions로 완전 자동화한다.

## 범위 (v1)

- 소스: 네이버 데이터랩 API, RSS 피드, 유튜브 데이터 API v3 — 3개만. 네이버 검색광고 API(절대 검색량), 블로그/카페 검색 API는 v2로 미룬다.
- 버티컬: 멀티 버티컬 지원 구조로 설계하되, 첫 키워드 세트는 창업/프랜차이즈 중심으로 시작.
- 실행 주기: 매일 1회 (GitHub Actions cron, KST 07:00).
- AI 요약: Google Gemini 무료 API로 시작. 추후 OpenAI/Anthropic으로 교체 가능하도록 얇게 추상화.
- 키워드·RSS 피드 목록: 노션 "설정" DB에서 관리 (코드 수정 없이 노션에서 추가/삭제).

## 아키텍처

```
GitHub Actions (매일 07:00 KST cron + workflow_dispatch 수동 실행)
        │
        ▼
   main.py 오케스트레이터
        │
   ① 노션 "설정" DB에서 키워드/RSS 목록 로드
        │
   ② 3개 수집기 순차 실행 (하나 실패해도 나머지는 진행)
        ├─ collectors/datalab.py   (네이버 데이터랩 검색어트렌드 API)
        ├─ collectors/rss.py       (RSS 피드, feedparser)
        └─ collectors/youtube.py   (유튜브 데이터 API v3 급상승/검색)
        │
   ③ summarizer.py → Gemini 무료 API로 한국어 리포트 텍스트 생성
        │
   ④ notion_writer.py → 노션에 기록
        ├─ "트렌드 로그" DB (일별 원자료, 시계열 차트용)
        └─ "일일 리포트" DB (AI 요약 리포트 페이지)
```

상태(키워드/RSS 목록)는 전부 노션 "설정" DB에 있으므로 Actions 러너는 무상태다.

## 컴포넌트

- `main.py` — 오케스트레이션: 설정 로드 → 수집 → 요약 → 노션 기록 → 로깅. `--dry-run` 플래그로 노션에 쓰지 않고 콘솔 출력만 하는 로컬 실행 모드 지원.
- `config.py` — 노션 "설정" DB를 조회해 키워드 리스트/RSS 피드 리스트/버티컬 태그를 파싱.
- `collectors/datalab.py` — 네이버 데이터랩 검색어트렌드 API 호출. 키워드는 최대 5개씩 그룹으로 묶어 호출(API 제한). 오늘/어제/지난주 같은 요일 지수를 비교해 전일대비·전주대비 델타 계산.
- `collectors/rss.py` — 설정된 RSS 피드를 feedparser로 파싱, 최근 24~48시간 내 게시물만 필터링해 제목/링크/요약 추출.
- `collectors/youtube.py` — 유튜브 데이터 API v3 `search.list`(키워드별, order=viewCount 또는 date)로 급상승 영상 제목/키워드 추출. 쿼터 소비량(검색 1회당 100 unit, 일일 기본 10,000 unit)을 감안해 키워드 수를 제한.
- 각 collector 함수는 순수 함수(입력: API 원본 응답 → 출력: 정규화된 dict)로 분리해 실제 API 호출 없이 단위 테스트 가능하게 한다.
- `summarizer.py` — 수집된 원자료를 프롬프트로 구성해 AI에게 한국어 리포트 요약을 생성시킨다. `summarize(provider, prompt)` 형태로 추상화해, 나중에 Gemini → GPT/Claude 교체 시 함수 하나 추가 + 환경변수 하나만 바꾸면 되게 한다.
- `notion_writer.py` — 노션 API 래퍼. 속도 제한(3 req/sec) 대응을 위해 요청 사이 짧은 sleep과 429 재시도 로직을 포함.

## 노션 DB 구조

### 설정 DB
| 필드 | 타입 | 설명 |
|---|---|---|
| 키워드 | text | 추적할 검색어 |
| 버티컬 | select | 창업/프랜차이즈, 일반 등 |
| RSS피드URL | url | 버티컬 미디어/브랜드 블로그 RSS 주소 |
| 활성여부 | checkbox | 체크 해제 시 수집 대상에서 제외 |

### 트렌드 로그 DB (시계열 원자료)
| 필드 | 타입 | 설명 |
|---|---|---|
| 날짜 | date | 수집 일자 |
| 키워드 | text | |
| 소스 | select | 데이터랩 / 유튜브 / RSS |
| 값 | number | 검색지수, 조회수 등 |
| 전일대비 | number | |
| 전주대비 | number | |

### 일일 리포트 DB
| 필드 | 타입 | 설명 |
|---|---|---|
| 제목 | title | 예: "2026-07-27 창업 트렌드 리포트" |
| 날짜 | date | |
| 버티컬 | select | |
| 요약 | rich text (페이지 본문) | AI 생성 리포트 |
| 급상승 키워드 | multi-select 또는 text | |
| RSS 원본 링크 | rich text | 수집된 링크 모음 |

## 에러 처리

- **API 호출 한도 초과** (네이버/유튜브): 429 응답 시 1회 지수 백오프 재시도 → 실패 시 해당 소스만 스킵하고 리포트에 "⚠️ OO 소스 수집 실패" 명시. 다른 소스 수집/리포트 생성은 계속 진행.
- **노션 API 속도 제한**: 쓰기 요청 사이 짧은 sleep + 429 시 `Retry-After` 헤더를 준수하는 재시도 래퍼.
- **RSS 피드 구조 변경**: feedparser가 malformed XML도 최대한 파싱하되, title/link가 없는 entry는 개별 스킵. 피드 자체가 파싱 불가능하면 해당 피드만 로그에 남기고 나머지 피드는 정상 처리.
- 전체 실행이 실패하면 GitHub Actions가 실패 상태로 표시되어 사용자에게 기본 이메일 알림이 간다 (v1에서는 별도 Slack/이메일 알림 미구현).

## GitHub Actions

`.github/workflows/trend-report.yml`
- 트리거: `cron: '0 22 * * *'` (UTC 22:00 = KST 07:00) + `workflow_dispatch` (수동 실행/디버깅용)
- Python 3.11, `pip install -r requirements.txt`
- 필요 Secrets: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `YOUTUBE_API_KEY`, `NOTION_TOKEN`, `NOTION_SETTINGS_DB_ID`, `NOTION_LOG_DB_ID`, `NOTION_REPORT_DB_ID`, `GEMINI_API_KEY`

## 테스트

- 각 collector는 순수 함수로 분리되어 mock 응답으로 단위 테스트 가능 (`pytest`).
- `main.py --dry-run`으로 노션에 실제로 쓰지 않고 콘솔 출력만 확인하는 로컬 실행 모드.
- GitHub Actions에 `workflow_dispatch`를 남겨 언제든 수동 실행/디버깅 가능.

## v2 후보 (범위 밖)

- 네이버 검색광고 API(절대 검색량) 연동 → 데이터랩 상대지수와 결합해 정확도 향상
- 네이버 블로그/카페 검색 API로 "관심 증가" 콘텐츠량 지표 추가
- 빅카인즈 뉴스 언급량 API
- Slack/이메일 알림, AI 요약 엔진 GPT/Claude로 교체

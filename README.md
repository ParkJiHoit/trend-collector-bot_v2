# 트렌드 수집봇

네이버 데이터랩 + RSS + 유튜브 데이터를 매일 수집해 노션에 기록하고 Gemini로 한국어 리포트를 생성합니다.

## 1. 노션 준비

1. https://www.notion.so/my-integrations 에서 새 integration 생성 → Internal Integration Token 발급 (`NOTION_TOKEN`)
2. 노션에 DB 3개 생성: 설정 / 트렌드 로그 / 일일 리포트 (필드 구조는 `docs/superpowers/specs/2026-07-26-trend-collector-bot-design.md` 참고)
3. 각 DB 우측 상단 `...` → `Connections` → 위에서 만든 integration 연결
4. 각 DB URL에서 32자리 ID 추출 → `NOTION_SETTINGS_DB_ID` / `NOTION_LOG_DB_ID` / `NOTION_REPORT_DB_ID`

## 2. 네이버 API

1. https://developers.naver.com/apps 에서 애플리케이션 등록, "검색어트렌드" API 사용 신청
2. Client ID / Secret 발급 → `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`

## 3. 유튜브 API

1. https://console.cloud.google.com 에서 프로젝트 생성, YouTube Data API v3 사용 설정
2. API 키 발급 → `YOUTUBE_API_KEY` (일일 쿼터 10,000 unit, 검색 1회당 100 unit)

## 4. Gemini API

1. https://aistudio.google.com/apikey 에서 무료 API 키 발급 → `GEMINI_API_KEY`

## 5. GitHub Secrets 등록

저장소 Settings → Secrets and variables → Actions 에서 위 8개 값을 모두 등록.

## 6. 로컬 실행

```bash
pip install -r requirements.txt
cp .env.example .env  # 값 채우기
python main.py --dry-run   # 노션에 쓰지 않고 콘솔 출력만 확인
python main.py             # 실제 노션에 기록
```

## 7. 자동 실행

`.github/workflows/trend-report.yml`이 매일 07:00 KST에 자동 실행됩니다. Actions 탭에서 `Run workflow`로 수동 실행도 가능합니다.

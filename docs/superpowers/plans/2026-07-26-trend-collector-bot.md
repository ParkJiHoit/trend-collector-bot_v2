# 트렌드 수집봇 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 네이버 데이터랩, RSS 피드, 유튜브 데이터 API v3에서 매일 트렌드 데이터를 수집해 노션 DB에 기록하고 Gemini로 한국어 리포트를 생성하는 GitHub Actions 자동화 봇을 만든다.

**Architecture:** 각 소스(데이터랩/RSS/유튜브)마다 "네트워크 호출 함수"와 "순수 정규화 함수"를 분리한 collector 모듈. `config.py`가 노션 "설정" DB에서 키워드/피드 목록을 읽고, `main.py`가 전체를 오케스트레이션해 `summarizer.py`(Gemini)와 `notion_writer.py`(노션 기록)로 넘긴다. 모든 외부 API는 `requests`로 직접 호출 (SDK 미사용).

**Tech Stack:** Python 3.11, `requests`, `feedparser`, `python-dotenv`, `pytest`. GitHub Actions cron.

## Global Constraints

- v1 소스는 데이터랩 + RSS + 유튜브 3개만. 검색광고 API, 블로그/카페 검색은 범위 밖.
- 실행 주기: 매일 1회, GitHub Actions cron KST 07:00 (`cron: '0 22 * * *'`, UTC 기준).
- AI 요약은 Gemini 무료 API로 시작하되, provider를 바꿀 수 있도록 `summarize()` 뒤에 얇게 추상화.
- 키워드/RSS 피드 목록은 코드가 아니라 노션 "설정" DB에서 읽는다.
- 노션 API 속도 제한(3req/sec) 대응: 429 시 `Retry-After` 준수 재시도.
- 각 collector는 독립적으로 실패할 수 있어야 한다 (하나 실패해도 나머지 소스/리포트 생성은 계속).
- 각 collector의 정규화 로직은 순수 함수로 분리해 네트워크 없이 단위 테스트 가능해야 한다.
- 새 의존성 추가 금지: 이미 정한 4개(`requests`, `feedparser`, `python-dotenv`, `pytest`) 외에는 stdlib로 해결한다.

---

## File Structure

```
trend-collector-bot/
  requirements.txt
  .env.example
  .gitignore
  notion_api.py
  config.py
  collectors/
    __init__.py
    datalab.py
    rss.py
    youtube.py
  summarizer.py
  notion_writer.py
  main.py
  tests/
    __init__.py
    test_notion_api.py
    test_config.py
    test_datalab.py
    test_rss.py
    test_youtube.py
    test_summarizer.py
    test_notion_writer.py
    test_main.py
  .github/workflows/trend-report.yml
  README.md
```

---

### Task 1: 프로젝트 스캐폴딩 + 노션 API 래퍼

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `notion_api.py`
- Test: `tests/test_notion_api.py`
- Create: `tests/__init__.py` (빈 파일)

**Interfaces:**
- Produces: `notion_api.query_database(database_id: str, token: str) -> dict`, `notion_api.create_page(database_id: str, properties: dict, token: str, children: list | None = None) -> dict`

- [ ] **Step 1: requirements.txt / .env.example / .gitignore 작성**

`requirements.txt`:
```
requests==2.32.3
feedparser==6.0.11
python-dotenv==1.0.1
pytest==8.3.3
```

`.env.example`:
```
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
YOUTUBE_API_KEY=
NOTION_TOKEN=
NOTION_SETTINGS_DB_ID=
NOTION_LOG_DB_ID=
NOTION_REPORT_DB_ID=
GEMINI_API_KEY=
```

`.gitignore`:
```
.env
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 2: 빈 `tests/__init__.py` 생성**

- [ ] **Step 3: 실패하는 테스트 작성 (`tests/test_notion_api.py`)**

```python
from unittest.mock import patch, MagicMock
import notion_api


def test_query_database_calls_correct_endpoint():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"results": []}
    with patch("notion_api.requests.request", return_value=fake_response) as mock_req:
        result = notion_api.query_database("db123", "secret-token")

    assert result == {"results": []}
    args, kwargs = mock_req.call_args
    assert args[0] == "POST"
    assert args[1] == "https://api.notion.com/v1/databases/db123/query"
    assert kwargs["headers"]["Authorization"] == "Bearer secret-token"
    assert kwargs["headers"]["Notion-Version"] == "2022-06-28"


def test_create_page_sends_properties_in_body():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"id": "page1"}
    with patch("notion_api.requests.request", return_value=fake_response) as mock_req:
        result = notion_api.create_page("db456", {"Name": {}}, "secret-token")

    assert result == {"id": "page1"}
    _, kwargs = mock_req.call_args
    assert kwargs["json"]["parent"] == {"database_id": "db456"}
    assert kwargs["json"]["properties"] == {"Name": {}}


def test_query_database_retries_once_on_429_then_succeeds():
    rate_limited = MagicMock(status_code=429, headers={"Retry-After": "0"})
    ok = MagicMock(status_code=200)
    ok.json.return_value = {"results": []}
    with patch("notion_api.requests.request", side_effect=[rate_limited, ok]) as mock_req, \
         patch("notion_api.time.sleep") as mock_sleep:
        result = notion_api.query_database("db123", "secret-token")

    assert result == {"results": []}
    assert mock_req.call_count == 2
    mock_sleep.assert_called_once()
```

- [ ] **Step 4: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_notion_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'notion_api'`

- [ ] **Step 5: `notion_api.py` 최소 구현**

```python
import time

import requests

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _request(method, path, token, **kwargs):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{path}"

    response = requests.request(method, url, headers=headers, timeout=10, **kwargs)
    if response.status_code == 429:
        time.sleep(float(response.headers.get("Retry-After", 1)))
        response = requests.request(method, url, headers=headers, timeout=10, **kwargs)

    response.raise_for_status()
    return response.json()


def query_database(database_id, token):
    return _request("POST", f"/databases/{database_id}/query", token)


def create_page(database_id, properties, token, children=None):
    body = {"parent": {"database_id": database_id}, "properties": properties}
    if children:
        body["children"] = children
    return _request("POST", "/pages", token, json=body)
```

- [ ] **Step 6: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_notion_api.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt .env.example .gitignore notion_api.py tests/__init__.py tests/test_notion_api.py
git commit -m "feat: add notion API wrapper with 429 retry"
```

---

### Task 2: 설정(키워드/RSS) 로더

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `notion_api.query_database(database_id: str, token: str) -> dict` (Task 1)
- Produces: `config.parse_settings_response(response: dict) -> list[dict]`, `config.load_settings(database_id: str, token: str) -> list[dict]`. 각 dict: `{"keyword": str, "vertical": str, "rss_url": str, "active": bool}`

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_config.py`)**

```python
from unittest.mock import patch
import config

RAW_RESPONSE = {
    "results": [
        {
            "properties": {
                "키워드": {"title": [{"plain_text": "휴대폰 창업"}]},
                "버티컬": {"select": {"name": "창업/프랜차이즈"}},
                "RSS피드URL": {"url": "https://example.com/rss"},
                "활성여부": {"checkbox": True},
            }
        },
        {
            "properties": {
                "키워드": {"title": [{"plain_text": "비활성 키워드"}]},
                "버티컬": {"select": {"name": "일반"}},
                "RSS피드URL": {"url": None},
                "활성여부": {"checkbox": False},
            }
        },
    ]
}


def test_parse_settings_response_extracts_fields():
    result = config.parse_settings_response(RAW_RESPONSE)

    assert result == [
        {"keyword": "휴대폰 창업", "vertical": "창업/프랜차이즈", "rss_url": "https://example.com/rss", "active": True},
        {"keyword": "비활성 키워드", "vertical": "일반", "rss_url": None, "active": False},
    ]


def test_load_settings_filters_inactive_rows():
    with patch("config.notion_api.query_database", return_value=RAW_RESPONSE):
        result = config.load_settings("db123", "token")

    assert len(result) == 1
    assert result[0]["keyword"] == "휴대폰 창업"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: `config.py` 최소 구현**

```python
import notion_api


def parse_settings_response(response):
    rows = []
    for item in response["results"]:
        props = item["properties"]
        title_parts = props["키워드"]["title"]
        keyword = title_parts[0]["plain_text"] if title_parts else ""
        select = props["버티컬"]["select"]
        rows.append(
            {
                "keyword": keyword,
                "vertical": select["name"] if select else None,
                "rss_url": props["RSS피드URL"]["url"],
                "active": props["활성여부"]["checkbox"],
            }
        )
    return rows


def load_settings(database_id, token):
    response = notion_api.query_database(database_id, token)
    rows = parse_settings_response(response)
    return [row for row in rows if row["active"]]
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add config.py tests/test_config.py
git commit -m "feat: load keyword/RSS settings from notion"
```

---

### Task 3: 네이버 데이터랩 collector

**Files:**
- Create: `collectors/__init__.py` (빈 파일)
- Create: `collectors/datalab.py`
- Test: `tests/test_datalab.py`

**Interfaces:**
- Produces:
  - `collectors.datalab.chunk_keywords(keywords: list[str], size: int = 5) -> list[list[str]]`
  - `collectors.datalab.fetch_datalab_group(keywords: list[str], client_id: str, client_secret: str, start_date: str, end_date: str) -> dict`
  - `collectors.datalab.normalize_datalab_response(response: dict) -> dict[str, dict]` — 값: `{"today": float, "yesterday": float | None, "last_week": float | None, "vs_yesterday_pct": float | None, "vs_last_week_pct": float | None}`

- [ ] **Step 1: 빈 `collectors/__init__.py` 생성**

- [ ] **Step 2: 실패하는 테스트 작성 (`tests/test_datalab.py`)**

```python
from unittest.mock import patch, MagicMock
from collectors import datalab

RAW_RESPONSE = {
    "results": [
        {
            "title": "휴대폰 창업",
            "keywords": ["휴대폰 창업"],
            "data": [
                {"period": "2026-07-19", "ratio": 40.0},
                {"period": "2026-07-20", "ratio": 42.0},
                {"period": "2026-07-21", "ratio": 41.0},
                {"period": "2026-07-22", "ratio": 45.0},
                {"period": "2026-07-23", "ratio": 50.0},
                {"period": "2026-07-24", "ratio": 60.0},
                {"period": "2026-07-25", "ratio": 55.0},
                {"period": "2026-07-26", "ratio": 74.0},
            ],
        }
    ]
}


def test_chunk_keywords_splits_into_groups_of_five():
    keywords = ["a", "b", "c", "d", "e", "f", "g"]
    assert datalab.chunk_keywords(keywords) == [["a", "b", "c", "d", "e"], ["f", "g"]]


def test_fetch_datalab_group_posts_expected_body():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = RAW_RESPONSE
    with patch("collectors.datalab.requests.post", return_value=fake_response) as mock_post:
        result = datalab.fetch_datalab_group(["휴대폰 창업"], "id", "secret", "2026-07-19", "2026-07-26")

    assert result == RAW_RESPONSE
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["X-Naver-Client-Id"] == "id"
    assert kwargs["headers"]["X-Naver-Client-Secret"] == "secret"
    body = kwargs["json"]
    assert body["keywordGroups"] == [{"groupName": "휴대폰 창업", "keywords": ["휴대폰 창업"]}]
    assert body["startDate"] == "2026-07-19"
    assert body["endDate"] == "2026-07-26"


def test_normalize_datalab_response_computes_deltas():
    result = datalab.normalize_datalab_response(RAW_RESPONSE)

    entry = result["휴대폰 창업"]
    assert entry["today"] == 74.0
    assert entry["yesterday"] == 55.0
    assert entry["last_week"] == 40.0
    assert round(entry["vs_yesterday_pct"], 1) == round((74.0 - 55.0) / 55.0 * 100, 1)
    assert round(entry["vs_last_week_pct"], 1) == round((74.0 - 40.0) / 40.0 * 100, 1)


def test_normalize_datalab_response_handles_short_history():
    short_response = {
        "results": [
            {"title": "새 키워드", "keywords": ["새 키워드"], "data": [{"period": "2026-07-26", "ratio": 10.0}]}
        ]
    }
    result = datalab.normalize_datalab_response(short_response)

    entry = result["새 키워드"]
    assert entry["today"] == 10.0
    assert entry["yesterday"] is None
    assert entry["vs_yesterday_pct"] is None
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_datalab.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collectors'`

- [ ] **Step 4: `collectors/datalab.py` 최소 구현**

```python
import requests

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"


def chunk_keywords(keywords, size=5):
    return [keywords[i:i + size] for i in range(0, len(keywords), size)]


def fetch_datalab_group(keywords, client_id, client_secret, start_date, end_date):
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json",
    }
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
    }
    response = requests.post(DATALAB_URL, headers=headers, json=body, timeout=10)
    response.raise_for_status()
    return response.json()


def _pct_change(current, previous):
    if previous is None or previous == 0:
        return None
    return (current - previous) / previous * 100


def normalize_datalab_response(response):
    normalized = {}
    for group in response["results"]:
        data = group["data"]
        today = data[-1]["ratio"]
        yesterday = data[-2]["ratio"] if len(data) >= 2 else None
        last_week = data[-8]["ratio"] if len(data) >= 8 else None
        normalized[group["title"]] = {
            "today": today,
            "yesterday": yesterday,
            "last_week": last_week,
            "vs_yesterday_pct": _pct_change(today, yesterday),
            "vs_last_week_pct": _pct_change(today, last_week),
        }
    return normalized
```

Note: `fetch_datalab_group`은 그룹명(`groupName`)에 키워드 자기 자신 하나만 넣어 그룹당 1키워드 = 1결과로 단순화한다 (여러 키워드를 한 그룹으로 묶으면 결과가 합쳐져서 개별 키워드 지수를 못 뽑기 때문). `chunk_keywords`는 한 번의 API 호출에 그룹을 최대 5개까지 실을 수 있게 나누는 용도.

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_datalab.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 커밋**

```bash
git add collectors/__init__.py collectors/datalab.py tests/test_datalab.py
git commit -m "feat: add naver datalab collector"
```

---

### Task 4: RSS collector

**Files:**
- Create: `collectors/rss.py`
- Test: `tests/test_rss.py`

**Interfaces:**
- Produces:
  - `collectors.rss.fetch_rss_entries(feed_url: str) -> list[dict]` — 각 dict: `{"title": str, "link": str, "published_parsed": time.struct_time | None}`
  - `collectors.rss.filter_recent_entries(entries: list[dict], since_hours: int = 48, now: datetime | None = None) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_rss.py`)**

```python
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from collectors import rss


def _struct(dt):
    return dt.timetuple()


def test_filter_recent_entries_keeps_only_last_48_hours():
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    entries = [
        {"title": "24시간 전", "link": "a", "published_parsed": _struct(now - timedelta(hours=24))},
        {"title": "72시간 전", "link": "b", "published_parsed": _struct(now - timedelta(hours=72))},
        {"title": "발행일 없음", "link": "c", "published_parsed": None},
    ]

    result = rss.filter_recent_entries(entries, since_hours=48, now=now)

    titles = [e["title"] for e in result]
    assert titles == ["24시간 전"]


def test_fetch_rss_entries_parses_feed(monkeypatch):
    fake_feed = MagicMock()
    fake_feed.entries = [
        {"title": "글 제목", "link": "https://example.com/post", "published_parsed": time.gmtime()}
    ]
    with patch("collectors.rss.feedparser.parse", return_value=fake_feed) as mock_parse:
        result = rss.fetch_rss_entries("https://example.com/rss")

    mock_parse.assert_called_once_with("https://example.com/rss")
    assert result == [
        {"title": "글 제목", "link": "https://example.com/post", "published_parsed": fake_feed.entries[0]["published_parsed"]}
    ]
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_rss.py -v`
Expected: FAIL — `ImportError: cannot import name 'rss' from 'collectors'`

- [ ] **Step 3: `collectors/rss.py` 최소 구현**

```python
from calendar import timegm
from datetime import datetime, timedelta, timezone

import feedparser


def fetch_rss_entries(feed_url):
    feed = feedparser.parse(feed_url)
    entries = []
    for entry in feed.entries:
        entries.append(
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published_parsed": entry.get("published_parsed"),
            }
        )
    return entries


def filter_recent_entries(entries, since_hours=48, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=since_hours)
    recent = []
    for entry in entries:
        parsed = entry.get("published_parsed")
        if not parsed:
            continue
        published = datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
        if published >= cutoff:
            recent.append(entry)
    return recent
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_rss.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add collectors/rss.py tests/test_rss.py
git commit -m "feat: add rss collector with recency filter"
```

---

### Task 5: 유튜브 collector

**Files:**
- Create: `collectors/youtube.py`
- Test: `tests/test_youtube.py`

**Interfaces:**
- Produces:
  - `collectors.youtube.fetch_youtube_trending(keyword: str, api_key: str, max_results: int = 5) -> dict`
  - `collectors.youtube.normalize_youtube_response(response: dict) -> list[dict]` — 각 dict: `{"title": str, "video_id": str, "channel": str, "published_at": str}`

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_youtube.py`)**

```python
from unittest.mock import patch, MagicMock
from collectors import youtube

RAW_RESPONSE = {
    "items": [
        {
            "id": {"videoId": "abc123"},
            "snippet": {"title": "휴대폰 창업 브이로그", "channelTitle": "창업채널", "publishedAt": "2026-07-25T10:00:00Z"},
        }
    ]
}


def test_fetch_youtube_trending_sends_expected_params():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = RAW_RESPONSE
    with patch("collectors.youtube.requests.get", return_value=fake_response) as mock_get:
        result = youtube.fetch_youtube_trending("휴대폰 창업", "api-key", max_results=5)

    assert result == RAW_RESPONSE
    _, kwargs = mock_get.call_args
    params = kwargs["params"]
    assert params["q"] == "휴대폰 창업"
    assert params["key"] == "api-key"
    assert params["maxResults"] == 5
    assert params["order"] == "viewCount"
    assert params["type"] == "video"


def test_normalize_youtube_response_extracts_fields():
    result = youtube.normalize_youtube_response(RAW_RESPONSE)

    assert result == [
        {
            "title": "휴대폰 창업 브이로그",
            "video_id": "abc123",
            "channel": "창업채널",
            "published_at": "2026-07-25T10:00:00Z",
        }
    ]
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_youtube.py -v`
Expected: FAIL — `ImportError: cannot import name 'youtube' from 'collectors'`

- [ ] **Step 3: `collectors/youtube.py` 최소 구현**

```python
import requests

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def fetch_youtube_trending(keyword, api_key, max_results=5):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "order": "viewCount",
        "maxResults": max_results,
        "key": api_key,
    }
    response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def normalize_youtube_response(response):
    normalized = []
    for item in response["items"]:
        snippet = item["snippet"]
        normalized.append(
            {
                "title": snippet["title"],
                "video_id": item["id"]["videoId"],
                "channel": snippet["channelTitle"],
                "published_at": snippet["publishedAt"],
            }
        )
    return normalized
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_youtube.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add collectors/youtube.py tests/test_youtube.py
git commit -m "feat: add youtube trending collector"
```

---

### Task 6: AI 요약 (Gemini)

**Files:**
- Create: `summarizer.py`
- Test: `tests/test_summarizer.py`

**Interfaces:**
- Consumes: `collectors.datalab.normalize_datalab_response` 결과 형태, `collectors.rss.filter_recent_entries` 결과 형태, `collectors.youtube.normalize_youtube_response` 결과 형태 (Task 3~5)
- Produces:
  - `summarizer.build_prompt(vertical: str, date: str, datalab_results: dict, rss_items: list[dict], youtube_results: list[dict]) -> str`
  - `summarizer.call_gemini(prompt: str, api_key: str) -> dict`
  - `summarizer.extract_gemini_text(response: dict) -> str`
  - `summarizer.summarize(vertical: str, date: str, datalab_results: dict, rss_items: list[dict], youtube_results: list[dict], api_key: str) -> str`

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_summarizer.py`)**

```python
from unittest.mock import patch, MagicMock
import summarizer

DATALAB_RESULTS = {"휴대폰 창업": {"today": 74.0, "vs_yesterday_pct": 12.3, "vs_last_week_pct": 30.0}}
RSS_ITEMS = [{"title": "릴스 후킹 문구 트렌드", "link": "https://example.com/a"}]
YOUTUBE_RESULTS = [{"title": "휴대폰 창업 브이로그", "video_id": "abc123", "channel": "창업채널"}]


def test_build_prompt_includes_all_sources():
    prompt = summarizer.build_prompt("창업/프랜차이즈", "2026-07-27", DATALAB_RESULTS, RSS_ITEMS, YOUTUBE_RESULTS)

    assert "휴대폰 창업" in prompt
    assert "74.0" in prompt
    assert "릴스 후킹 문구 트렌드" in prompt
    assert "휴대폰 창업 브이로그" in prompt
    assert "2026-07-27" in prompt


def test_call_gemini_sends_prompt_in_body():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "요약 결과"}]}}]}
    with patch("summarizer.requests.post", return_value=fake_response) as mock_post:
        result = summarizer.call_gemini("프롬프트 내용", "gemini-key")

    assert result == {"candidates": [{"content": {"parts": [{"text": "요약 결과"}]}}]}
    _, kwargs = mock_post.call_args
    assert kwargs["params"]["key"] == "gemini-key"
    assert kwargs["json"]["contents"][0]["parts"][0]["text"] == "프롬프트 내용"


def test_extract_gemini_text_reads_first_candidate():
    response = {"candidates": [{"content": {"parts": [{"text": "요약 결과"}]}}]}
    assert summarizer.extract_gemini_text(response) == "요약 결과"


def test_summarize_composes_prompt_call_and_extract():
    with patch("summarizer.call_gemini", return_value={"candidates": [{"content": {"parts": [{"text": "최종 리포트"}]}}]}) as mock_call:
        result = summarizer.summarize("창업/프랜차이즈", "2026-07-27", DATALAB_RESULTS, RSS_ITEMS, YOUTUBE_RESULTS, "gemini-key")

    assert result == "최종 리포트"
    prompt_arg = mock_call.call_args[0][0]
    assert "휴대폰 창업" in prompt_arg
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_summarizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'summarizer'`

- [ ] **Step 3: `summarizer.py` 최소 구현**

```python
import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def build_prompt(vertical, date, datalab_results, rss_items, youtube_results):
    lines = [f"{date} {vertical} 트렌드 리포트를 작성해줘.", "", "[데이터랩 검색량]"]
    for keyword, stats in datalab_results.items():
        lines.append(
            f"- {keyword}: 검색지수 {stats['today']} "
            f"(전일대비 {stats['vs_yesterday_pct']}%, 전주대비 {stats['vs_last_week_pct']}%)"
        )

    lines.append("")
    lines.append("[RSS 신규 글]")
    for item in rss_items:
        lines.append(f"- {item['title']} ({item['link']})")

    lines.append("")
    lines.append("[유튜브 급상승]")
    for video in youtube_results:
        lines.append(f"- {video['title']} ({video['channel']})")

    lines.append("")
    lines.append("위 데이터를 바탕으로 급상승 키워드, 관심 증가, 유튜브 급상승, RSS 수집 항목을 정리한 한국어 리포트를 작성해줘.")
    return "\n".join(lines)


def call_gemini(prompt, api_key):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(GEMINI_URL, params={"key": api_key}, json=body, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_gemini_text(response):
    return response["candidates"][0]["content"]["parts"][0]["text"]


def summarize(vertical, date, datalab_results, rss_items, youtube_results, api_key):
    prompt = build_prompt(vertical, date, datalab_results, rss_items, youtube_results)
    response = call_gemini(prompt, api_key)
    return extract_gemini_text(response)
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_summarizer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add summarizer.py tests/test_summarizer.py
git commit -m "feat: add gemini-based trend summarizer"
```

---

### Task 7: 노션 기록 (트렌드 로그 + 일일 리포트)

**Files:**
- Create: `notion_writer.py`
- Test: `tests/test_notion_writer.py`

**Interfaces:**
- Consumes: `notion_api.create_page(database_id: str, properties: dict, token: str, children: list | None = None) -> dict` (Task 1)
- Produces:
  - `notion_writer.build_log_properties(date: str, keyword: str, source: str, value: float, vs_yesterday: float | None, vs_last_week: float | None) -> dict`
  - `notion_writer.build_report_properties(date: str, vertical: str, summary: str, top_keywords: list[str], rss_links: list[str]) -> dict`
  - `notion_writer.write_trend_log_entries(entries: list[dict], log_db_id: str, token: str) -> None` — `entries`의 각 dict는 `build_log_properties`의 키워드 인자와 동일한 키(`date, keyword, source, value, vs_yesterday, vs_last_week`)를 가진다
  - `notion_writer.write_report(date: str, vertical: str, summary: str, top_keywords: list[str], rss_links: list[str], report_db_id: str, token: str) -> dict`

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_notion_writer.py`)**

```python
from unittest.mock import patch
import notion_writer


def test_build_log_properties_shape():
    props = notion_writer.build_log_properties("2026-07-27", "휴대폰 창업", "데이터랩", 74.0, 12.3, 30.0)

    assert props["키워드"]["title"][0]["text"]["content"] == "휴대폰 창업"
    assert props["날짜"]["date"]["start"] == "2026-07-27"
    assert props["소스"]["select"]["name"] == "데이터랩"
    assert props["값"]["number"] == 74.0
    assert props["전일대비"]["number"] == 12.3
    assert props["전주대비"]["number"] == 30.0


def test_build_report_properties_shape():
    props = notion_writer.build_report_properties(
        "2026-07-27", "창업/프랜차이즈", "요약 내용", ["휴대폰 창업"], ["https://example.com/a"]
    )

    assert props["제목"]["title"][0]["text"]["content"] == "2026-07-27 창업/프랜차이즈 트렌드 리포트"
    assert props["날짜"]["date"]["start"] == "2026-07-27"
    assert props["버티컬"]["select"]["name"] == "창업/프랜차이즈"
    assert props["요약"]["rich_text"][0]["text"]["content"] == "요약 내용"
    assert props["급상승 키워드"]["multi_select"] == [{"name": "휴대폰 창업"}]
    assert "https://example.com/a" in props["RSS 원본 링크"]["rich_text"][0]["text"]["content"]


def test_write_trend_log_entries_calls_create_page_per_entry():
    entries = [
        {"date": "2026-07-27", "keyword": "휴대폰 창업", "source": "데이터랩", "value": 74.0, "vs_yesterday": 12.3, "vs_last_week": 30.0},
        {"date": "2026-07-27", "keyword": "매장 인테리어", "source": "유튜브", "value": 5.0, "vs_yesterday": None, "vs_last_week": None},
    ]
    with patch("notion_writer.notion_api.create_page") as mock_create:
        notion_writer.write_trend_log_entries(entries, "log-db", "token")

    assert mock_create.call_count == 2
    first_call_args = mock_create.call_args_list[0][0]
    assert first_call_args[0] == "log-db"
    assert first_call_args[2] == "token"


def test_write_report_calls_create_page_once():
    with patch("notion_writer.notion_api.create_page", return_value={"id": "page1"}) as mock_create:
        result = notion_writer.write_report(
            "2026-07-27", "창업/프랜차이즈", "요약 내용", ["휴대폰 창업"], ["https://example.com/a"], "report-db", "token"
        )

    assert result == {"id": "page1"}
    mock_create.assert_called_once()
    args = mock_create.call_args[0]
    assert args[0] == "report-db"
    assert args[2] == "token"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_notion_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'notion_writer'`

- [ ] **Step 3: `notion_writer.py` 최소 구현**

```python
import notion_api


def build_log_properties(date, keyword, source, value, vs_yesterday, vs_last_week):
    return {
        "키워드": {"title": [{"text": {"content": keyword}}]},
        "날짜": {"date": {"start": date}},
        "소스": {"select": {"name": source}},
        "값": {"number": value},
        "전일대비": {"number": vs_yesterday},
        "전주대비": {"number": vs_last_week},
    }


def build_report_properties(date, vertical, summary, top_keywords, rss_links):
    links_text = "\n".join(rss_links)
    return {
        "제목": {"title": [{"text": {"content": f"{date} {vertical} 트렌드 리포트"}}]},
        "날짜": {"date": {"start": date}},
        "버티컬": {"select": {"name": vertical}},
        "요약": {"rich_text": [{"text": {"content": summary}}]},
        "급상승 키워드": {"multi_select": [{"name": kw} for kw in top_keywords]},
        "RSS 원본 링크": {"rich_text": [{"text": {"content": links_text}}]},
    }


def write_trend_log_entries(entries, log_db_id, token):
    for entry in entries:
        properties = build_log_properties(
            entry["date"], entry["keyword"], entry["source"], entry["value"], entry["vs_yesterday"], entry["vs_last_week"]
        )
        notion_api.create_page(log_db_id, properties, token)


def write_report(date, vertical, summary, top_keywords, rss_links, report_db_id, token):
    properties = build_report_properties(date, vertical, summary, top_keywords, rss_links)
    return notion_api.create_page(report_db_id, properties, token)
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_notion_writer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add notion_writer.py tests/test_notion_writer.py
git commit -m "feat: write trend log and daily report to notion"
```

---

### Task 8: 오케스트레이터 (`main.py`)

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes 모든 이전 태스크의 함수:
  - `config.load_settings`, `collectors.datalab.chunk_keywords/fetch_datalab_group/normalize_datalab_response`
  - `collectors.rss.fetch_rss_entries/filter_recent_entries`
  - `collectors.youtube.fetch_youtube_trending/normalize_youtube_response`
  - `summarizer.summarize`
  - `notion_writer.write_trend_log_entries/write_report`
- Produces: `main.run(dry_run: bool = False) -> None`, CLI 진입점 (`python main.py`, `python main.py --dry-run`)

이 태스크는 각 collector를 이미 유닛테스트로 검증했으므로, 통합 코드 자체에는 새 로직이 거의 없다(오케스트레이션 배선). 오류 격리(하나의 collector가 실패해도 계속 진행)만 직접 검증한다.

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_main.py`)**

```python
from unittest.mock import patch
import main


SETTINGS = [
    {"keyword": "휴대폰 창업", "vertical": "창업/프랜차이즈", "rss_url": "https://example.com/rss", "active": True},
]


def test_run_continues_when_youtube_collector_fails(capsys):
    with patch("main.config.load_settings", return_value=SETTINGS), \
         patch("main.datalab.fetch_datalab_group", return_value={"results": []}), \
         patch("main.datalab.normalize_datalab_response", return_value={}), \
         patch("main.rss.fetch_rss_entries", return_value=[]), \
         patch("main.rss.filter_recent_entries", return_value=[]), \
         patch("main.youtube.fetch_youtube_trending", side_effect=Exception("quota exceeded")), \
         patch("main.summarizer.summarize", return_value="요약") as mock_summarize, \
         patch("main.notion_writer.write_trend_log_entries") as mock_log, \
         patch("main.notion_writer.write_report") as mock_report, \
         patch.dict("os.environ", {
             "NAVER_CLIENT_ID": "x", "NAVER_CLIENT_SECRET": "x", "YOUTUBE_API_KEY": "x",
             "NOTION_TOKEN": "x", "NOTION_SETTINGS_DB_ID": "x", "NOTION_LOG_DB_ID": "x",
             "NOTION_REPORT_DB_ID": "x", "GEMINI_API_KEY": "x",
         }):
        main.run(dry_run=True)

    captured = capsys.readouterr()
    assert "유튜브" in captured.out
    mock_summarize.assert_called_once()
    mock_log.assert_not_called()
    mock_report.assert_not_called()
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: `main.py` 구현**

```python
import argparse
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

import config
import notion_writer
import summarizer
from collectors import datalab, rss, youtube

KST = timezone(timedelta(hours=9))


def _collect_datalab(keywords, client_id, client_secret, date_str):
    start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    results = {}
    for group in datalab.chunk_keywords(keywords):
        response = datalab.fetch_datalab_group(group, client_id, client_secret, start_date, date_str)
        results.update(datalab.normalize_datalab_response(response))
    return results


def _collect_rss(feed_urls):
    items = []
    for url in feed_urls:
        entries = rss.fetch_rss_entries(url)
        items.extend(rss.filter_recent_entries(entries))
    return items


def _collect_youtube(keywords, api_key):
    results = []
    for keyword in keywords:
        response = youtube.fetch_youtube_trending(keyword, api_key)
        results.extend(youtube.normalize_youtube_response(response))
    return results


def run(dry_run=False):
    load_dotenv()
    date_str = datetime.now(KST).strftime("%Y-%m-%d")

    settings = config.load_settings(os.environ["NOTION_SETTINGS_DB_ID"], os.environ["NOTION_TOKEN"])
    keywords = [row["keyword"] for row in settings]
    feed_urls = [row["rss_url"] for row in settings if row["rss_url"]]
    vertical = settings[0]["vertical"] if settings else "일반"

    datalab_results = {}
    try:
        datalab_results = _collect_datalab(keywords, os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"], date_str)
    except Exception as exc:
        print(f"⚠️ 데이터랩 수집 실패: {exc}")

    rss_items = []
    try:
        rss_items = _collect_rss(feed_urls)
    except Exception as exc:
        print(f"⚠️ RSS 수집 실패: {exc}")

    youtube_results = []
    try:
        youtube_results = _collect_youtube(keywords, os.environ["YOUTUBE_API_KEY"])
    except Exception as exc:
        print(f"⚠️ 유튜브 수집 실패: {exc}")

    summary = summarizer.summarize(vertical, date_str, datalab_results, rss_items, youtube_results, os.environ["GEMINI_API_KEY"])

    if dry_run:
        print(summary)
        return

    log_entries = [
        {"date": date_str, "keyword": kw, "source": "데이터랩", "value": stats["today"], "vs_yesterday": stats["vs_yesterday_pct"], "vs_last_week": stats["vs_last_week_pct"]}
        for kw, stats in datalab_results.items()
    ]
    notion_writer.write_trend_log_entries(log_entries, os.environ["NOTION_LOG_DB_ID"], os.environ["NOTION_TOKEN"])

    top_keywords = list(datalab_results.keys())
    rss_links = [item["link"] for item in rss_items]
    notion_writer.write_report(date_str, vertical, summary, top_keywords, rss_links, os.environ["NOTION_REPORT_DB_ID"], os.environ["NOTION_TOKEN"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
```

`python-dotenv`는 `requirements.txt`에 이미 추가했으므로(Task 1) 별도 설치 불필요. `test_main.py`가 `main.datalab`, `main.rss`, `main.youtube`를 patch 대상으로 쓰므로 `main.py`는 반드시 `from collectors import datalab, rss, youtube` 형태로 임포트해야 한다 (모듈 객체를 그대로 참조해야 patch가 적용됨).

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `pytest tests/test_main.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: 전체 테스트 스위트 실행**

Run: `pytest -v`
Expected: 모든 테스트 PASS (Task 1~8 누적, 총 21개)

- [ ] **Step 6: 커밋**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add orchestrator with per-source failure isolation"
```

---

### Task 9: GitHub Actions 워크플로 + README 설정 가이드

**Files:**
- Create: `.github/workflows/trend-report.yml`
- Create: `README.md`

**Interfaces:** 없음 (설정/문서 태스크, 이전 태스크 코드 변경 없음)

- [ ] **Step 1: 워크플로 작성**

`.github/workflows/trend-report.yml`:
```yaml
name: Trend Report

on:
  schedule:
    - cron: '0 22 * * *'
  workflow_dispatch:

jobs:
  collect-and-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install -r requirements.txt

      - run: python main.py
        env:
          NAVER_CLIENT_ID: ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          NOTION_SETTINGS_DB_ID: ${{ secrets.NOTION_SETTINGS_DB_ID }}
          NOTION_LOG_DB_ID: ${{ secrets.NOTION_LOG_DB_ID }}
          NOTION_REPORT_DB_ID: ${{ secrets.NOTION_REPORT_DB_ID }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

- [ ] **Step 2: README 작성 (시크릿 발급 가이드 포함)**

`README.md`:
```markdown
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

\`\`\`bash
pip install -r requirements.txt
cp .env.example .env  # 값 채우기
python main.py --dry-run   # 노션에 쓰지 않고 콘솔 출력만 확인
python main.py             # 실제 노션에 기록
\`\`\`

## 7. 자동 실행

`.github/workflows/trend-report.yml`이 매일 07:00 KST에 자동 실행됩니다. Actions 탭에서 `Run workflow`로 수동 실행도 가능합니다.
```

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/trend-report.yml README.md
git commit -m "docs: add github actions workflow and setup guide"
```

---

## Self-Review Notes

- **스펙 커버리지:** 데이터랩(Task 3)/RSS(Task 4)/유튜브(Task 5) 3개 소스, 노션 설정 DB 연동(Task 2), Gemini 요약(Task 6), 노션 기록(Task 7), 소스별 실패 격리(Task 8), GitHub Actions + 시크릿 가이드(Task 9) 모두 태스크로 매핑됨. v2 후보(검색광고 API, 블로그/카페 검색, 알림)는 의도적으로 범위 밖.
- **플레이스홀더 스캔:** TBD/TODO 없음. 모든 스텝에 실행 가능한 코드 포함.
- **타입 일관성 확인:** `datalab.normalize_datalab_response` 반환 키(`today, yesterday, last_week, vs_yesterday_pct, vs_last_week_pct`)가 Task 6 `build_prompt`와 Task 8 `_collect_datalab`/`run`에서 동일하게 사용됨. `notion_writer.build_log_properties`의 인자 이름(`vs_yesterday, vs_last_week`)과 Task 8에서 만드는 `log_entries` dict 키가 일치함. `config.load_settings`가 반환하는 dict 키(`keyword, vertical, rss_url, active`)가 Task 8 전체에서 동일하게 사용됨. Task 8 테스트가 `main.datalab`/`main.rss`/`main.youtube`를 patch하므로 `main.py`의 import 방식(`from collectors import datalab, rss, youtube`)을 명시해 불일치를 방지함.

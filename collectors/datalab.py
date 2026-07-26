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

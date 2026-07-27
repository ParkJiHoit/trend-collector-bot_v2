from unittest.mock import patch, MagicMock
import requests
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


def test_fetch_datalab_group_retries_once_on_timeout_then_succeeds():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = RAW_RESPONSE
    with patch(
        "collectors.datalab.requests.post",
        side_effect=[requests.exceptions.ConnectTimeout("timed out"), fake_response],
    ) as mock_post:
        result = datalab.fetch_datalab_group(["휴대폰 창업"], "id", "secret", "2026-07-19", "2026-07-26")

    assert result == RAW_RESPONSE
    assert mock_post.call_count == 2


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


def test_normalize_datalab_response_skips_empty_data():
    empty_response = {
        "results": [{"title": "검색량 없는 키워드", "keywords": ["검색량 없는 키워드"], "data": []}]
    }
    result = datalab.normalize_datalab_response(empty_response)

    assert result == {}

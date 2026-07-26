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

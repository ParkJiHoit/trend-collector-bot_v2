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

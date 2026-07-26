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

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

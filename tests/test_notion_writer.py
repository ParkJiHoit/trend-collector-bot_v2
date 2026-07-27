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
    datalab_results = {"휴대폰 창업": {"today": 74.0, "vs_yesterday_pct": 12.3, "vs_last_week_pct": 30.0}}
    rss_items = [{"title": "릴스 후킹 문구 트렌드", "link": "https://example.com/a"}]
    youtube_results = [{"title": "휴대폰 창업 브이로그", "video_id": "abc123", "channel": "창업채널"}]

    with patch("notion_writer.notion_api.create_page", return_value={"id": "page1"}) as mock_create:
        result = notion_writer.write_report(
            "2026-07-27", "창업/프랜차이즈", "요약 내용", datalab_results, rss_items, youtube_results, "report-db", "token"
        )

    assert result == {"id": "page1"}
    mock_create.assert_called_once()
    args = mock_create.call_args[0]
    kwargs = mock_create.call_args[1]
    assert args[0] == "report-db"
    assert args[2] == "token"
    assert args[1]["급상승 키워드"]["multi_select"] == [{"name": "휴대폰 창업"}]
    assert len(kwargs["children"]) > 0


def test_build_report_blocks_includes_all_sections():
    datalab_results = {"휴대폰 창업": {"today": 74.0, "vs_yesterday_pct": 12.3, "vs_last_week_pct": 30.0}}
    rss_items = [{"title": "릴스 후킹 문구 트렌드", "link": "https://example.com/a"}]
    youtube_results = [{"title": "휴대폰 창업 브이로그", "video_id": "abc123", "channel": "창업채널"}]

    blocks = notion_writer.build_report_blocks("최종 요약", datalab_results, rss_items, youtube_results)

    text_contents = [
        block[block["type"]]["rich_text"][0]["text"]["content"]
        for block in blocks
    ]
    assert "최종 요약" in text_contents
    assert any("휴대폰 창업" in text for text in text_contents)
    assert any("릴스 후킹 문구 트렌드" in text for text in text_contents)
    assert any("휴대폰 창업 브이로그" in text for text in text_contents)


def test_datalab_bullet_rounds_percentages_and_marks_missing_as_dash():
    datalab_results = {"휴대폰 창업": {"today": 93.33333, "vs_yesterday_pct": -6.666669999999996, "vs_last_week_pct": None}}

    blocks = notion_writer.build_report_blocks("요약", datalab_results, [], [])

    bullet = next(b for b in blocks if b["type"] == "bulleted_list_item")
    spans = bullet["bulleted_list_item"]["rich_text"]
    assert spans[0]["text"]["content"] == "휴대폰 창업"
    assert spans[1]["text"]["content"] == ": 93.3 (전일대비 -6.7% · 전주대비 -)"


def test_youtube_bullets_are_deduplicated_by_video_id():
    youtube_results = [
        {"title": "영상 A", "video_id": "id1", "channel": "채널1"},
        {"title": "영상 A", "video_id": "id1", "channel": "채널1"},
        {"title": "영상 B", "video_id": "id2", "channel": "채널2"},
    ]

    blocks = notion_writer.build_report_blocks("요약", {}, [], youtube_results)

    video_bullets = [
        b for b in blocks
        if b["type"] == "bulleted_list_item" and b["bulleted_list_item"]["rich_text"][0]["text"].get("link")
    ]
    assert len(video_bullets) == 2

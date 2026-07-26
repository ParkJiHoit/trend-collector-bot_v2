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

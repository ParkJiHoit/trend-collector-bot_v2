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

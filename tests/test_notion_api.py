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

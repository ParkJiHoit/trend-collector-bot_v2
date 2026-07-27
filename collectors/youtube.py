import html

import requests

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def fetch_youtube_trending(keyword, api_key, max_results=5):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "order": "viewCount",
        "maxResults": max_results,
    }
    headers = {"X-Goog-Api-Key": api_key}
    response = requests.get(YOUTUBE_SEARCH_URL, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def normalize_youtube_response(response):
    normalized = []
    for item in response["items"]:
        snippet = item["snippet"]
        normalized.append(
            {
                "title": html.unescape(snippet["title"]),
                "video_id": item["id"]["videoId"],
                "channel": html.unescape(snippet["channelTitle"]),
                "published_at": snippet["publishedAt"],
            }
        )
    return normalized

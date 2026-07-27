import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def build_prompt(vertical, date, datalab_results, rss_items, youtube_results):
    lines = [f"{date} {vertical} 트렌드 리포트를 작성해줘.", "", "[데이터랩 검색량]"]
    for keyword, stats in datalab_results.items():
        lines.append(
            f"- {keyword}: 검색지수 {stats['today']} "
            f"(전일대비 {stats['vs_yesterday_pct']}%, 전주대비 {stats['vs_last_week_pct']}%)"
        )

    lines.append("")
    lines.append("[RSS 신규 글]")
    for item in rss_items:
        lines.append(f"- {item['title']} ({item['link']})")

    lines.append("")
    lines.append("[유튜브 급상승]")
    for video in youtube_results:
        lines.append(f"- {video['title']} ({video['channel']})")

    lines.append("")
    lines.append("위 데이터를 바탕으로 급상승 키워드, 관심 증가, 유튜브 급상승, RSS 수집 항목을 정리한 한국어 리포트를 작성해줘.")
    return "\n".join(lines)


def call_gemini(prompt, api_key):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(GEMINI_URL, params={"key": api_key}, json=body, timeout=30)
    if not response.ok:
        print(f"⚠️ Gemini API error {response.status_code}: {response.text}")
    response.raise_for_status()
    return response.json()


def extract_gemini_text(response):
    return response["candidates"][0]["content"]["parts"][0]["text"]


def summarize(vertical, date, datalab_results, rss_items, youtube_results, api_key):
    prompt = build_prompt(vertical, date, datalab_results, rss_items, youtube_results)
    response = call_gemini(prompt, api_key)
    return extract_gemini_text(response)

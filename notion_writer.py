import notion_api


def build_log_properties(date, keyword, source, value, vs_yesterday, vs_last_week):
    return {
        "키워드": {"title": [{"text": {"content": keyword}}]},
        "날짜": {"date": {"start": date}},
        "소스": {"select": {"name": source}},
        "값": {"number": value},
        "전일대비": {"number": vs_yesterday},
        "전주대비": {"number": vs_last_week},
    }


RICH_TEXT_CHUNK_SIZE = 2000


def _chunk_rich_text(text):
    if not text:
        return [{"text": {"content": ""}}]
    return [
        {"text": {"content": text[i:i + RICH_TEXT_CHUNK_SIZE]}}
        for i in range(0, len(text), RICH_TEXT_CHUNK_SIZE)
    ]


def build_report_properties(date, vertical, summary, top_keywords, rss_links):
    links_text = "\n".join(rss_links)
    return {
        "제목": {"title": [{"text": {"content": f"{date} {vertical} 트렌드 리포트"}}]},
        "날짜": {"date": {"start": date}},
        "버티컬": {"select": {"name": vertical}},
        "요약": {"rich_text": _chunk_rich_text(summary)},
        "급상승 키워드": {"multi_select": [{"name": kw} for kw in top_keywords]},
        "RSS 원본 링크": {"rich_text": _chunk_rich_text(links_text)},
    }


def _heading(text):
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _paragraph(text):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _bullet(text, link=None):
    text_obj = {"type": "text", "text": {"content": text}}
    if link:
        text_obj["text"]["link"] = {"url": link}
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [text_obj]}}


def _bullet_with_bold_prefix(bold_text, rest_text):
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [
                {"type": "text", "text": {"content": bold_text}, "annotations": {"bold": True}},
                {"type": "text", "text": {"content": rest_text}},
            ]
        },
    }


def _fmt_num(value):
    if value is None:
        return "-"
    rounded = round(value, 1)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)


def _fmt_pct(value):
    if value is None:
        return "-"
    rounded = round(value, 1)
    sign = "+" if rounded > 0 else ""
    text = str(int(rounded)) if rounded == int(rounded) else str(rounded)
    return f"{sign}{text}%"


def _dedupe_by_video_id(youtube_results):
    seen = set()
    deduped = []
    for video in youtube_results:
        if video["video_id"] in seen:
            continue
        seen.add(video["video_id"])
        deduped.append(video)
    return deduped


def build_report_blocks(summary, datalab_results, rss_items, youtube_results):
    blocks = [_heading("AI 요약"), _paragraph(summary or "(요약 없음)"), _heading("데이터랩 검색 지수")]

    if datalab_results:
        for keyword, stats in datalab_results.items():
            detail = f": {_fmt_num(stats['today'])} (전일대비 {_fmt_pct(stats['vs_yesterday_pct'])} · 전주대비 {_fmt_pct(stats['vs_last_week_pct'])})"
            blocks.append(_bullet_with_bold_prefix(keyword, detail))
    else:
        blocks.append(_paragraph("(수집된 데이터 없음)"))

    blocks.append(_heading("유튜브 급상승 영상"))
    deduped_videos = _dedupe_by_video_id(youtube_results)
    if deduped_videos:
        for video in deduped_videos[:10]:
            blocks.append(_bullet_with_bold_prefix(
                video["title"], f" — {video['channel']}"
            ))
            blocks[-1]["bulleted_list_item"]["rich_text"][0]["text"]["link"] = {"url": f"https://youtu.be/{video['video_id']}"}
    else:
        blocks.append(_paragraph("(수집된 영상 없음)"))

    blocks.append(_heading("RSS 신규 글"))
    if rss_items:
        for item in rss_items:
            blocks.append(_bullet(item["title"], link=item["link"]))
    else:
        blocks.append(_paragraph("(수집된 글 없음)"))

    return blocks


def write_trend_log_entries(entries, log_db_id, token):
    for entry in entries:
        properties = build_log_properties(
            entry["date"], entry["keyword"], entry["source"], entry["value"], entry["vs_yesterday"], entry["vs_last_week"]
        )
        notion_api.create_page(log_db_id, properties, token)


def write_report(date, vertical, summary, datalab_results, rss_items, youtube_results, report_db_id, token):
    top_keywords = list(datalab_results.keys())
    rss_links = [item["link"] for item in rss_items]
    properties = build_report_properties(date, vertical, summary, top_keywords, rss_links)
    children = build_report_blocks(summary, datalab_results, rss_items, youtube_results)
    return notion_api.create_page(report_db_id, properties, token, children=children)

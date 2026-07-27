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


def build_report_properties(date, vertical, summary, top_keywords, rss_links):
    links_text = "\n".join(rss_links)
    return {
        "제목": {"title": [{"text": {"content": f"{date} {vertical} 트렌드 리포트"}}]},
        "날짜": {"date": {"start": date}},
        "버티컬": {"select": {"name": vertical}},
        "요약": {"rich_text": [{"text": {"content": summary}}]},
        "급상승 키워드": {"multi_select": [{"name": kw} for kw in top_keywords]},
        "RSS 원본 링크": {"rich_text": [{"text": {"content": links_text}}]},
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


def build_report_blocks(summary, datalab_results, rss_items, youtube_results):
    blocks = [_heading("AI 요약"), _paragraph(summary or "(요약 없음)"), _heading("데이터랩 검색 지수")]

    if datalab_results:
        for keyword, stats in datalab_results.items():
            blocks.append(_bullet(
                f"{keyword}: {stats['today']} (전일대비 {stats['vs_yesterday_pct']}%, 전주대비 {stats['vs_last_week_pct']}%)"
            ))
    else:
        blocks.append(_paragraph("(수집된 데이터 없음)"))

    blocks.append(_heading("유튜브 급상승 영상"))
    if youtube_results:
        for video in youtube_results:
            blocks.append(_bullet(f"{video['title']} - {video['channel']}", link=f"https://youtu.be/{video['video_id']}"))
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

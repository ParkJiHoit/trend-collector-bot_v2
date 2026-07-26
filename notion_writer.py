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


def write_trend_log_entries(entries, log_db_id, token):
    for entry in entries:
        properties = build_log_properties(
            entry["date"], entry["keyword"], entry["source"], entry["value"], entry["vs_yesterday"], entry["vs_last_week"]
        )
        notion_api.create_page(log_db_id, properties, token)


def write_report(date, vertical, summary, top_keywords, rss_links, report_db_id, token):
    properties = build_report_properties(date, vertical, summary, top_keywords, rss_links)
    return notion_api.create_page(report_db_id, properties, token)

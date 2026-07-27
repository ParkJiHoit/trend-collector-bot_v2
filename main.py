import argparse
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

import config
import notion_writer
import summarizer
from collectors import datalab, rss, youtube

KST = timezone(timedelta(hours=9))


def _collect_datalab(keywords, client_id, client_secret, date_str):
    start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    results = {}
    for group in datalab.chunk_keywords(keywords):
        response = datalab.fetch_datalab_group(group, client_id, client_secret, start_date, date_str)
        results.update(datalab.normalize_datalab_response(response))
    return results


RSS_RECENCY_HOURS = 24 * 7


def _collect_rss(feed_urls):
    items = []
    for url in feed_urls:
        entries = rss.fetch_rss_entries(url)
        recent = rss.filter_recent_entries(entries, since_hours=RSS_RECENCY_HOURS)
        print(f"ℹ️ RSS {url}: 전체 {len(entries)}건 수집, {RSS_RECENCY_HOURS}시간 이내 {len(recent)}건")
        items.extend(recent)
    return items


def _collect_youtube(keywords, api_key):
    results = []
    for keyword in keywords:
        response = youtube.fetch_youtube_trending(keyword, api_key)
        results.extend(youtube.normalize_youtube_response(response))
    return results


def run(dry_run=False):
    load_dotenv()
    date_str = datetime.now(KST).strftime("%Y-%m-%d")

    settings = config.load_settings(os.environ["NOTION_SETTINGS_DB_ID"], os.environ["NOTION_TOKEN"])
    keywords = [row["keyword"] for row in settings]
    feed_urls = [row["rss_url"] for row in settings if row["rss_url"]]
    vertical = settings[0]["vertical"] if settings else "일반"

    failures = []

    datalab_results = {}
    try:
        datalab_results = _collect_datalab(keywords, os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"], date_str)
    except Exception as exc:
        failures.append(f"⚠️ 데이터랩 수집 실패: {exc}")

    rss_items = []
    try:
        rss_items = _collect_rss(feed_urls)
    except Exception as exc:
        failures.append(f"⚠️ RSS 수집 실패: {exc}")

    youtube_results = []
    try:
        youtube_results = _collect_youtube(keywords, os.environ["YOUTUBE_API_KEY"])
    except Exception as exc:
        failures.append(f"⚠️ 유튜브 수집 실패: {exc}")

    for failure in failures:
        print(failure)

    summary = ""
    try:
        summary = summarizer.summarize(vertical, date_str, datalab_results, rss_items, youtube_results, os.environ["GEMINI_API_KEY"])
    except Exception as exc:
        failures.append(f"⚠️ AI 요약 실패: {exc}")
        print(failures[-1])
    if failures:
        summary = summary + "\n\n" + "\n".join(failures)

    if dry_run:
        print(summary)
        return

    log_entries = [
        {"date": date_str, "keyword": kw, "source": "데이터랩", "value": stats["today"], "vs_yesterday": stats["vs_yesterday_pct"], "vs_last_week": stats["vs_last_week_pct"]}
        for kw, stats in datalab_results.items()
    ]
    notion_writer.write_trend_log_entries(log_entries, os.environ["NOTION_LOG_DB_ID"], os.environ["NOTION_TOKEN"])

    notion_writer.write_report(
        date_str, vertical, summary, datalab_results, rss_items, youtube_results,
        os.environ["NOTION_REPORT_DB_ID"], os.environ["NOTION_TOKEN"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)

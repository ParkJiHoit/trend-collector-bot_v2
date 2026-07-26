import socket
from calendar import timegm
from datetime import datetime, timedelta, timezone

import feedparser


def fetch_rss_entries(feed_url, timeout=10):
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        feed = feedparser.parse(feed_url)
    finally:
        socket.setdefaulttimeout(previous_timeout)
    entries = []
    for entry in feed.entries:
        entries.append(
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published_parsed": entry.get("published_parsed"),
            }
        )
    return entries


def filter_recent_entries(entries, since_hours=48, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=since_hours)
    recent = []
    for entry in entries:
        parsed = entry.get("published_parsed")
        if not parsed:
            continue
        published = datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
        if published >= cutoff:
            recent.append(entry)
    return recent

#!/usr/bin/env python3
"""Fetch recent items from a curated list of RSS/Atom feeds (newsletters, VC
blogs, publications). Edit FEEDS below to match what you actually follow —
these are just a verified starting point.
"""
import datetime

import feedparser

LOOKBACK_HOURS = 48
MAX_PER_FEED = 6

FEEDS = [
    {"name": "Import AI", "category": "newsletter", "url": "https://importai.substack.com/feed"},
    {"name": "Ben's Bites", "category": "newsletter", "url": "https://www.bensbites.com/feed"},
    {"name": "Sequoia Capital", "category": "VC", "url": "https://www.sequoiacap.com/feed/"},
    {"name": "Benedict Evans", "category": "VC", "url": "https://www.ben-evans.com/benedictevans?format=rss"},
    {"name": "NYT Technology", "category": "publication", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"},
    {"name": "The Verge (AI)", "category": "publication", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "Ars Technica", "category": "publication", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
]


def entry_datetime(entry):
    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            return datetime.datetime(*value[:6], tzinfo=datetime.timezone.utc)
    return None


def fetch_feed(feed_def):
    try:
        parsed = feedparser.parse(feed_def["url"])
    except Exception:
        return []

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=LOOKBACK_HOURS)
    items = []
    for entry in parsed.entries[: MAX_PER_FEED * 3]:
        dt = entry_datetime(entry)
        if dt and dt < cutoff:
            continue
        title = entry.get("title", "").strip()
        if not title:
            continue
        summary = (entry.get("summary", "") or "")[:300]
        link = entry.get("link", "")
        items.append({"title": title, "summary": summary, "url": link})
        if len(items) >= MAX_PER_FEED:
            break
    return items


def main():
    sections = []
    for feed_def in FEEDS:
        items = fetch_feed(feed_def)
        if not items:
            continue
        lines = [f"## {feed_def['name']} ({feed_def['category']})"]
        for item in items:
            lines.append(f"- {item['title']} ({item['url']})")
            if item["summary"]:
                lines.append(f"  {item['summary']}")
        sections.append("\n".join(lines))

    if sections:
        print("\n\n".join(sections))


if __name__ == "__main__":
    main()

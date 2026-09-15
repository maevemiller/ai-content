#!/usr/bin/env python3
"""Fetch recent AI-related Hacker News stories via the public Algolia search API (no auth needed)."""
import datetime
import json
import urllib.error
import urllib.parse
import urllib.request

QUERIES = ["AI", "LLM", "agent", "Claude", "GPT"]
MAX_PER_QUERY = 6
LOOKBACK_HOURS = 30


def fetch(query, since_ts):
    params = urllib.parse.urlencode(
        {
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{since_ts},points>5",
            "hitsPerPage": MAX_PER_QUERY,
        }
    )
    url = f"https://hn.algolia.com/api/v1/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.load(resp).get("hits", [])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return []


def main():
    since_ts = int((datetime.datetime.now() - datetime.timedelta(hours=LOOKBACK_HOURS)).timestamp())
    seen_ids = set()
    lines = ["## Hacker News (recent AI-related stories)"]
    found = False

    for query in QUERIES:
        for hit in fetch(query, since_ts):
            object_id = hit.get("objectID")
            if object_id in seen_ids:
                continue
            seen_ids.add(object_id)
            title = hit.get("title", "").strip()
            if not title:
                continue
            points = hit.get("points", 0)
            comments = hit.get("num_comments", 0)
            hn_url = f"https://news.ycombinator.com/item?id={object_id}"
            lines.append(f"- [{points} pts, {comments} comments] {title} ({hn_url})")
            found = True

    if found:
        print("\n".join(lines))


if __name__ == "__main__":
    main()

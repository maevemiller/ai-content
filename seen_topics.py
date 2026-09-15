"""Tracks topics (by URL) that have already appeared in a past digest, so the
same story doesn't get re-surfaced day after day just because it's still
trending in the raw fetched material. Separate from the backlog, which is for
topics you deliberately want to come back to — this is the opposite: things
already shown once, picked or not, shouldn't repeat.
"""
import json
from pathlib import Path

SEEN_FILE = Path(__file__).parent / "state" / "seen_topics.json"
MAX_STORED = 300  # plenty of runway; a JSON list of URLs is tiny


def load():
    if not SEEN_FILE.exists():
        return []
    return json.loads(SEEN_FILE.read_text())


def record(topics):
    """Add these topics' URLs (and titles, for url-less items) to the seen
    list, keeping only the most recent MAX_STORED entries."""
    seen = load()
    existing = {entry["key"] for entry in seen}
    for t in topics:
        key = t.get("url") or t.get("title", "")
        if key and key not in existing:
            seen.append({"key": key, "title": t.get("title", "")})
            existing.add(key)
    seen = seen[-MAX_STORED:]
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def is_seen(topic, seen_keys):
    key = topic.get("url") or topic.get("title", "")
    return bool(key) and key in seen_keys


def seen_keys_set():
    return {entry["key"] for entry in load()}

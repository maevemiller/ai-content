"""Persistent backlog of interesting-but-not-today topics for the news pipeline.

Topics move here when you reply to a digest with more than one number (the
first is today's pick; the rest get saved here). They resurface at the top
of every future digest until you finally pick one (removing it) or leave it
indefinitely (no automatic expiry — this list is small and yours to prune).
"""
import datetime
import json
from pathlib import Path

BACKLOG_FILE = Path(__file__).parent / "state" / "backlog.json"


def load():
    if not BACKLOG_FILE.exists():
        return []
    return json.loads(BACKLOG_FILE.read_text())


def save(items):
    BACKLOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKLOG_FILE.write_text(json.dumps(items, indent=2))


def add(topic):
    """Add a topic dict (type/source/title/description/url) to the backlog,
    skipping if a topic with the same title is already there."""
    items = load()
    if any(t["title"] == topic["title"] for t in items):
        return
    entry = dict(topic)
    entry["date_added"] = datetime.date.today().strftime("%Y-%m-%d")
    entry.pop("number", None)
    items.append(entry)
    save(items)


def remove(title):
    items = load()
    items = [t for t in items if t["title"] != title]
    save(items)

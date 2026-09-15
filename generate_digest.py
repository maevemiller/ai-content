#!/usr/bin/env python3
"""Morning step for the news pipeline: fetch sources, merge with the backlog,
build a numbered digest of topics + newly-spotted concepts (each tagged with
its source and a major/niche tier), send it to Telegram along with the daily
checklist, and save state so a later reply can pick a topic.
"""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import backlog
import seen_topics
import telegram_lib

DIR = Path(__file__).parent
STATE_FILE = DIR / "state" / "news_state.json"
DIGESTS_DIR = Path.home() / "content-log" / "digests"
SCRIPTS_DIR = Path.home() / "content-log" / "scripts"
DRAFTS_DIR = Path.home() / "learning-log" / "drafts"

TOPIC_LINE_RE = re.compile(
    r"^\s*(\d+)\.\s*\[(major|niche)/(news|concept)/([^\]/]+)\]\s*(.+?)\s*—\s*(.+?)(?:\s*\((https?://[^\s)]+)\))?\s*$"
)

FETCHERS = ["fetch_reddit.py", "fetch_hn.py", "fetch_arxiv.py", "fetch_rss.py", "fetch_twitter.py"]


def fetch_sources():
    sections = []
    for fetcher in FETCHERS:
        output = subprocess.run(["python3", str(DIR / fetcher)], capture_output=True, text=True).stdout
        if output.strip():
            sections.append(output.strip())

    inbox_output = subprocess.run(["python3", str(DIR / "inbox.py")], capture_output=True, text=True).stdout
    if inbox_output.strip():
        sections.append(inbox_output.strip())

    return "\n\n".join(sections)


def build_digest_prompt(already_shown):
    already_shown_block = ""
    if already_shown:
        titles = "\n".join(f"- {entry['title']}" for entry in already_shown if entry.get("title"))
        already_shown_block = (
            "Already shown in a previous digest — do NOT include these STORIES/EVENTS again, "
            "even if a new article, follow-up, or differently-worded headline about the SAME "
            "underlying event shows up in the material below (a new URL or a new day's coverage "
            "of the same essay/announcement/incident is still a repeat — judge by the actual "
            "event, not by exact title or URL matching). Pick something genuinely different "
            "instead:\n"
            f"{titles}\n\n"
        )

    return (
        f"{already_shown_block}"
        "Below is today's raw material from several sources (each under its own '## ' header), "
        "which may include Reddit, Hacker News, arXiv papers, newsletters, VC blogs, publications, "
        "and Twitter/X. Be SELECTIVE — produce a short numbered digest of only 3-6 items total for "
        "me to choose from for a short video I'll film today. This is a curated shortlist, not a "
        "comprehensive roundup. Mix genuinely interesting NEWS items (things that happened) with any "
        "NEW/EMERGING CONCEPTS OR TERMS you notice appearing in the discussion that would be worth "
        "explaining to someone learning AI, but only include something if it's genuinely worth my "
        "attention today — cut anything borderline rather than padding the count.\n\n"
        "Tag EVERY item with a tier:\n"
        "- major: the biggest, most-discussed story/stories of the day — the thing someone following "
        "AI news would already be seeing everywhere (a frontier lab CEO publishing a major essay/policy "
        "statement, a significant model release, major funding/acquisition news, a widely-covered "
        "controversy). If multiple sources independently cover the same story, or a story is echoed "
        "across several of the fetched sources, that is a strong signal it belongs here, not in niche. "
        "Include 1-3 major items — don't leave this empty just because nothing looks flashy, the most "
        "widely-covered story of the day is still major even if it's a serious/policy topic rather than "
        "a flashy launch, but don't force it past 3 either.\n"
        "- niche: real and worth knowing, but not mainstream-huge — an interesting paper, a smaller "
        "product, an emerging technique, active niche discussion. Include 1-3 of the best ones, not "
        "every candidate.\n\n"
        "Output STRICTLY as one line per item, in exactly this format, nothing else — ONE bracket "
        "group with tier, type, and source separated by slashes, do not use separate brackets for "
        "each:\n"
        "N. [major/news/Source Name] Title — one-line description (url)\n"
        "or\n"
        "N. [niche/concept/Source Name] Title — one-line description (url)\n"
        "(tier is major or niche; type is news or concept; any combination is valid; source name "
        "must not itself contain a '/' character)\n\n"
        "Source Name should be a short human-readable label for which source this came from (e.g. "
        "'Reddit r/MachineLearning', 'Hacker News', 'arXiv', 'Import AI', 'NYT', 'The Verge', "
        "'Twitter/X'). If a story is covered by more than one source, name the most authoritative one "
        "but you can mention the others in the description. Always include the url in parens if the "
        "source material had one. No preamble, no headers, no extra commentary — just the numbered lines."
    )


def parse_fresh_topics(digest_text, start_number):
    topics = []
    number = start_number
    for line in digest_text.splitlines():
        m = TOPIC_LINE_RE.match(line)
        if not m:
            continue
        _orig_number, tier, kind, source, title, description, url = m.groups()
        source = source.strip()
        topics.append(
            {
                "number": number,
                "tier": tier,
                "type": kind,
                "source": source.strip(),
                "title": title.strip(),
                "description": description.strip(),
                "url": url or "",
                "origin": "fresh",
            }
        )
        number += 1
    return topics


def build_checklist(date):
    items = []
    tweet_draft = DRAFTS_DIR / f"{date}.txt"
    items.append(("Sign off on yesterday's/today's tweet thread (check Telegram)", tweet_draft.exists()))
    concept_script = SCRIPTS_DIR / f"{date}-concept.md"
    items.append(("Film today's concept video", concept_script.exists()))
    items.append(("Pick + film today's news video (see topics above)", False))
    items.append(("Write for 30 min (start_essay.sh)", False))

    lines = ["Today's checklist:"]
    for label, done in items:
        mark = "✅" if done else "⬜"
        lines.append(f"{mark} {label}")
    return "\n".join(lines)


def format_topic_line(topic):
    url_part = f" ({topic['url']})" if topic.get("url") else ""
    origin_tag = " [from backlog]" if topic.get("origin") == "backlog" else ""
    return f"{topic['number']}. [{topic['type']}] [{topic['source']}]{origin_tag} {topic['title']} — {topic['description']}{url_part}"


def format_grouped_digest(topics):
    """Group topics into Major/Pressing and Niche/Interesting sections for
    Telegram display, while keeping numbering continuous across both groups
    so replying with a number still works unambiguously. Backlog items
    (which predate the tier field, or came from before this feature existed)
    default to 'major' tier bucket only if explicitly tagged; otherwise they
    land in niche so nothing old causes a crash."""
    major = [t for t in topics if t.get("tier") == "major"]
    niche = [t for t in topics if t.get("tier") != "major"]

    sections = []
    if major:
        sections.append("🔥 MAJOR / PRESSING\n" + "\n".join(format_topic_line(t) for t in major))
    if niche:
        sections.append("🔍 NICHE / INTERESTING\n" + "\n".join(format_topic_line(t) for t in niche))
    return "\n\n".join(sections)


def main():
    date = datetime.date.today().strftime("%Y-%m-%d")

    backlog_items = backlog.load()
    backlog_topics = []
    for i, item in enumerate(backlog_items, start=1):
        topic = dict(item)
        topic["number"] = i
        topic["origin"] = "backlog"
        backlog_topics.append(topic)

    # Backlog items are always "already shown" — make sure they're recorded
    # even if they predate this tracking, so fresh generation never proposes
    # a duplicate of something already sitting in the backlog.
    seen_topics.record(backlog_topics)
    already_shown = seen_topics.load()

    source_text = fetch_sources()

    fresh_topics = []
    generation_failed = False
    if len(source_text.strip()) >= 20:
        prompt = build_digest_prompt(already_shown)
        result = subprocess.run(
            [
                "claude", "-p", "--no-session-persistence",
                "--disallowedTools", "Write", "Edit", "Bash", "NotebookEdit", "Agent", "WebFetch", "WebSearch",
                "--", prompt,
            ],
            input=source_text,
            capture_output=True,
            text=True,
        )
        digest_text = result.stdout.strip()
        fresh_topics = parse_fresh_topics(digest_text, start_number=len(backlog_topics) + 1)
        parsed_count = len(fresh_topics)

        # Safety net in case the model repeats something despite the
        # instruction not to — drop exact URL/title repeats of past digests.
        seen_keys = seen_topics.seen_keys_set()
        fresh_topics = [t for t in fresh_topics if not seen_topics.is_seen(t, seen_keys)]

        if parsed_count == 0:
            # We had real source material but got zero usable topics back —
            # this is a failure (bad/empty claude output, timeout, whatever),
            # not "no news today". Silently falling back to backlog-only here
            # previously hid real generation failures as if they were normal.
            generation_failed = True
            print(
                f"Digest generation returned no parseable topics despite "
                f"{len(source_text)} chars of source material. "
                f"returncode={result.returncode}, stderr={result.stderr.strip()[-500:]}, "
                f"raw stdout={digest_text[:1000]!r}",
                file=sys.stderr,
            )

    MAX_TOTAL = 6
    remaining = max(0, MAX_TOTAL - len(backlog_topics))
    # Prompt compliance on item count isn't 100% reliable, and backlog items
    # add on top of whatever the model generates — enforce the cap in code.
    # Backlog items are kept in full (already a curated, persistent
    # shortlist); remaining slots fill from fresh topics, major-tier first.
    fresh_topics = sorted(fresh_topics, key=lambda t: t.get("tier") != "major")[:remaining]
    topics = backlog_topics[:MAX_TOTAL] + fresh_topics

    # Number in the same order they'll actually be displayed (major section
    # first, then niche) — not construction order (backlog first, then
    # fresh) — so numbering reads top-to-bottom instead of jumping around.
    topics = sorted(topics, key=lambda t: t.get("tier") != "major")
    for i, t in enumerate(topics, start=1):
        t["number"] = i

    if not topics:
        print("No topics available today (no fresh material and empty backlog).", file=sys.stderr)
        return

    # Only fresh topics need recording — backlog items were already recorded
    # as "seen" the day they first appeared as fresh topics.
    seen_topics.record(fresh_topics)

    digest_text_full = format_grouped_digest(topics)

    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    (DIGESTS_DIR / f"{date}.md").write_text(digest_text_full + "\n")

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "date": date,
        "status": "awaiting_topic_pick",
        "topics": topics,
        "current_topic": None,
        "current_script": None,
        "script_path": None,
        "revision_count": 0,
        "updated_at": datetime.datetime.now().isoformat(),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))

    checklist = build_checklist(date)
    warning = (
        "⚠️ Today's fresh news generation failed silently before — this digest is backlog-only, "
        "not a real reflection of today's news. Check run_morning.err.log.\n\n"
        if generation_failed
        else ""
    )
    message = "\n".join(
        [
            f"AI content digest — {date}",
            "",
            warning + digest_text_full,
            "",
            "Reply with a number to pick today's news video topic.",
            "Reply with several numbers (e.g. '3,5,7') to pick the first as today's topic and save the rest to your backlog for another day.",
            "",
            checklist,
        ]
    )

    telegram_lib.send_message(message)
    status = "FAILED (backlog-only fallback)" if generation_failed else "ok"
    print(f"Digest sent to Telegram, {len(topics)} topics ({len(backlog_topics)} from backlog). Generation: {status}")


if __name__ == "__main__":
    main()

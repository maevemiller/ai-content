#!/usr/bin/env python3
"""Poll Telegram for replies and advance the news-pipeline state machine:

  awaiting_topic_pick --(reply with number(s))--> generate script for the
      first number; any additional numbers get saved to the backlog --> awaiting_review
  awaiting_review     --(reply "approved" etc.)--> done
  awaiting_review     --(any other reply)--> revise script, stay in awaiting_review

Run periodically (every few minutes) via launchd. No-ops quickly if there are
no new messages or no active state.
"""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import backlog
import telegram_lib

sys.path.insert(0, str(Path.home() / "dev" / "learning-tweet"))
import thread_review  # noqa: E402

sys.path.insert(0, str(Path.home() / "dev" / "nyc-events"))
import nyc_events_review  # noqa: E402

DIR = Path(__file__).parent
STATE_FILE = DIR / "state" / "news_state.json"
OFFSET_FILE = DIR / "state" / "telegram_offset.txt"
SCRIPTS_DIR = Path.home() / "content-log" / "scripts"

APPROVAL_RE = re.compile(
    r"^\s*(approved?|good|great|done|yes|ok(ay)?|lgtm|looks good|👍|perfect|ship it)\s*!?\s*$",
    re.IGNORECASE,
)
NUMBER_LIST_RE = re.compile(r"\d+")


def load_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def run_claude(prompt, stdin_text=""):
    result = subprocess.run(
        [
            "claude", "-p", "--no-session-persistence",
            "--disallowedTools", "Write", "Edit", "Bash", "NotebookEdit", "Agent", "WebFetch", "WebSearch",
            "--", prompt,
        ],
        input=stdin_text,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


STYLE_CLAUSE = (
    "Sound like a real person talking, not an AI: no filler like 'it's worth noting' or "
    "'game-changer' or 'at the end of the day', no throat-clearing intros, no corporate tone. "
    "Short, direct sentences someone would actually say out loud."
)


def sources_footer(topic):
    url_part = f" ({topic['url']})" if topic.get("url") else ""
    return f"\n\n# Source\n{topic.get('source', 'unknown')}{url_part}"


def generate_script(topic):
    if topic["type"] == "concept":
        prompt = (
            f"You are helping me prepare a short video I will film myself, teaching a concept to "
            f"people learning about AI. Today's concept, spotted via {topic.get('source', 'a source')}: "
            f"\"{topic['title']}\" — {topic['description']}. Write:\n"
            "1. A short suggested title (one line).\n"
            "2. A spoken script of roughly 60-90 seconds (about 150-220 words) explaining this "
            "concept simply, with one concrete example or analogy, in my casual first-person voice, "
            f"as if I'm talking to camera. No stage directions, just the words to say. {STYLE_CLAUSE}\n"
            "Output as markdown with headers for Title / Script."
        )
    else:
        prompt = (
            f"You are helping me prepare a short video I will film myself, covering what's currently "
            f"happening in AI. Today's chosen topic, from {topic.get('source', 'a source')}: "
            f"\"{topic['title']}\" — {topic['description']}. Write:\n"
            "1. A short suggested title (one line).\n"
            "2. A spoken script of roughly 60-90 seconds (about 150-220 words) explaining what happened "
            "and why it matters, in my casual first-person voice, as if I'm talking to camera. No stage "
            f"directions, just the words to say. {STYLE_CLAUSE}\n"
            "Output as markdown with headers for Title / Script."
        )
    return run_claude(prompt) + sources_footer(topic)


def revise_script(topic, previous_script, feedback):
    prompt = (
        f"Here is a video script I'm working on about \"{topic['title']}\":\n\n{previous_script}\n\n"
        f"I gave this feedback: \"{feedback}\"\n\n"
        "Revise the script accordingly, keeping the same markdown format (Title / Script / Source "
        f"headers). {STYLE_CLAUSE} Output ONLY the revised markdown, nothing else."
    )
    return run_claude(prompt)


def handle_topic_pick(state, message):
    numbers = [int(n) for n in NUMBER_LIST_RE.findall(message)]
    if not numbers:
        telegram_lib.send_message(
            f"Please reply with a topic number from today's list (1-{len(state['topics'])}), "
            "or several numbers like '3,5,7' to pick the first and backlog the rest."
        )
        return state

    by_number = {t["number"]: t for t in state["topics"]}
    valid_numbers = [n for n in numbers if n in by_number]
    if not valid_numbers:
        telegram_lib.send_message(
            f"None of those match today's topic numbers (1-{len(state['topics'])}). Try again."
        )
        return state

    pick_number, backlog_numbers = valid_numbers[0], valid_numbers[1:]
    topic = by_number[pick_number]

    for n in backlog_numbers:
        backlog.add(by_number[n])

    if topic.get("origin") == "backlog":
        backlog.remove(topic["title"])

    script_text = generate_script(topic)
    date = state["date"]
    script_path = SCRIPTS_DIR / f"{date}-news.md"
    script_path.write_text(script_text + "\n")

    backlog_note = f" Saved {len(backlog_numbers)} other topic(s) to your backlog." if backlog_numbers else ""
    telegram_lib.send_message(
        f"Script for \"{topic['title']}\":\n\n{script_text}\n\n"
        f"Reply 'approved' if this is good, or send feedback to revise it.{backlog_note}"
    )

    state["status"] = "awaiting_review"
    state["current_topic"] = topic
    state["current_script"] = script_text
    state["script_path"] = str(script_path)
    state["revision_count"] = 0
    state["updated_at"] = datetime.datetime.now().isoformat()
    return state


def handle_review(state, message):
    if APPROVAL_RE.match(message):
        telegram_lib.send_message(f"Great — script finalized at {state['script_path']}. Go film it!")
        state["status"] = "done"
        return state

    topic = state["current_topic"]
    revised = revise_script(topic, state["current_script"], message)
    Path(state["script_path"]).write_text(revised + "\n")

    telegram_lib.send_message(
        f"Updated script:\n\n{revised}\n\nReply 'approved' if this is good, or send more feedback."
    )
    state["current_script"] = revised
    state["revision_count"] = state.get("revision_count", 0) + 1
    state["updated_at"] = datetime.datetime.now().isoformat()
    return state


STALE_AFTER = datetime.timedelta(hours=20)


def is_fresh(state):
    """A state older than STALE_AFTER stops being eligible to receive replies —
    an abandoned digest/thread from a day ago shouldn't hijack routing just
    because it's technically still 'awaiting'. Doesn't touch the state file;
    a later reply to it just falls through to the "nothing active" message."""
    updated_at = state.get("updated_at")
    if not updated_at:
        return True
    age = datetime.datetime.now() - datetime.datetime.fromisoformat(updated_at)
    return age < STALE_AFTER


def news_is_awaiting(state):
    return (
        bool(state)
        and state.get("status") in ("awaiting_topic_pick", "awaiting_review")
        and is_fresh(state)
    )


def main():
    """Single shared poller for every Telegram-mediated flow in this whole
    system: the news-pipeline digest/script review (this file), the daily
    tweet thread review (learning-tweet/thread_review.py), and the NYC
    events digest (nyc-events/nyc_events_review.py). All share one
    getUpdates offset so they don't race each other consuming the same
    bot's messages — each incoming message is routed to whichever flow is
    awaiting a reply, and if more than one is, to whichever was updated
    most recently.

    Offset is confirmed one message at a time, only after that message is
    fully handled — never speculatively in advance. A message that fails
    mid-processing (a network blip, a crashed subprocess, anything) is left
    unconfirmed and retried on the next poll instead of being silently lost."""
    try:
        messages = telegram_lib.get_new_messages(OFFSET_FILE)
    except RuntimeError:
        # Telegram not configured yet — nothing to do until SETUP.md is followed.
        return
    except Exception as e:
        # Network hiccup etc. mid-fetch — nothing was confirmed, next poll retries.
        print(f"get_new_messages failed, will retry next poll: {e}", file=sys.stderr)
        return

    if not messages:
        return

    news_state = load_state()
    thread_state = thread_review.load_state()
    nyc_state = nyc_events_review.load_digest_state()

    for update_id, message in messages:
        try:
            candidates = [
                ("news", news_is_awaiting(news_state), news_state),
                ("thread", thread_review.is_awaiting(thread_state), thread_state),
                ("nyc", nyc_events_review.is_awaiting(nyc_state), nyc_state),
            ]
            active = [(name, state) for name, is_active, state in candidates if is_active]
            target = max(active, key=lambda pair: pair[1]["updated_at"])[0] if active else None

            if target is not None:
                telegram_lib.send_message("Got it, working on it...")

            if target == "news":
                if news_state["status"] == "awaiting_topic_pick":
                    news_state = handle_topic_pick(news_state, message)
                else:
                    news_state = handle_review(news_state, message)
                save_state(news_state)
            elif target == "thread":
                thread_state = thread_review.handle_reply(thread_state, message)
                thread_review.save_state(thread_state)
            elif target == "nyc":
                nyc_state = nyc_events_review.handle_reply(nyc_state, message)
                nyc_events_review.save_state(nyc_state)
            else:
                telegram_lib.send_message(
                    "Nothing awaiting your reply right now — check back after the next digest or thread."
                )
        except Exception as e:
            print(f"Failed to process update {update_id}, will retry next poll: {e}", file=sys.stderr)
            break

        telegram_lib.write_offset(OFFSET_FILE, update_id)


if __name__ == "__main__":
    main()

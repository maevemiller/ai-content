#!/usr/bin/env python3
"""Pop the next queued concept from concepts.md, mark it covered, print it to stdout."""
import datetime
import sys
from pathlib import Path

CONCEPTS_FILE = Path(__file__).parent / "concepts.md"


def main():
    text = CONCEPTS_FILE.read_text()
    lines = text.splitlines()

    queued_start = queued_end = covered_start = None
    for i, line in enumerate(lines):
        if line.strip() == "## Queued":
            queued_start = i
        elif line.strip() == "## Covered" and queued_start is not None and covered_start is None:
            covered_start = i
        elif queued_start is not None and queued_end is None and line.strip().startswith("## ") and i > queued_start:
            queued_end = i

    if queued_start is None or covered_start is None:
        print("concepts.md is missing ## Queued or ## Covered sections", file=sys.stderr)
        sys.exit(1)
    if queued_end is None:
        queued_end = covered_start

    queued_lines = lines[queued_start + 1 : queued_end]
    topic_index = None
    for i, line in enumerate(queued_lines):
        if line.strip().startswith("- "):
            topic_index = i
            break

    if topic_index is None:
        print("No queued concepts left in concepts.md", file=sys.stderr)
        sys.exit(1)

    topic_line = queued_lines.pop(topic_index)
    topic = topic_line.strip()[2:].strip()

    new_lines = lines[: queued_start + 1] + queued_lines + lines[queued_end:covered_start]
    today = datetime.date.today().strftime("%Y-%m-%d")
    covered_entry = f"- {topic} (covered {today})"

    remainder = lines[covered_start:]
    insert_at = 1
    while insert_at < len(remainder) and remainder[insert_at].strip() == "":
        insert_at += 1
    while insert_at < len(remainder) and remainder[insert_at].strip().startswith("<!--"):
        insert_at += 1
    remainder = remainder[:insert_at] + [covered_entry] + remainder[insert_at:]

    new_lines = new_lines + remainder
    CONCEPTS_FILE.write_text("\n".join(new_lines) + "\n")

    print(topic)


if __name__ == "__main__":
    main()

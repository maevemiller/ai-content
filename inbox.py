"""Read-and-clear helper for twitter_inbox.md — the free manual drop-in for
tweets/threads you want folded into the digest without paying for API access.
"""
import datetime
import re
from pathlib import Path

DIR = Path(__file__).parent
INBOX_FILE = DIR / "twitter_inbox.md"
ARCHIVE_FILE = DIR / "twitter_inbox_archive.md"
TEMPLATE = (
    "<!--\n"
    "Paste interesting tweets/threads here as you come across them on Twitter/X —\n"
    "just the link, or link + why it's interesting. Anything in this file gets\n"
    "folded into the next morning's digest, then archived automatically (see\n"
    "twitter_inbox_archive.md) and this file is cleared back to empty.\n"
    "-->\n"
)


def read_and_archive():
    """Return today's inbox content (or "" if empty/only the template comment),
    then archive it and reset the inbox file."""
    if not INBOX_FILE.exists():
        INBOX_FILE.write_text(TEMPLATE)
        return ""

    raw = INBOX_FILE.read_text()
    without_comments = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    content = without_comments.strip()

    if not content:
        return ""

    date = datetime.date.today().strftime("%Y-%m-%d")
    with ARCHIVE_FILE.open("a") as f:
        f.write(f"\n## {date}\n{content}\n")

    INBOX_FILE.write_text(TEMPLATE)
    return content


def main():
    content = read_and_archive()
    if content:
        print("## Twitter/X (manual drop-in)")
        print(content)


if __name__ == "__main__":
    main()

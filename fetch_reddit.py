#!/usr/bin/env python3
"""Fetch today's top posts from a curated list of AI subreddits via Reddit's OAuth API.

Reddit now blocks unauthenticated requests to its public .json endpoints
(403 challenge page, even with a descriptive User-Agent) — this changed at
some point after the old "no auth needed for light use" advice was common.
A free "script" app (personal use script, client_credentials grant) still
works with no cost. See SETUP.md for the 5-minute one-time setup.

If no credentials are configured yet, this prints nothing so the rest of
the pipeline (Hacker News) still works standalone.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SUBREDDITS = ["artificial", "MachineLearning", "LocalLLaMA", "OpenAI", "singularity", "ClaudeAI"]
POSTS_PER_SUB = 8
USER_AGENT = "macos:daily-ai-content-digest:v1.0 (personal, single-user, once-daily)"
KEYCHAIN_SERVICE = "ai-content-reddit"


def get_secret(account):
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_access_token(client_id, client_secret):
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=data,
        method="POST",
        headers={"User-Agent": USER_AGENT},
    )
    auth = f"{client_id}:{client_secret}"
    import base64

    req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp).get("access_token")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def fetch_subreddit(name, token):
    url = f"https://oauth.reddit.com/r/{name}/top?limit={POSTS_PER_SUB}&t=day"
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        title = p.get("title", "").strip()
        if not title:
            continue
        posts.append(
            {
                "subreddit": name,
                "title": title,
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "selftext": (p.get("selftext") or "")[:300],
            }
        )
    return posts


def main():
    client_id = get_secret("client_id")
    client_secret = get_secret("client_secret")
    if not client_id or not client_secret:
        print(
            "(Reddit not configured yet — see SETUP.md. Skipping Reddit source.)",
            file=sys.stderr,
        )
        return

    token = get_access_token(client_id, client_secret)
    if not token:
        print("(Reddit auth failed — check credentials. Skipping Reddit source.)", file=sys.stderr)
        return

    sections = []
    for sub in SUBREDDITS:
        posts = fetch_subreddit(sub, token)
        if not posts:
            continue
        lines = [f"## r/{sub} (top today)"]
        for p in sorted(posts, key=lambda x: x["score"], reverse=True):
            lines.append(f"- [{p['score']} pts, {p['num_comments']} comments] {p['title']} ({p['url']})")
            if p["selftext"]:
                lines.append(f"  {p['selftext']}")
        sections.append("\n".join(lines))

    if sections:
        print("\n\n".join(sections))


if __name__ == "__main__":
    main()

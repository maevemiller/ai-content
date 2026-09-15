#!/usr/bin/env python3
"""Fetch recent AI-related tweets via the X API v2 recent-search endpoint.

Requires a paid API tier (Basic or above) for read/search access — this is
a real recurring cost, not a free-tier feature. Gracefully prints nothing if
no bearer token is configured, so the rest of the pipeline works without it;
see SETUP.md for signup + configuration steps.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

KEYCHAIN_SERVICE = "ai-content-twitter"
QUERIES = [
    "(AI agent OR LLM OR \"agentic\") (launch OR announces OR released) -is:retweet lang:en",
    "(Claude OR GPT OR Gemini OR \"open source model\") -is:retweet lang:en",
]
MAX_RESULTS_PER_QUERY = 15


def get_secret(account):
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def search(query, bearer_token):
    params = {
        "query": query,
        "max_results": MAX_RESULTS_PER_QUERY,
        "tweet.fields": "public_metrics,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    url = f"https://api.twitter.com/2/tweets/search/recent?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {bearer_token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def main():
    bearer_token = get_secret("bearer_token")
    if not bearer_token:
        print("(X/Twitter API not configured — see SETUP.md. Skipping.)", file=sys.stderr)
        return

    lines = ["## X/Twitter (recent)"]
    found = False

    for query in QUERIES:
        data = search(query, bearer_token)
        if not data or "data" not in data:
            continue
        users = {u["id"]: u.get("username", "?") for u in data.get("includes", {}).get("users", [])}
        for tweet in data["data"]:
            text = tweet.get("text", "").replace("\n", " ").strip()
            if not text:
                continue
            username = users.get(tweet.get("author_id"), "?")
            metrics = tweet.get("public_metrics", {})
            likes = metrics.get("like_count", 0)
            tweet_url = f"https://x.com/{username}/status/{tweet['id']}"
            lines.append(f"- [@{username}, {likes} likes] {text} ({tweet_url})")
            found = True

    if found:
        print("\n".join(lines))


if __name__ == "__main__":
    main()

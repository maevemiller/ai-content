#!/usr/bin/env python3
"""Fetch recent AI-related papers from arXiv's public API (no auth needed)."""
import datetime
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.MA"]
MAX_RESULTS = 15
LOOKBACK_DAYS = 5  # arXiv has a multi-day submission-to-listing lag, longer over weekends
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch():
    query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": MAX_RESULTS,
    }
    url = f"http://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            xml_data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return []

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=LOOKBACK_DAYS)
    papers = []
    for entry in root.findall("atom:entry", ATOM_NS):
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        try:
            pub_dt = datetime.datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc
            )
        except ValueError:
            pub_dt = None
        if pub_dt and pub_dt < cutoff:
            continue

        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip().replace("\n", " ")
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip().replace("\n", " ")
        link = ""
        for link_el in entry.findall("atom:link", ATOM_NS):
            if link_el.get("rel") == "alternate" or link_el.get("type") == "text/html":
                link = link_el.get("href", "")
                break
        if not title:
            continue
        papers.append({"title": title, "summary": summary[:300], "url": link})

    return papers


def main():
    papers = fetch()
    if not papers:
        return
    lines = ["## arXiv (recent AI/ML papers)"]
    for p in papers:
        lines.append(f"- {p['title']} ({p['url']})")
        if p["summary"]:
            lines.append(f"  {p['summary']}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

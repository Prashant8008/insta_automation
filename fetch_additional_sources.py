"""
fetch_additional_sources.py

Expands Phase 1 scraping beyond IDRW + PIB to cover defence, geopolitics,
and SSB-specific sources. Merges everything into the SAME schema your
pipeline already uses: {source, title, description, pubDate, url}
so downstream scripts (extract_verified_facts.py, generate_instagram_posts.py)
need zero changes.

Two source types are handled differently:
  1. RSS sources  -> parsed with feedparser (fast, structured, low risk)
  2. No-RSS sources -> checked against robots.txt BEFORE any request,
     then scraped with a generic (best-effort) HTML parser you should
     customize per-site if the generic pass doesn't extract cleanly.

Run this alongside (or instead of) fetch_ai_news_rss.py in Phase 1.
It APPENDS to ai_news_data.json rather than overwriting, so run your
existing fetch_ai_news_rss.py first, then this script second.

Install deps:
    pip install feedparser requests beautifulsoup4 --break-system-packages
"""

import json
import os
import time
import feedparser
import requests
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

OUTPUT_PATH = "ai_news_data.json"
REQUEST_DELAY_SECONDS = 3          # politeness delay between HTTP requests
MAX_ITEMS_PER_SOURCE = 8
USER_AGENT = "SSBContentBot/1.0 (+contact: your-email@example.com)"

HEADERS = {"User-Agent": USER_AGENT}

# ---------------------------------------------------------------------------
# RSS sources — safest, structured, preferred wherever available
# ---------------------------------------------------------------------------
RSS_SOURCES = [
    {"name": "IDRW Defence", "url": "https://idrw.org/feed/"},
    {"name": "Indian Defence Review", "url": "https://indiandefencereview.com/feed/"},
    {"name": "Defence.in", "url": "https://defence.in/feed/"},
    {"name": "Indian Defence News", "url": "https://www.indiandefensenews.in/feeds/posts/default"},
    {"name": "StratNews Global", "url": "https://stratnewsglobal.com/feed/"},
    {"name": "The Diplomat - South Asia", "url": "https://thediplomat.com/regions/south-asia/feed/"},
    {"name": "ORF", "url": "https://www.orfonline.org/feed/"},
    {"name": "IADN", "url": "https://iadnews.in/feed/"},
    {"name": "Gateway House", "url": "https://www.gatewayhouse.in/feed/"},
    {"name": "PRS Legislative Research", "url": "https://prsindia.org/rss.xml"},
    {"name": "SSBCrack", "url": "https://www.ssbcrack.com/feed/"},
    {"name": "PIB Defence", "url": "https://www.pib.gov.in/RssMain.aspx?ModId=6&Reg=3&Lang=1"},
]

# ---------------------------------------------------------------------------
# No-RSS sources — robots.txt is checked before every fetch.
# 'list_page' = a page listing multiple articles (generic scrape attempt).
# These are lower priority / lower frequency by design (checked once, not looped).
# ---------------------------------------------------------------------------
NO_RSS_SOURCES = [
    {"name": "Ministry of Defence", "url": "https://mod.gov.in/press-release"},
    {"name": "MEA Press Releases", "url": "https://mea.gov.in/press-releases.htm"},
    {"name": "GKToday Current Affairs", "url": "https://www.gktoday.in/current-affairs/"},
]


def is_allowed_by_robots(url: str) -> bool:
    """Checks robots.txt for the given URL before any scrape attempt."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception as e:
        print(f"[fetch_additional_sources] Could not read {robots_url} ({e}) — skipping this source to be safe.")
        return False
    return rp.can_fetch(USER_AGENT, url)


def fetch_rss_source(source: dict) -> list:
    """Parses one RSS feed into the pipeline's standard article schema."""
    items = []
    try:
        feed = feedparser.parse(source["url"], agent=USER_AGENT)
    except Exception as e:
        print(f"[fetch_additional_sources] Failed to parse {source['name']}: {e}")
        return items

    if feed.bozo and not feed.entries:
        print(f"[fetch_additional_sources] {source['name']} feed looked malformed and had no entries — skipping.")
        return items

    for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
        description = entry.get("summary", entry.get("description", ""))
        # Strip any HTML tags feedparser left in the summary
        description = BeautifulSoup(description, "html.parser").get_text().strip()

        items.append({
            "source": source["name"],
            "title": entry.get("title", "").strip(),
            "description": description,
            "pubDate": entry.get("published", entry.get("updated", "")),
            "url": entry.get("link", source["url"]),
        })

    print(f"[fetch_additional_sources] {source['name']}: {len(items)} items via RSS")
    return items


def fetch_no_rss_source(source: dict) -> list:
    """
    Generic best-effort scraper for sites without RSS. This is intentionally
    conservative — it grabs <a> tags that look like article links plus their
    visible text, and does NOT try to guess a description (too fragile across
    different site structures). Treat these as headline-only leads; verify
    manually or via extract_verified_facts.py before trusting any numbers
    that come from them.

    If a site's markup is stable enough, replace this function's body with
    a site-specific BeautifulSoup selector for better description extraction.
    """
    items = []
    url = source["url"]

    if not is_allowed_by_robots(url):
        print(f"[fetch_additional_sources] robots.txt disallows scraping {source['name']} ({url}) — skipping.")
        return items

    time.sleep(REQUEST_DELAY_SECONDS)  # politeness delay

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[fetch_additional_sources] Failed to fetch {source['name']}: {e}")
        return items

    soup = BeautifulSoup(resp.text, "html.parser")
    seen_titles = set()

    # Specialized scraper for GKToday Current Affairs
    if "gktoday.in" in url:
        posts = soup.find_all(class_="home-post-item")
        for post in posts[:MAX_ITEMS_PER_SOURCE]:
            h3 = post.find("h3")
            if not h3:
                continue
            a = h3.find("a")
            if not a:
                continue
            title = a.get_text().strip()
            link = a.get("href", "")
            
            if title in seen_titles:
                continue
            seen_titles.add(title)
            
            post_data_div = post.find(class_="post-data")
            desc = ""
            date_str = ""
            if post_data_div:
                meta = post_data_div.find(class_="home-post-data-meta")
                if meta:
                    date_str = meta.get_text().strip()
                    date_str = " ".join(date_str.split())
                
                h3_text = h3.get_text()
                meta_text = meta.get_text() if meta else ""
                full_text = post_data_div.get_text()
                
                desc = full_text.replace(h3_text, "").replace(meta_text, "").strip()
                desc = " ".join(desc.split())
                
            items.append({
                "source": source["name"],
                "title": title,
                "description": desc,
                "pubDate": date_str,
                "url": link,
            })
        print(f"[fetch_additional_sources] {source['name']}: {len(items)} items via custom HTML parser")
        return items

    for a_tag in soup.find_all("a"):
        text = a_tag.get_text().strip()
        href = a_tag.get("href", "")
        # Heuristic: treat reasonably long link text as a headline candidate
        if len(text) < 25 or text in seen_titles:
            continue
        seen_titles.add(text)

        full_url = urljoin(url, href)
        items.append({
            "source": source["name"],
            "title": text,
            "description": "",  # intentionally empty — headline-only lead
            "pubDate": "",
            "url": full_url,
        })
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break

    print(f"[fetch_additional_sources] {source['name']}: {len(items)} headline leads via HTML scrape "
          f"(descriptions empty — verify before using as fact source)")
    return items


def merge_into_existing(new_items: list):
    existing = []
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_urls = {item.get("url") for item in existing}
    added = 0
    for item in new_items:
        if item["url"] not in existing_urls:
            existing.append(item)
            existing_urls.add(item["url"])
            added += 1

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"[fetch_additional_sources] Added {added} new items -> {OUTPUT_PATH} "
          f"(total now {len(existing)})")


def main():
    all_new_items = []

    for source in RSS_SOURCES:
        all_new_items.extend(fetch_rss_source(source))
        time.sleep(REQUEST_DELAY_SECONDS)

    for source in NO_RSS_SOURCES:
        all_new_items.extend(fetch_no_rss_source(source))

    merge_into_existing(all_new_items)


if __name__ == "__main__":
    main()

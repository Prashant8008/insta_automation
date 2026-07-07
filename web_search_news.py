"""
web_search_news.py
Search the web for a topic and return structured article data for card generation.
"""
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(ROOT, "web_search_result.json")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SSBConnectBot/1.0)",
}


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "meta":
            prop = (attr.get("property") or attr.get("name") or "").lower()
            if prop in ("og:title", "twitter:title") and not self.title:
                self.title = attr.get("content", "").strip()
            if prop in ("og:description", "description", "twitter:description"):
                self.description = attr.get("content", "").strip()

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title += data.strip()


def _domain(url):
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "Web"


def _enrich_from_url(url: str) -> dict:
    out = {"url": url, "title": "", "description": "", "source": _domain(url), "pubDate": ""}
    if not url.startswith("http"):
        return out
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as res:
            html = res.read(200_000).decode("utf-8", errors="ignore")
        parser = MetaParser()
        parser.feed(html)
        out["title"] = parser.title[:300]
        out["description"] = parser.description[:1200]
        if not out["description"]:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            out["description"] = text[:800]
    except Exception as e:
        print(f"[web_search] page fetch failed {url}: {e}")
    return out


def search_google_news_rss(query: str, max_results: int = 8) -> list:
    """Google News RSS — no API key required."""
    results = []
    q = urllib.parse.quote(f"{query} India defence")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    print(f"[web_search] Google News RSS: {query}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=20) as res:
            xml_text = res.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item")[:max_results]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")
            title = title_el.text if title_el is not None and title_el.text else ""
            link = link_el.text if link_el is not None and link_el.text else ""
            desc_raw = desc_el.text if desc_el is not None and desc_el.text else ""
            desc = re.sub(r"<[^>]+>", "", desc_raw).strip()
            pub = pub_el.text if pub_el is not None and pub_el.text else ""
            if title:
                results.append({
                    "title": title,
                    "description": desc,
                    "url": link,
                    "source": _domain(link) if link else "Google News",
                    "pubDate": pub,
                })
    except Exception as e:
        print(f"[web_search] Google News RSS failed: {e}")
    return results


def search_duckduckgo(query: str, max_results: int = 5) -> list:
    results = []
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return results
    search_query = f"{query} India defence news"
    try:
        with DDGS() as ddgs:
            for item in ddgs.news(search_query, max_results=max_results):
                url = item.get("url", "")
                if not url:
                    continue
                results.append({
                    "title": item.get("title", ""),
                    "description": item.get("body", item.get("excerpt", "")),
                    "url": url,
                    "source": item.get("source") or _domain(url),
                    "pubDate": item.get("date", ""),
                })
    except Exception as e:
        print(f"[web_search] DuckDuckGo failed: {e}")
    return results


def search_local_feed(query: str) -> list:
    path = os.path.join(ROOT, "ai_news_data.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    words = set(re.findall(r"[a-z0-9]{4,}", query.lower()))
    scored = []
    for item in data:
        blob = f"{item.get('title', '')} {item.get('description', '')}".lower()
        score = sum(1 for w in words if w in blob)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:5]]


def search_web(query: str, max_results: int = 5) -> list:
    results = []
    seen = set()

    for batch in (
        search_google_news_rss(query, max_results),
        search_local_feed(query),
    ):
        for item in batch:
            url = item.get("url", "")
            key = url or item.get("title", "")
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
        if len(results) >= 2:
            break

    print(f"[web_search] Total unique results: {len(results)}")
    return results


def pick_best_article(query: str, results: list) -> dict | None:
    if not results:
        return None
    words = set(re.findall(r"[a-z0-9]{4,}", query.lower()))
    best, best_score = results[0], 0
    for item in results:
        blob = f"{item.get('title', '')} {item.get('description', '')}".lower()
        score = sum(1 for w in words if w in blob)
        if item.get("description"):
            score += 1
        if score > best_score:
            best_score = score
            best = item
    return best


def research_topic(query: str) -> dict:
    results = search_web(query)
    article = pick_best_article(query, results)

    if article and article.get("url") and not article.get("url", "").startswith(
        "https://news.google.com"
    ):
        try:
            enriched = _enrich_from_url(article["url"])
            if enriched.get("title"):
                article["title"] = enriched["title"]
            if enriched.get("description") and len(enriched["description"]) > len(
                article.get("description", "")
            ):
                article["description"] = enriched["description"]
        except Exception as e:
            print(f"[web_search] enrich skipped: {e}")

    if article and not article.get("pubDate"):
        article["pubDate"] = datetime.now().strftime("%B %d, %Y")

    payload = {
        "query": query,
        "searched_at": datetime.now().isoformat(),
        "article": article,
        "all_results": results[:5],
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    if article:
        print(f"[web_search] Best match: {article.get('title', '')[:80]}")
    else:
        print("[web_search] No article found")
    return payload


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "DRDO missile test"
    data = research_topic(q)
    print(json.dumps(data.get("article"), indent=2, ensure_ascii=False))

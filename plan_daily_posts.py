"""
plan_daily_posts.py
Plans daily Instagram output: 3 latest news cards + 1 SSB prep card.
"""
import json
import os
import re
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NEWS_PATH = "ai_news_data.json"
NEWS_LOG_PATH = "news-card-log.json"
SSB_LOG_PATH = "ssb-topic-log.json"
OUTPUT_PATH = "daily_post_plan.json"

MIN_NEWS_CARDS = 3
SSB_TOPICS = ["TAT", "WAT", "SRT", "PPDT", "OIR", "GTO"]

DEFENCE_KEYWORDS = [
    "defence", "defense", "army", "navy", "air force", "military", "ssb",
    "missile", "drone", "exercise", "agniveer", "mod", "indigenous",
    "geopolit", "border", "iaf", "ins ", "drdo", "procurement", "current affairs",
]

# Tier 1 sources get priority selection for news cards
TIER_1_SOURCES = {
    "SSBCrack",
    "SSBCrack News",
    "ThePrint Defence",
    "PIB Defence",
    "IDRW Defence",
}


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_title(title):
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def _parse_date(pub_date):
    if not pub_date:
        return datetime.min
    raw = pub_date.strip()[:31]
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d",
        "%d %b %Y",
        "%B %d, %Y",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return datetime.min


def _is_defence_relevant(item):
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    return any(kw in text for kw in DEFENCE_KEYWORDS)


def _are_similar(title1, title2):
    # Split into words of length > 3
    words1 = {w for w in re.findall(r"\b\w{4,}\b", (title1 or "").lower())}
    words2 = {w for w in re.findall(r"\b\w{4,}\b", (title2 or "").lower())}
    overlap = words1.intersection(words2)
    # If they share 3 or more significant words, they are similar
    return len(overlap) >= 3


def _pick_top_news(news_data, news_log, count=MIN_NEWS_CARDS, strict_new_only=False):
    recent_topics = set()
    recent_urls = set()
    for e in news_log[-40:]:
        if e.get("topic"):
            recent_topics.add(_normalize_title(e["topic"]))
        if e.get("headline"):
            recent_topics.add(_normalize_title(e["headline"]))
        if e.get("url"):
            recent_urls.add(e["url"].strip().lower())

    candidates = []
    seen_titles = set()
    for item in news_data:
        title = item.get("title", "").strip()
        url = (item.get("url") or "").strip().lower()
        norm = _normalize_title(title)
        if not title or norm in seen_titles:
            continue
        seen_titles.add(norm)
        
        # Check direct URL match
        if url and url in recent_urls:
            continue

        # Check direct topic/headline match
        if norm in recent_topics:
            continue
            
        # Check similarity match against logged topics and headlines
        is_recent_similar = False
        for entry in news_log[-40:]:
            logged_topic = entry.get("topic", "").strip()
            logged_headline = entry.get("headline", "").strip()
            if _are_similar(title, logged_topic) or _are_similar(title, logged_headline):
                is_recent_similar = True
                break
        if is_recent_similar:
            continue

        score = 0
        source = item.get("source", "")
        # Tier 1 sources get a large bonus — always preferred
        if source in TIER_1_SOURCES or item.get("priority", 2) == 1:
            score += 20
        if _is_defence_relevant(item):
            score += 10
        if item.get("description"):
            score += 3
        if item.get("url"):
            score += 1
        candidates.append((score, _parse_date(item.get("pubDate", "")), item))

    # Sort by score DESC, then by date DESC
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    selected = []
    for _, _, item in candidates:
        title = item.get("title", "").strip()
        
        # Check similarity against already selected items in this batch
        is_duplicate = False
        for sel in selected:
            if _are_similar(title, sel["title"]):
                is_duplicate = True
                break
        if is_duplicate:
            continue

        selected.append({
            "title": title,
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": item.get("source", "News"),
            "pubDate": item.get("pubDate", ""),
        })
        if len(selected) >= count:
            break

    # If strict_new_only is True (e.g. evening check), never fallback to old/already logged news
    if strict_new_only:
        return selected

    # If not enough fresh defence news, fill with most recent regardless of log/similarity
    if len(selected) < count:
        for item in news_data:
            title = item.get("title", "").strip()
            norm = _normalize_title(title)
            
            # Check direct match
            if not title or norm in [ _normalize_title(s["title"]) for s in selected ]:
                continue
                
            # Check similarity against current selection
            is_duplicate = False
            for sel in selected:
                if _are_similar(title, sel["title"]):
                    is_duplicate = True
                    break
            if is_duplicate:
                continue

            selected.append({
                "title": title,
                "description": item.get("description", ""),
                "url": item.get("url", ""),
                "source": item.get("source", "News"),
                "pubDate": item.get("pubDate", ""),
            })
            if len(selected) >= count:
                break

    return selected


def _pick_ssb_topic(ssb_log):
    recent = [e.get("topic") for e in ssb_log[-4:] if e.get("topic")]
    for topic in SSB_TOPICS:
        if topic not in recent:
            return topic
    return SSB_TOPICS[len(ssb_log) % len(SSB_TOPICS)]


def build_plan(require_new=False):
    import sys
    news_data = _load_json(NEWS_PATH, [])
    news_log = _load_json(NEWS_LOG_PATH, [])
    ssb_log = _load_json(SSB_LOG_PATH, [])

    news_assignments = _pick_top_news(news_data, news_log, MIN_NEWS_CARDS, strict_new_only=require_new)
    
    if require_new and len(news_assignments) == 0:
        empty_plan = {
            "num_posts": 0,
            "post_types": [],
            "news_assignments": [],
            "has_new_content": False,
            "reasoning": "No fresh updates found since last run."
        }
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(empty_plan, f, indent=2)
        print("[plan_daily_posts] ℹ️ No fresh defence/current affairs news found since last run.")
        sys.exit(2)

    ssb_topic = _pick_ssb_topic(ssb_log)

    post_types = ["NewsCard"] * len(news_assignments) + ["SSBCard"]
    plan = {
        "num_posts": len(post_types),
        "post_types": post_types,
        "news_assignments": news_assignments,
        "ssb_topic": ssb_topic,
        "has_new_content": True,
        "reasoning": (
            f"Selected {len(news_assignments)} GKToday news cards from {len(news_data)} feed items."
        ),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    print(f"[plan_daily_posts] {plan['reasoning']}")
    print(f"[plan_daily_posts] Post types: {post_types}")
    return plan


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-new", action="store_true", help="Only plan if fresh/unposted news is found")
    args = parser.parse_args()
    build_plan(require_new=args.require_new)

"""
plan_daily_posts.py
Plans daily Instagram output: 3 latest news cards + 1 SSB prep card.
"""
import json
import os
import re
from datetime import datetime

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


def _pick_top_news(news_data, news_log, count=MIN_NEWS_CARDS):
    recent_topics = {_normalize_title(e.get("topic", "")) for e in news_log[-21:]}

    candidates = []
    seen_titles = set()
    for item in news_data:
        # Only select news from GKToday website
        if item.get("source") != "GKToday Current Affairs":
            continue
        title = item.get("title", "").strip()
        norm = _normalize_title(title)
        if not title or norm in seen_titles:
            continue
        seen_titles.add(norm)
        if norm in recent_topics:
            continue
        score = 0
        if _is_defence_relevant(item):
            score += 10
        if item.get("description"):
            score += 3
        if item.get("url"):
            score += 1
        candidates.append((score, _parse_date(item.get("pubDate", "")), item))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    defence_first = [c for c in candidates if c[0] >= 10]
    general = [c for c in candidates if c[0] < 10]
    ordered = defence_first + general

    selected = []
    used_norm = set()
    for _, _, item in ordered:
        norm = _normalize_title(item.get("title", ""))
        if norm in used_norm:
            continue
        used_norm.add(norm)
        selected.append({
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": item.get("source", "News"),
            "pubDate": item.get("pubDate", ""),
        })
        if len(selected) >= count:
            break

    # If not enough fresh defence news, fill with most recent regardless of log
    if len(selected) < count:
        for item in news_data:
            title = item.get("title", "").strip()
            norm = _normalize_title(title)
            if not title or norm in used_norm:
                continue
            used_norm.add(norm)
            selected.append({
                "title": item.get("title", ""),
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


def build_plan():
    news_data = _load_json(NEWS_PATH, [])
    news_log = _load_json(NEWS_LOG_PATH, [])
    ssb_log = _load_json(SSB_LOG_PATH, [])

    news_assignments = _pick_top_news(news_data, news_log, MIN_NEWS_CARDS)
    ssb_topic = _pick_ssb_topic(ssb_log)

    post_types = ["NewsCard"] * len(news_assignments) + ["SSBCard"]
    plan = {
        "num_posts": len(post_types),
        "post_types": post_types,
        "news_assignments": news_assignments,
        "ssb_topic": ssb_topic,
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
    build_plan()

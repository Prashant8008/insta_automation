"""
extract_verified_facts.py
Phase 2.5a — Fact extraction. Builds a pool of verified numeric facts from
scraped news (ai_news_data.json) plus optional manual entries (verified_data.json).
Gemini will only be allowed to reference numbers from this pool — it never
invents a figure, and never decides whether a number counts as sourced.
"""
import json, re, os
from datetime import datetime

AI_NEWS_PATH = "ai_news_data.json"
VERIFIED_MANUAL_PATH = "verified_data.json"
OUTPUT_PATH = "verified_facts_today.json"

NUMBER_PATTERN = re.compile(
    r"(?<![\d./])(\d{1,4}(?:\.\d+)?)(?!\d)\s*(billion|million|crore|lakh|%)?",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")

def _split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

def _tag_topics(text):
    text_l = text.lower()
    tag_keywords = {
        "helicopter": ["helicopter", "seahawk", "mh-60r", "dhruv", "chetak", "sea king"],
        "navy": ["navy", "naval", "inas", "ins "],
        "army": ["army", "infantry", "regiment"],
        "air_force": ["air force", "iaf", "fighter", "jet"],
        "missile": ["missile", "brahmos", "akash", "divyastra"],
        "procurement": ["contract", "deal", "order", "fms", "crore", "billion"],
    }
    return [tag for tag, kws in tag_keywords.items() if any(k in text_l for k in kws)]

def extract_from_scraped_news(ai_news_data):
    facts = []
    for article in ai_news_data:
        full_text = f"{article.get('title', '')}. {article.get('description', '')}"
        for sentence in _split_sentences(full_text):
            for match in NUMBER_PATTERN.finditer(sentence):
                raw_num, scale_word = match.group(1), match.group(2)
                if YEAR_PATTERN.match(raw_num) and not scale_word:
                    continue
                try:
                    value = float(raw_num) if "." in raw_num else int(raw_num)
                except ValueError:
                    continue
                start = match.end()
                unit_context = sentence[start:start + 40].strip()
                facts.append({
                    "value": value,
                    "unit_context": unit_context,
                    "source_sentence": sentence,
                    "source": article.get("source", "unknown"),
                    "url": article.get("url", ""),
                    "date": article.get("pubDate", ""),
                    "origin": "scraped",
                    "topic_tags": _tag_topics(full_text),
                })
    return facts

def load_manual_facts():
    if not os.path.exists(VERIFIED_MANUAL_PATH):
        return []
    with open(VERIFIED_MANUAL_PATH, "r", encoding="utf-8") as f:
        manual_entries = json.load(f)
    facts = []
    for entry in manual_entries:
        facts.append({
            "value": entry["value"],
            "unit_context": entry.get("unit_context", ""),
            "source_sentence": entry.get("source_sentence", entry.get("note", "")),
            "source": entry.get("source", "manual"),
            "url": entry.get("url", ""),
            "date": entry.get("date", datetime.now().strftime("%Y-%m-%d")),
            "origin": "manual",
            "topic_tags": entry.get("topic_tags", _tag_topics(entry.get("unit_context", ""))),
        })
    return facts

def build_verified_facts_pool():
    ai_news_data = []
    if os.path.exists(AI_NEWS_PATH):
        with open(AI_NEWS_PATH, "r", encoding="utf-8") as f:
            ai_news_data = json.load(f)
    scraped_facts = extract_from_scraped_news(ai_news_data)
    manual_facts = load_manual_facts()
    all_facts = scraped_facts + manual_facts
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_facts, f, indent=2)
    print(f"[extract_verified_facts] {len(scraped_facts)} scraped + {len(manual_facts)} manual = {len(all_facts)} facts -> {OUTPUT_PATH}")
    return all_facts

if __name__ == "__main__":
    build_verified_facts_pool()

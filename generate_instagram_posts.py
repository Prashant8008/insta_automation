"""
generate_instagram_posts.py
Generates captions + card layout JSON for 3 news cards and 1 SSB prep card.
"""
import datetime
import json
import os
import re
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request

from brand_utils import sanitize_brand_text

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

gemini_key = None
env_path = "./.env"
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                gemini_key = line.strip().split("=", 1)[1]
                break
if not gemini_key:
    gemini_key = os.environ.get("GEMINI_API_KEY")
if not gemini_key:
    print("Error: GEMINI_API_KEY not found in .env or environment variables.")
    sys.exit(1)

if not os.path.exists("daily_post_plan.json"):
    print("Error: daily_post_plan.json not found. Run plan_daily_posts.py first.")
    sys.exit(1)

with open("daily_post_plan.json", "r", encoding="utf-8") as f:
    plan = json.load(f)

post_types = plan.get("post_types", [])
news_assignments = plan.get("news_assignments", [])
ssb_topic = plan.get("ssb_topic", "TAT")

banned_news_topics = []
try:
    if os.path.exists("news-card-log.json"):
        with open("news-card-log.json", encoding="utf-8") as f:
            banned_news_topics = [e.get("topic", "") for e in json.load(f)[-14:]]
except Exception as e:
    print(f"Warning loading news-card-log.json: {e}")

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.5-flash:generateContent?key={gemini_key}"
)

CAPTION_RULES = """
CAPTION RULES:
1. Third-person observer voice, inspiring and disciplined tone.
2. Short punchy sentences. Line breaks between ideas. Use emojis naturally.
3. Hook in caps. End with engagement question, then 5-8 relevant hashtags.
4. No em-dashes.
5. BRAND CTA (REQUIRED): End every caption with this exact line on its own line:
   Follow @ssb.connect for daily SSB prep & defence updates.
6. NEVER mention Founders Wing, founderswing, @founderswing, or "daily frameworks".
7. BANNED WORDS: delve, underscore, vibrant, tapestry, pivotal, showcase, foster,
   landscape, leverages, game-changer, revolutionary, groundbreaking, empower, unlock,
   journey, ecosystem, passionate, excited to share.
"""

def make_call(system_p, user_p, max_t=3000):
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_p}]}],
        "systemInstruction": {"parts": [{"text": system_p}]},
        "generationConfig": {
            "maxOutputTokens": max_t,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(1, 3):
        try:
            print(f"  Calling Gemini (attempt {attempt}/2)...")
            with urllib.request.urlopen(req, context=ctx, timeout=30) as res:
                resp = json.loads(res.read().decode("utf-8"))
            if resp.get("candidates"):
                return resp["candidates"][0]["content"]["parts"][0]["text"]
            print(f"  Unexpected response: {resp}")
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.reason}")
            if attempt < 2:
                time.sleep(attempt * 2)
        except Exception as e:
            print(f"  Error: {e}")
            if attempt < 2:
                time.sleep(2)
    return None


def extract_json_block(response):
    match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
    if match:
        return match.group(1).strip()
    start, end = response.find("{"), response.rfind("}")
    if start != -1 and end != -1:
        return response[start : end + 1].strip()
    return None


def extract_caption_text(response, caption_key):
    label_idx = response.find("VISUAL LAYOUT JSON")
    text = response[:label_idx] if label_idx != -1 else response
    if caption_key in text:
        return text.split(caption_key, 1)[1].split("=" * 20)[0].strip()
    return text.strip()


def save_card_json(num, ptype, data):
    filename = f"./{ptype.lower()}_{num}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved {filename}")


post_contents = []
news_idx = 0

for idx, ptype in enumerate(post_types):
    num = idx + 1
    print(f"\n--- Generating Post {num}/{len(post_types)} ({ptype}) ---")

    if ptype == "NewsCard":
        if news_idx >= len(news_assignments):
            print(f"Error: No news assignment for post {num}")
            sys.exit(1)
        article = news_assignments[news_idx]
        news_idx += 1
        bg = article.get("background_image", f"./assets/card-bg_{num}.svg")

        system_prompt = f"""You are SSB Connect's Instagram copywriter.
Create a NEWS CARD post grounded ONLY in the article below.
{CAPTION_RULES}
Highlight 1-3 key phrases in the headline (organisations, numbers, dates, locations).
Do NOT invent facts not present in the article."""

        user_prompt = f"""Article:
Title: {article.get('title', '')}
Description: {article.get('description', '')}
Source: {article.get('source', '')}
URL: {article.get('url', '')}
Date: {article.get('pubDate', '')}

Output format:

==================================================
{num}. NEWS CARD
==================================================
CAPTION:
[Instagram caption]

==================================================
VISUAL LAYOUT JSON
==================================================
```json
{{
  "card_type": "NewsCard",
  "badge": "NEWS",
  "headline": "[Full headline in ALL CAPS, max 20 words]",
  "highlight_phrases": ["[phrase1]", "[phrase2]"],
  "image_source": "Source: {article.get('source', 'News')} | @ssb.connect",
  "topic": "[short topic label]",
  "background_image": "{bg}"
}}
```"""

    else:  # SSBCard
        bg = plan.get("ssb_background_image", f"./assets/card-bg_{num}.svg")
        system_prompt = f"""You are SSB Connect's SSB preparation expert.
Create one practical SSB prep card about {ssb_topic}.
{CAPTION_RULES}
Give actionable, exam-room advice. Use real SSB test terminology."""

        topic_guides = {
            "TAT": "Thematic Apperception Test — how to read the picture and write a positive 8-12 line story.",
            "WAT": "Word Association Test — how to respond in 15 seconds with OLQ-aligned associations.",
            "SRT": "Situation Reaction Test — how to write practical, leader-like responses.",
            "PPDT": "Picture Perception & Discussion Test — how to observe the picture, write a story, and contribute in GD.",
            "OIR": "Officer Intelligence Rating — reasoning approach and time management.",
            "GTO": "Group Testing Officer tasks — planning, coordination, and initiative in outdoor tasks.",
        }
        guide = topic_guides.get(ssb_topic, f"Practical tips for {ssb_topic}.")

        user_prompt = f"""Topic: {ssb_topic}
Focus: {guide}

Output format:

==================================================
{num}. SSB CARD
==================================================
CAPTION:
[Instagram caption with actionable tips]

==================================================
VISUAL LAYOUT JSON
==================================================
```json
{{
  "card_type": "SSBCard",
  "topic": "{ssb_topic}",
  "header": "[Header line, e.g. HOW TO APPROACH THE PICTURE]",
  "header_highlight": "[1-3 words to highlight in yellow]",
  "headline": "[Main tip headline, max 18 words]",
  "detail": "[2-3 sentence practical advice]",
  "detail_highlights": ["[keyword1]", "[keyword2]", "[keyword3]"],
  "background_image": "{bg}"
}}
```"""

    response = make_call(system_prompt, user_prompt)
    if not response:
        print(f"Error: Gemini failed for post {num}")
        sys.exit(1)

    caption_key = "CAPTION:"
    caption_block = sanitize_brand_text(extract_caption_text(response, caption_key))
    header = f"{'=' * 50}\n{num}. {ptype.upper().replace('CARD', ' CARD')}\n{'=' * 50}\n{caption_key}\n{caption_block}"
    post_contents.append(header)

    json_str = extract_json_block(response)
    if not json_str:
        print(f"Warning: No JSON for post {num}")
        continue
    try:
        card_data = json.loads(json_str)
        if ptype == "NewsCard":
            card_data["background_image"] = article.get("background_image", card_data.get("background_image"))
            card_data["article_url"] = article.get("url", "")
        else:
            card_data["background_image"] = plan.get("ssb_background_image", card_data.get("background_image"))
        prefix = "newscard" if ptype == "NewsCard" else "ssbcard"
        save_card_json(num, prefix, card_data)
    except json.JSONDecodeError as e:
        print(f"JSON parse error post {num}: {e}")
        print(json_str[:500])

combined = "\n\n".join(post_contents)
date_compact = datetime.date.today().isoformat().replace("-", "")
with open("./instagram_posts_today.txt", "w", encoding="utf-8") as f:
    f.write(combined)
with open(f"./instagram_posts_{date_compact}.txt", "w", encoding="utf-8") as f:
    f.write(combined)
print(f"\nAll captions saved to instagram_posts_{date_compact}.txt")

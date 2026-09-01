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

MODELS = ["gemini-flash-latest", "gemini-2.5-flash"]

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
8. LOCATION (REQUIRED): Immediately below the top HOOK line, always include a location line starting with 📍, e.g. '📍 India' or specific Indian city/station (e.g. '📍 New Delhi, India', '📍 Pokhran, Rajasthan', '📍 Bengaluru, India', '📍 NDA Khadakwasla, Pune').
"""

def make_call(system_p, user_p, max_t=3000):
    if not gemini_key:
        return None
    time.sleep(2)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_p}]}],
        "systemInstruction": {"parts": [{"text": system_p}]},
        "generationConfig": {
            "maxOutputTokens": max_t,
        },
    }

    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(1, 4):
            try:
                print(f"  Calling Gemini ({model}, attempt {attempt}/3)...")
                with urllib.request.urlopen(req, context=ctx, timeout=35) as res:
                    resp = json.loads(res.read().decode("utf-8"))
                if resp.get("candidates"):
                    return resp["candidates"][0]["content"]["parts"][0]["text"]
                print(f"  Unexpected response: {resp}")
            except urllib.error.HTTPError as e:
                print(f"  HTTP {e.code} ({model}): {e.reason}")
                if e.code == 429:
                    wait_time = 5 * attempt
                    print(f"  Rate limited. Backing off for {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    break
            except Exception as e:
                print(f"  Error ({model}): {e}")
                time.sleep(3)
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


def generate_fallback_post(ptype, num, article=None, ssb_topic="TAT", bg="./assets/card-bg_1.jpg"):
    print(f"  [Fallback Engine] Generating post {num} ({ptype}) via structured template...")
    if ptype == "NewsCard" and article:
        title = article.get("title", "Defence & Security Update").strip()
        desc = article.get("description", article.get("summary", "")).strip()
        clean_title = re.sub(r"<[^>]+>", "", title).replace("\n", " ")
        clean_desc = re.sub(r"<[^>]+>", "", desc).replace("\n", " ")
        if len(clean_desc) < 30:
            clean_desc = clean_title

        headline = clean_title.upper()[:120]
        spoken = f"{clean_title}. {clean_desc[:140]}. Stay updated with SSB Connect for daily defence news!"
        caption = (
            f"🔴 DEFENCE UPDATE: {clean_title.upper()}\n"
            f"📍 India\n\n"
            f"{clean_desc[:250]}\n\n"
            f"Key takeaway: India continues to strengthen its strategic security posture.\n\n"
            f"What are your thoughts on this development?\n\n"
            f"Follow @ssb.connect for daily SSB prep & defence updates.\n\n"
            f"#IndianDefence #DefenceNews #IndianArmedForces #SSBPrep #CurrentAffairs #SSBConnect"
        )
        card_data = {
            "card_type": "NewsCard",
            "badge": "DEFENCE FLASH",
            "headline": headline,
            "spoken_script": spoken,
            "highlight_phrases": [clean_title[:30]],
            "image_source": f"Source: {article.get('source', 'News')} | @ssb.connect",
            "topic": clean_title[:40],
            "background_image": bg,
            "article_url": article.get("url", "")
        }
        return caption, card_data
    else:
        topic_info = {
            "TAT": ("THEMATIC APPERCEPTION TEST", "OBSERVE THE HERO & PLOT", "Look closely at the characters, identify the age, gender, mood, and build a logical 12-line story showing proactive action."),
            "WAT": ("WORD ASSOCIATION TEST", "WRITE NATURAL RESPONSES", "Respond within 15 seconds with brief, positive sentences reflecting officer-like qualities."),
            "SRT": ("SITUATION REACTION TEST", "PROACTIVE LEADERSHIP", "State practical, step-by-step actions resolving the crisis effectively."),
            "PPDT": ("PICTURE PERCEPTION TEST", "ACCURATE PERCEPTION & GD", "Perceive characters accurately, narrate clearly in 1 minute, and support the group in common story formulation."),
            "OIR": ("OFFICER INTELLIGENCE RATING", "SPEED & ACCURACY", "Practice non-verbal reasoning and dice problems daily to score OIR 1 in screening."),
            "GTO": ("GROUP TESTING OFFICER TASKS", "TEAMWORK & INITIATIVE", "Cooperate with the group, offer helpful ideas, and show stamina and determination.")
        }
        name, hdr, tip = topic_info.get(ssb_topic, (ssb_topic, "KEY PREPARATION TIP", f"Focus on core principles and structured practice for {ssb_topic}."))
        spoken = f"Essential SSB prep tip for {ssb_topic}. {tip}. Save this reel and follow SSB Connect for daily SSB success!"
        caption = (
            f"🎯 SSB MASTERCLASS: {name}\n"
            f"📍 SSB Centre, India\n\n"
            f"HOW TO ACE {ssb_topic}:\n"
            f"• {hdr}: {tip}\n"
            f"• Maintain calm confidence and clarity in your thought process.\n"
            f"• Demonstrate genuine Officer Like Qualities (OLQs) consistently.\n\n"
            f"Save this reel for your upcoming SSB interview!\n\n"
            f"Follow @ssb.connect for daily SSB prep & defence updates.\n\n"
            f"#SSBInterview #SSBPreparation #IndianArmy #IndianAirForce #IndianNavy #NDA #CDS #SSBConnect"
        )
        card_data = {
            "card_type": "SSBCard",
            "topic": ssb_topic,
            "badge": "SSB TIP",
            "header": hdr,
            "header_highlight": hdr.split()[0] if hdr else "KEY",
            "headline": f"Master {ssb_topic}: {tip[:80]}",
            "spoken_script": spoken,
            "detail": tip,
            "detail_highlights": [ssb_topic, "Officer", "Preparation"],
            "background_image": bg
        }
        return caption, card_data


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

        system_prompt = f"""You are SSB Connect's Instagram video and post creator.
Create a NEWS CARD and REEL post grounded ONLY in the article below.
{CAPTION_RULES}
Also generate a 'spoken_script' for a 20-second short-form Reel video:
- 0-3s Hook: Engaging, exciting statement.
- 3-15s Story: 2 core facts from the article in simple spoken English.
- 15-20s CTA: 'Follow SSB Connect for daily defence updates!'
Highlight 1-3 key phrases in the headline. Do NOT invent facts."""

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
  "badge": "DEFENCE FLASH",
  "headline": "[Full headline in ALL CAPS, max 20 words]",
  "spoken_script": "[Punchy 20-second spoken script with hook, 2 facts, and follow CTA]",
  "highlight_phrases": ["[phrase1]", "[phrase2]"],
  "image_source": "Source: {article.get('source', 'News')} | @ssb.connect",
  "topic": "[short topic label]",
  "background_image": "{bg}"
}}
```"""

    else:  # SSBCard
        bg = plan.get("ssb_background_image", f"./assets/card-bg_{num}.svg")
        system_prompt = f"""You are SSB Connect's SSB preparation expert.
Create one practical SSB prep post and short video script about {ssb_topic}.
{CAPTION_RULES}
Also generate a 'spoken_script' for a 20-second Reel video:
- 0-3s Hook: 'Stop making this common mistake in {ssb_topic}...'
- 3-15s Practical advice: 2 clear actionable tips with real SSB terms.
- 15-20s CTA: 'Save this for your SSB and follow SSB Connect for daily tips.'"""

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
  "badge": "SSB TIP",
  "header": "[Header line, e.g. HOW TO APPROACH THE PICTURE]",
  "header_highlight": "[1-3 words to highlight in yellow]",
  "headline": "[Main tip headline, max 18 words]",
  "spoken_script": "[Actionable 20-second spoken script with hook, tips, and follow CTA]",
  "detail": "[2-3 sentence practical advice]",
  "detail_highlights": ["[keyword1]", "[keyword2]", "[keyword3]"],
  "background_image": "{bg}"
}}
```"""

    response = make_call(system_prompt, user_prompt)
    if not response:
        print(f"Warning: Gemini unavailable for post {num}. Engaging fallback template...")
        caption_block, card_data = generate_fallback_post(ptype, num, article if ptype == "NewsCard" else None, ssb_topic, bg)
        header = f"{'=' * 50}\n{num}. {ptype.upper().replace('CARD', ' CARD')}\n{'=' * 50}\nCAPTION:\n{caption_block}"
        post_contents.append(header)
        prefix = "newscard" if ptype == "NewsCard" else "ssbcard"
        save_card_json(num, prefix, card_data)
        continue

    caption_key = "CAPTION:"
    caption_block = sanitize_brand_text(extract_caption_text(response, caption_key))
    header = f"{'=' * 50}\n{num}. {ptype.upper().replace('CARD', ' CARD')}\n{'=' * 50}\n{caption_key}\n{caption_block}"
    post_contents.append(header)

    json_str = extract_json_block(response)
    if not json_str:
        print(f"Warning: No JSON for post {num}. Using fallback.")
        _, card_data = generate_fallback_post(ptype, num, article if ptype == "NewsCard" else None, ssb_topic, bg)
        prefix = "newscard" if ptype == "NewsCard" else "ssbcard"
        save_card_json(num, prefix, card_data)
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
        _, card_data = generate_fallback_post(ptype, num, article if ptype == "NewsCard" else None, ssb_topic, bg)
        prefix = "newscard" if ptype == "NewsCard" else "ssbcard"
        save_card_json(num, prefix, card_data)

combined = "\n\n".join(post_contents)
date_compact = datetime.date.today().isoformat().replace("-", "")
with open("./instagram_posts_today.txt", "w", encoding="utf-8") as f:
    f.write(combined)
with open(f"./instagram_posts_{date_compact}.txt", "w", encoding="utf-8") as f:
    f.write(combined)
print(f"\nAll captions saved to instagram_posts_{date_compact}.txt")

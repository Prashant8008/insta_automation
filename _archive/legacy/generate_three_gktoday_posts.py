import os
import json
import urllib.request
import urllib.parse
import ssl
import sys
import datetime
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Read Gemini API key from .env
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

# The top 3 GKToday news items we extracted
news_items = [
    {
        "title": "Armed Forces Review Higher Agniveer Retention",
        "description": "The Department of Military Affairs, headed by Chief of Defence Staff General Anil Chauhan, is reviewing a proposal to raise the retention rate of Agniveers under the Agnipath scheme. Currently, the Agnipath scheme retains 25% of Agniveers after 4 years. The proposal is to increase this retention rate to 50% or more.",
        "url": "https://www.gktoday.in/armed-forces-review-higher-agniveer-retention/",
        "date": "July 6, 2026",
        "visual_template": "BEFORE_AFTER",
        "caption_style": "fact_led"
    },
    {
        "title": "Uttar Pradesh Expands Free Residential Education Under JPNSV Scheme",
        "description": "Jai Prakash Narayan Sarvodaya Vidyalaya (JPNSV) schools are a network of free residential schools in Uttar Pradesh managed by the Uttar Pradesh Social Welfare Department. The scheme is being expanded to provide free residential education and academic training to students from weaker sections.",
        "url": "https://www.gktoday.in/uttar-pradesh-expands-free-residential-education-under-jpnsv-scheme/",
        "date": "July 6, 2026",
        "visual_template": "SINGLE_SPOTLIGHT",
        "caption_style": "explainer"
    },
    {
        "title": "Andhra Pradesh Introduces Millet Chikki in Schools",
        "description": "Andhra Pradesh introduced peanut millet jaggery chikki in government schools under the Dokka Seethamma Mid-Day Meal Scheme on 6 July 2026. The new snack replaces conventional peanut chikki, providing enhanced nutritional value to students.",
        "url": "https://www.gktoday.in/andhra-pradesh-introduces-millet-chikki-in-schools/",
        "date": "July 6, 2026",
        "visual_template": "BEFORE_AFTER",
        "caption_style": "fact_led"
    }
]

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={gemini_key}"
headers = {
    "Content-Type": "application/json"
}

def make_call(system_p, user_p):
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_p}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_p}]
        },
        "generationConfig": {
            "maxOutputTokens": 2000,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as res:
            resp = json.loads(res.read().decode("utf-8"))
            if resp and "candidates" in resp and len(resp["candidates"]) > 0:
                return resp["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini API Error: {e}")
    return None

post_contents_list = []

for idx, item in enumerate(news_items):
    num = idx + 1
    print(f"Generating Infographic Post {num} for: '{item['title']}'...")
    
    system_prompt = """
You are SSB Connect's AI copywriter. Generate an Instagram post caption and a visual layout JSON for an Infographic post.

CAPTIONS WRITING RULES:
1. Third-person observer voice, inspiring and disciplined tone.
2. Short, punchy sentences. Break up text with line spacing. Use emojis naturally.
3. Capitalize hooks. Use relevant hashtags at the bottom (5-10 hashtags).
4. No em-dashes anywhere.
5. Caption structure: Hook -> Explanation/Value -> Actionable Tip -> Engagement Question/Call to Comment -> Hashtags.
6. BANNED WORDS (NEVER USE ANY): delve, underscore, vibrant, tapestry, interplay, intricate, garner, pivotal, showcase, foster, align with, landscape, key (as adjective), leverages, encompasses, facilitates, utilized, commenced, subsequent to, prior to, in order to, stands as, serves as, is a testament to, plays a vital role, plays a significant role, plays a crucial role, enduring legacy, lasting impact, indelible mark, it's important to note, it's worth noting, no discussion would be complete without, moreover, furthermore, in addition, setting the stage for, marking a shift, evolving landscape, reflects broader trends, game-changer, supercharge, real results, real strategy, real conversations, disruptive, hustle, grind, crush it, synergy, paradigm shift, thought leader, go viral, revolutionary, groundbreaking, unprecedented, cutting-edge, state-of-the-art, next-generation, empower, unlock, journey, ecosystem, world-class, comprehensive, curated, innovative, transformative, passionate, excited to share.
"""

    user_prompt = f"""
Generate an Infographic post based on this GKToday news item:
Title: {item['title']}
Description: {item['description']}
Date: {item['date']}
URL: {item['url']}

Visual Template: {item['visual_template']}
Caption Style: {item['caption_style']}

Use the following exact output format:

==================================================
{num}. INFOGRAPHIC
==================================================
INFOGRAPHIC CAPTION:
[Instagram caption with summary insight, stats, call to comment, and hashtags]

==================================================
VISUAL LAYOUT JSON
==================================================
```json
{{
  "title_main": "[Main Title, 1-2 words, e.g. AGNIVEER or EDUCATION]", 
  "title_span": "[Highlighted Word, 1-2 words, e.g. RETENTION or EXPANSION]", 
  "subtitle": "[Sub-headline summarizing the change]", 
  "badge": "📊 {item['title'].upper()}", 
  "date_label": "{item['date']}", 
  "takeaway_num": "[Main percentage or stat, e.g. 50% or FREE]", 
  "takeaway_text": "[Key takeaway phrase, e.g. Proposed Agniveer Retention or Free Residential Schools]", 
  "chart_type": "relative_max", 
  "visual_template": "{item['visual_template']}", 
  "caption_style": "{item['caption_style']}", 
  "topic_tags": ["defence", "current_affairs"], 
  "source": "Source: GKToday | @ssb.connect",
  "before_label": "[Before label, e.g. CURRENT RETENTION]", 
  "before_value": "[Before value, e.g. 25%]", 
  "before_desc": "[Before description, e.g. Retained after 4 years]", 
  "after_label": "[After label, e.g. PROPOSED RETENTION]", 
  "after_value": "[After value, e.g. 50%]", 
  "after_desc": "[After description, e.g. Under active MoD review]",
  "spotlight_stat": "[Large spotlight value, e.g. FREE]", 
  "spotlight_unit": "[Unit, e.g. NET]", 
  "spotlight_desc": "[Description, e.g. Jai Prakash Narayan Sarvodaya Vidyalayas network expands in UP]"
}}
```

Make sure the JSON is valid. If the template is BEFORE_AFTER, make sure before_label/value/desc and after_label/value/desc are filled. If template is SINGLE_SPOTLIGHT, make sure spotlight_stat/unit/desc are filled.
"""

    response = make_call(system_prompt, user_prompt)
    if not response:
        print(f"Error: Failed to generate Post {num}")
        sys.exit(1)

    # Parse and separate caption from JSON
    clean_response_text = response.strip()
    json_data_str = None
    
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
    if json_match:
        json_data_str = json_match.group(1).strip()
        split_idx = response.find("==================================================")
        json_label_idx = response.find("VISUAL LAYOUT JSON")
        if json_label_idx != -1:
            split_idx = response.rfind("==================================================", 0, json_label_idx)
        if split_idx != -1:
            clean_response_text = response[:split_idx].strip()
        else:
            clean_response_text = response.split("```json")[0].strip()
            
    post_contents_list.append(clean_response_text)
    
    if json_data_str:
        try:
            post_data = json.loads(json_data_str)
            filename = f"./infographic_data_{num}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(post_data, f, indent=2)
            print(f"Saved {filename}")
        except Exception as e:
            print(f"Error parsing JSON for Post {num}: {e}")

# Save combined captions
combined_posts_text = "\n\n".join(post_contents_list)
with open("./instagram_posts_today.txt", "w", encoding="utf-8") as f:
    f.write(combined_posts_text)
with open("./instagram_posts_today_new.txt", "w", encoding="utf-8") as f:
    f.write(combined_posts_text)

print("\nCaptions generated successfully and saved to instagram_posts_today.txt")

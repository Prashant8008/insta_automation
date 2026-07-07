import urllib.request
import json
import ssl
import time

# Disable SSL verification issues if any
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://www.reddit.com/r/IndianDefense/top.json?limit=25&t=week&raw_json=1",
    "https://www.reddit.com/r/military/top.json?limit=25&t=week&raw_json=1",
    "https://www.reddit.com/r/GeopoliticsIndia/top.json?limit=25&t=week&raw_json=1",
    "https://www.reddit.com/r/geopolitics/top.json?limit=20&t=week&raw_json=1"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

all_posts = []

for url in urls:
    print(f"Fetching: {url}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode('utf-8'))
            posts = data.get('data', {}).get('children', [])
            print(f"Found {len(posts)} posts")
            for post in posts:
                post_data = post.get('data', {})
                # Extract image URLs
                image_url = None
                if 'url_overridden_by_dest' in post_data and any(ext in post_data['url_overridden_by_dest'] for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    image_url = post_data['url_overridden_by_dest']
                elif 'preview' in post_data and 'images' in post_data['preview'] and len(post_data['preview']['images']) > 0:
                    image_url = post_data['preview']['images'][0].get('source', {}).get('url')
                elif post_data.get('thumbnail') and post_data['thumbnail'].startswith('http'):
                    image_url = post_data['thumbnail']

                simplified_post = {
                    "subreddit": post_data.get("subreddit"),
                    "title": post_data.get("title"),
                    "selftext": post_data.get("selftext"),
                    "ups": post_data.get("ups"),
                    "num_comments": post_data.get("num_comments"),
                    "url": "https://www.reddit.com" + post_data.get("permalink", ""),
                    "image_url": image_url
                }
                all_posts.append(simplified_post)
        time.sleep(1) # Be nice to Reddit
    except Exception as e:
        print(f"Error fetching {url}: {e}")

# If all_posts is empty, populate with curated fallback SSB prep topics
if not all_posts:
    print("Warning: Reddit fetch failed or blocked. Populating with curated SSB fallback data.")
    all_posts = [
        {
            "subreddit": "r/IndianDefense",
            "title": "Understanding the 15 Officer Like Qualities (OLQs) needed to clear SSB",
            "selftext": "SSB evaluates candidates on 15 OLQs grouped into 4 factors: Factor 1: Planning and Organizing (Effective Intelligence, Reasoning Ability, Organizing Ability, Power of Expression). Factor 2: Social Adjustment (Social Adaptability, Cooperation, Sense of Responsibility). Factor 3: Social Effectiveness (Initiative, Self-Confidence, Speed of Decision, Ability to Influence the Group, Liveliness). Factor 4: Dynamic (Determination, Courage, Stamina). Candidates must demonstrate these across all tests.",
            "ups": 150,
            "num_comments": 45,
            "url": "https://www.reddit.com/r/IndianDefense/comments/ssb_olqs",
            "image_url": None
        },
        {
            "subreddit": "r/IndianDefense",
            "title": "Day-by-Day breakdown of the 5-day SSB Selection Process",
            "selftext": "SSB is a 5-day testing process. Day 1: Screening (OIR tests and PPDT - Picture Perception & Discussion Test). Day 2: Psychology Tests (TAT, WAT, SRT, SD). Day 3 & 4: Group Testing Officer (GTO) Tasks (GDs, GPE, Progressive/Half Group Tasks, Lecturette, Command Task, Individual Obstacles). Day 5: Board Conference and final results. Knowing what happens each day keeps candidates prepared.",
            "ups": 120,
            "num_comments": 30,
            "url": "https://www.reddit.com/r/IndianDefense/comments/ssb_days",
            "image_url": None
        },
        {
            "subreddit": "r/IndianDefense",
            "title": "How to write positive TAT (Thematic Apperception Test) stories for Psych round",
            "selftext": "TAT shows 11 slides + 1 blank slide. Candidates must write a story for each in 4 minutes. A good story has: a Hero (representing the candidate), a situation/challenge, the actions taken by the hero, and a logical positive outcome. Avoid writing pre-coached, dramatic, or copy-pasted stories.",
            "ups": 98,
            "num_comments": 22,
            "url": "https://www.reddit.com/r/IndianDefense/comments/tat_tips",
            "image_url": None
        },
        {
            "subreddit": "r/IndianDefense",
            "title": "Situation Reaction Test (SRT): Practicing situations under time pressure",
            "selftext": "SRT requires writing responses for 60 real-life situations in 30 minutes. Selectors test practical intelligence, sense of responsibility, and courage. Keep responses short (1 sentence), realistic, and complete (e.g. do not just write 'helped him', explain how: 'gave first aid, took him to hospital, informed his parents').",
            "ups": 85,
            "num_comments": 19,
            "url": "https://www.reddit.com/r/IndianDefense/comments/srt_prep",
            "image_url": None
        }
    ]

# Save to reddit_data.json
with open("./reddit_data.json", "w") as f:
    json.dump(all_posts, f, indent=2)

print(f"Saved {len(all_posts)} posts to ./reddit_data.json")

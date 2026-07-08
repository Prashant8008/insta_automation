import json

plan = json.load(open("daily_post_plan.json", encoding="utf-8"))

print("=== SELECTED NEWS CARDS ===")
for i, p in enumerate(plan["posts"], 1):
    if p["type"] == "NewsCard":
        news = p["news"]
        print(f"Card {i}: [{news['source']}] {news['title'][:80]}")

print()
print("=== SSB CARD ===")
for p in plan["posts"]:
    if p["type"] == "SSBCard":
        print(f"Topic: {p['ssb_topic']}")

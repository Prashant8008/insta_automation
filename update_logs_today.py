"""
update_logs_today.py
Logs news card topics and SSB topics to prevent repetition.
"""
import datetime
import json
import os

post_types = []
plan = {}
if os.path.exists("daily_post_plan.json"):
    with open("daily_post_plan.json", "r", encoding="utf-8") as f:
        plan = json.load(f)
        post_types = plan.get("post_types", [])

news_idx = 0
for idx, ptype in enumerate(post_types):
    num = idx + 1
    if ptype == "NewsCard":
        data_path = f"newscard_{num}.json"
        topic = "Defence News"
        try:
            if os.path.exists(data_path):
                with open(data_path, encoding="utf-8") as f:
                    card = json.load(f)
                topic = card.get("topic") or card.get("headline", topic)
        except Exception:
            assignments = plan.get("news_assignments", [])
            if news_idx < len(assignments):
                topic = assignments[news_idx].get("title", topic)
        news_idx += 1

        log_path = "news-card-log.json"
        try:
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
        log.append({"date": datetime.date.today().isoformat(), "topic": topic, "post_num": num})
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log[-30:], f, indent=2)
        print(f"News card log updated: {topic[:60]}")

    elif ptype == "SSBCard":
        topic = plan.get("ssb_topic", "SSB")
        try:
            if os.path.exists(f"ssbcard_{num}.json"):
                with open(f"ssbcard_{num}.json", encoding="utf-8") as f:
                    topic = json.load(f).get("topic", topic)
        except Exception:
            pass

        log_path = "ssb-topic-log.json"
        try:
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
        log.append({"date": datetime.date.today().isoformat(), "topic": topic, "post_num": num})
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log[-30:], f, indent=2)
        print(f"SSB topic log updated: {topic}")

import os
import json
import requests
import time
import sys
import datetime
import re

from brand_utils import sanitize_brand_text

env_path = "./.env"
access_token = None
ig_user_id = None
dry_run = True

if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("FACEBOOK_ACCESS_TOKEN="):
                access_token = line.strip().split("=", 1)[1]
            elif line.startswith("INSTAGRAM_BUSINESS_ACCOUNT_ID="):
                ig_user_id = line.strip().split("=", 1)[1]
            elif line.startswith("DRY_RUN="):
                dry_run = line.strip().split("=", 1)[1].lower() in ("true", "1", "yes")

access_token = os.environ.get("FACEBOOK_ACCESS_TOKEN", access_token)
ig_user_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", ig_user_id)
if os.environ.get("DRY_RUN"):
    dry_run = os.environ.get("DRY_RUN").lower() in ("true", "1", "yes")

public_base_url = None
try:
    res = requests.get("http://localhost:4040/api/tunnels", timeout=2)
    if res.status_code == 200:
        for tunnel in res.json().get("tunnels", []):
            if tunnel.get("proto") == "https":
                public_base_url = tunnel["public_url"]
                break
        if not public_base_url and res.json().get("tunnels"):
            public_base_url = res.json()["tunnels"][0]["public_url"]
        print(f"Auto-discovered ngrok tunnel: {public_base_url}")
except Exception:
    pass

public_base_url = os.environ.get("PUBLIC_BASE_URL", public_base_url)

if not dry_run and (not access_token or not ig_user_id):
    print("Warning: Missing credentials. Switching to DRY RUN mode.")
    dry_run = True

post_types = ["NewsCard", "NewsCard", "NewsCard", "SSBCard"]
if os.path.exists("daily_post_plan.json"):
    try:
        with open("daily_post_plan.json", "r", encoding="utf-8") as f:
            post_types = json.load(f).get("post_types", post_types)
            print(f"Loaded post types: {post_types}")
    except Exception as e:
        print(f"Error loading plan: {e}")


def get_public_url(local_path):
    if dry_run:
        return f"http://localhost:8000/{local_path.lstrip('./')}"
    if public_base_url:
        url = f"{public_base_url.rstrip('/')}/{local_path.lstrip('./')}"
        print(f"Using public base URL directly: {url}")
        return url
    print(f"Uploading {local_path} to tmpfiles.org...")
    for attempt in range(1, 4):
        try:
            with open(os.path.abspath(local_path), "rb") as f:
                upload_res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, timeout=25)
            if upload_res.status_code == 200:
                upload_json = upload_res.json()
                if upload_json.get("status") == "success":
                    view_url = upload_json["data"]["url"]
                    page_res = requests.get(view_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                    if page_res.status_code == 200:
                        match = re.search(r'href=["\'](https://tmpfiles.org/dl/[^"\']+)["\']', page_res.text)
                        if match:
                            return match.group(1)
                    return view_url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
        except Exception as e:
            print(f"Upload attempt {attempt} failed: {e}")
        if attempt < 3:
            time.sleep(5)
    return f"http://localhost:8000/{local_path.lstrip('./')}"


def extract_caption_for_post(content, num):
    pattern = (
        r"={40,}\s*\n" + str(num) + r"\.\s*(?:NEWS\s*CARD|SSB\s*CARD).*?\n={40,}\s*\nCAPTION:\s*\n(.*?)"
        r"(?=\n={40,}|\Z)"
    )
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


captions = {}
posts_file = "./instagram_posts_today.txt"
if os.path.exists(posts_file):
    with open(posts_file, "r", encoding="utf-8") as f:
        content = f.read()
    for idx in range(len(post_types)):
        captions[idx + 1] = sanitize_brand_text(extract_caption_for_post(content, idx + 1))


def get_scheduled_timestamp(target_hour, target_minute):
    now = datetime.datetime.now()
    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if target_time < now + datetime.timedelta(minutes=20):
        target_time += datetime.timedelta(days=1)
    return int(target_time.timestamp()), target_time.strftime("%Y-%m-%d %I:%M %p")


def get_delay_timestamp(delay_minutes, post_index=0, stagger_minutes=15):
    """Schedule post N minutes from now (daily pipeline: Slack first, Instagram later)."""
    now = datetime.datetime.now()
    total_minutes = max(10, delay_minutes + (post_index * stagger_minutes))
    target_time = now + datetime.timedelta(minutes=total_minutes)
    return int(target_time.timestamp()), target_time.strftime("%Y-%m-%d %I:%M %p")


def create_media_container(image_url, caption=None, scheduled_publish_time=None):
    if dry_run:
        print(f"[DRY RUN] Create container: {image_url} (sched={scheduled_publish_time})")
        return "MOCK_CONTAINER_ID"
    url = f"https://graph.facebook.com/v21.0/{ig_user_id}/media"
    payload = {"image_url": image_url, "access_token": access_token}
    if caption:
        payload["caption"] = caption
    if scheduled_publish_time:
        payload["scheduled_publish_time"] = str(scheduled_publish_time)
    res = requests.post(url, data=payload).json()
    if "id" in res:
        return res["id"]
    error_msg = res.get("error", {}).get("message", "")
    if "whitelist" in error_msg.lower() and scheduled_publish_time:
        print("Notice: Scheduling is not enabled for this account. Falling back to immediate publishing...")
        return create_media_container(image_url, caption, scheduled_publish_time=None)
    print("Error creating container:", res)
    return None


def publish_container(creation_id):
    if dry_run:
        print(f"[DRY RUN] Publish container: {creation_id}")
        return "MOCK_POST_ID"
    url = f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish"
    res = requests.post(url, data={"creation_id": creation_id, "access_token": access_token}).json()
    if "id" in res:
        return res["id"]
    print("Error publishing:", res)
    return None


# Schedule slots for up to 3 news + 1 SSB
NEWS_SLOTS = [(9, 0), (13, 0), (17, 0)]
SSB_SLOT = (20, 0)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--post", type=int, default=None, help="Publish only this post number")
    parser.add_argument("--immediate", action="store_true", help="Publish now instead of scheduling")
    parser.add_argument(
        "--delay-minutes",
        type=int,
        default=None,
        help="Schedule posts N minutes from now (daily pipeline: default 60 after Slack)",
    )
    parser.add_argument(
        "--stagger-minutes",
        type=int,
        default=15,
        help="Minutes between each post when using --delay-minutes",
    )
    args = parser.parse_args()

    daily_delay = args.delay_minutes
    if daily_delay is None and not args.immediate and args.post is None:
        daily_delay = int(os.environ.get("INSTAGRAM_DELAY_MINUTES", "0")) or None

    print(f"--- Instagram Publishing (DRY_RUN={dry_run}) ---")
    if args.immediate:
        print("Mode: publish immediately")
    elif daily_delay:
        print(f"Mode: schedule starting {daily_delay} min from now ({args.stagger_minutes} min apart)")
    else:
        print("Mode: fixed daily time slots")
    news_count = 0
    post_index = 0

    indices = range(len(post_types))
    if args.post is not None:
        indices = [args.post - 1]

    for post_idx, idx in enumerate(indices):
        if idx < 0 or idx >= len(post_types):
            continue

        # Stagger immediate posts to avoid triggering Instagram's spam filters
        if post_idx > 0 and args.immediate and not dry_run:
            stagger_sec = int(os.environ.get("IMMEDIATE_STAGGER_SEC", "300"))
            print(f"\n[Anti-Spam] Sleeping for {stagger_sec} seconds before processing Post {idx+1}...")
            time.sleep(stagger_sec)
        ptype = post_types[idx]
        num = idx + 1
        caption = captions.get(num, "")

        if ptype == "NewsCard":
            png = f"./output/instagram-newscard_{num}.png"
            if not os.path.exists(png):
                print(f"Skipping post {num}: {png} missing")
                continue
            if args.immediate:
                ts, time_str = None, "now (immediate)"
            elif daily_delay:
                ts, time_str = get_delay_timestamp(daily_delay, post_index, args.stagger_minutes)
                post_index += 1
            else:
                hour, minute = NEWS_SLOTS[news_count] if news_count < len(NEWS_SLOTS) else (19, 0)
                news_count += 1
                ts, time_str = get_scheduled_timestamp(hour, minute)
            print(f"\nPost {num}: News Card ({time_str})")
            url = get_public_url(png)
            cid = create_media_container(url, caption, ts)
            if cid:
                if not dry_run:
                    time.sleep(10)
                pid = publish_container(cid)
                print(f"Published! Post ID: {pid}")

        elif ptype == "SSBCard":
            png = f"./output/instagram-ssbcard_{num}.png"
            if not os.path.exists(png):
                print(f"Skipping post {num}: {png} missing")
                continue
            if args.immediate:
                ts, time_str = None, "now (immediate)"
            elif daily_delay:
                ts, time_str = get_delay_timestamp(daily_delay, post_index, args.stagger_minutes)
                post_index += 1
            else:
                ts, time_str = get_scheduled_timestamp(*SSB_SLOT)
            print(f"\nPost {num}: SSB Card ({time_str})")
            url = get_public_url(png)
            cid = create_media_container(url, caption, ts)
            if cid:
                if not dry_run:
                    time.sleep(10)
                pid = publish_container(cid)
                print(f"Published! Post ID: {pid}")

    print("\n--- Publishing finished ---")


if __name__ == "__main__":
    main()

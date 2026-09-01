import os
import sys
import json
import re
import time
import requests
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


def extract_caption_for_post(content, num):
    pattern = (
        r"={40,}\s*\n" + str(num) + r"\.\s*(?:NEWS\s*CARD|SSB\s*CARD).*?\n={40,}\s*\nCAPTION:\s*\n(.*?)"
        r"(?=\n={40,}|\Z)"
    )
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def get_latest_chat_id():
    """Attempt to detect the latest chat ID from getUpdates if not specified."""
    if not BOT_TOKEN:
        return None
    try:
        res = requests.get(f"{API_BASE}/getUpdates", timeout=10).json()
        if res.get("ok") and res.get("result"):
            latest = res["result"][-1]
            if "channel_post" in latest:
                return str(latest["channel_post"]["chat"]["id"])
            elif "message" in latest:
                return str(latest["message"]["chat"]["id"])
            elif "my_chat_member" in latest:
                return str(latest["my_chat_member"]["chat"]["id"])
    except Exception as e:
        print(f"[Telegram] Failed to fetch updates: {e}")
    return None


def send_telegram_message(chat_id, text):
    url = f"{API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=20).json()
        return res.get("ok", False)
    except Exception as e:
        print(f"[Telegram] Send message error: {e}")
        return False


def send_telegram_video(chat_id, video_path, caption="", thumbnail_path=None):
    url = f"{API_BASE}/sendVideo"
    # Telegram caption limit is 1024 chars for media
    main_caption = caption[:1020] + "..." if len(caption) > 1024 else caption
    
    with open(video_path, "rb") as video_file:
        files = {"video": video_file}
        data = {
            "chat_id": chat_id,
            "caption": main_caption,
            "supports_streaming": "true"
        }
        try:
            print(f"[Telegram] Uploading video: {os.path.basename(video_path)} ({os.path.getsize(video_path) / (1024*1024):.2f} MB)...")
            res = requests.post(url, data=data, files=files, timeout=120).json()
            if res.get("ok"):
                print(f"✅ Video delivered successfully to Telegram chat {chat_id}!")
                # If original caption exceeded 1024 chars, send remainder as text
                if len(caption) > 1024:
                    time.sleep(1)
                    send_telegram_message(chat_id, caption[1020:])
                return True
            else:
                print(f"❌ Telegram API Error: {res.get('description', res)}")
                return False
        except Exception as e:
            print(f"❌ Telegram upload error: {e}")
            return False


def send_telegram_photo(chat_id, photo_path, caption=""):
    url = f"{API_BASE}/sendPhoto"
    main_caption = caption[:1020] + "..." if len(caption) > 1024 else caption
    with open(photo_path, "rb") as photo_file:
        files = {"photo": photo_file}
        data = {"chat_id": chat_id, "caption": main_caption}
        try:
            print(f"[Telegram] Uploading image: {os.path.basename(photo_path)}...")
            res = requests.post(url, data=data, files=files, timeout=60).json()
            if res.get("ok"):
                print(f"✅ Image delivered successfully to Telegram chat {chat_id}!")
                return True
            else:
                print(f"❌ Telegram API Error: {res.get('description', res)}")
                return False
        except Exception as e:
            print(f"❌ Telegram upload error: {e}")
            return False


def publish_post_to_telegram(post_num, chat_id):
    post_types = ["NewsCard", "NewsCard", "NewsCard", "SSBCard"]
    if os.path.exists("daily_post_plan.json"):
        try:
            with open("daily_post_plan.json", "r", encoding="utf-8") as f:
                post_types = json.load(f).get("post_types", post_types)
        except Exception:
            pass

    idx = post_num - 1
    ptype = post_types[idx] if 0 <= idx < len(post_types) else "NewsCard"

    # Get caption
    caption = ""
    posts_file = "./instagram_posts_today.txt"
    if os.path.exists(posts_file):
        with open(posts_file, "r", encoding="utf-8") as f:
            caption = extract_caption_for_post(f.read(), post_num)

    # Check for reel first, then fallback to static card
    reel_mp4 = f"./output/reel_{post_num}.mp4"
    card_png = (
        f"./output/instagram-newscard_{post_num}.png"
        if ptype == "NewsCard"
        else f"./output/instagram-ssbcard_{post_num}.png"
    )

    if os.path.exists(reel_mp4):
        print(f"\n--- Delivering Post {post_num} ({ptype} Reel) to Telegram ---")
        return send_telegram_video(chat_id, reel_mp4, caption)
    elif os.path.exists(card_png):
        print(f"\n--- Delivering Post {post_num} ({ptype} Image) to Telegram ---")
        return send_telegram_photo(chat_id, card_png, caption)
    else:
        print(f"⚠️ Neither {reel_mp4} nor {card_png} found for post {post_num}.")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publish Daily Reels & Cards to Telegram")
    parser.add_argument("--chat-id", type=str, default=None, help="Target Telegram Chat ID or Channel (@channel)")
    parser.add_argument("--post", type=int, default=None, help="Publish only specific post number (1-4)")
    parser.add_argument("--test", action="store_true", help="Send a test ping message to verify connection")
    args = parser.parse_args()

    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env file.")
        sys.exit(1)

    target_chat = args.chat_id or CHAT_ID
    if not target_chat:
        print("[Telegram] TELEGRAM_CHAT_ID is not configured in .env. Checking recent bot updates...")
        detected = get_latest_chat_id()
        if detected:
            print(f"[Telegram] Auto-detected chat ID: {detected}")
            target_chat = detected
        else:
            print("❌ Error: Could not determine Telegram Chat ID.")
            print("👉 Please send a message to @daily_driver_001bot or add it to your channel, then run again,")
            print("   or set TELEGRAM_CHAT_ID in .env (e.g. @your_channel_name or chat ID).")
            sys.exit(1)

    if args.test:
        print(f"Sending test ping to Telegram chat {target_chat}...")
        ok = send_telegram_message(
            target_chat,
            "🚀 <b>SSB Connect Automation Bot</b> is connected and ready to deliver daily Reels & updates!"
        )
        if ok:
            print("✅ Test message sent successfully!")
        sys.exit(0 if ok else 1)

    # Determine which posts to publish
    total_posts = 4
    if os.path.exists("daily_post_plan.json"):
        try:
            with open("daily_post_plan.json", "r", encoding="utf-8") as f:
                total_posts = len(json.load(f).get("post_types", [1, 2, 3, 4]))
        except Exception:
            pass

    indices = [args.post] if args.post else list(range(1, total_posts + 1))
    success_count = 0
    for p_num in indices:
        if publish_post_to_telegram(p_num, target_chat):
            success_count += 1
            time.sleep(2)

    print(f"\n🎉 Finished delivering {success_count}/{len(indices)} posts to Telegram.")


if __name__ == "__main__":
    main()

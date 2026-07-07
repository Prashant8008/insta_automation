"""
send_to_slack_instagram.py
Delivers card PNG previews + captions to Slack.

Image delivery priority:
  1. SLACK_BOT_TOKEN — direct file upload (best, no ngrok needed)
  2. tmpfiles.org public URL — works with webhook image blocks
  3. ngrok PUBLIC_BASE_URL — if tunnel is running
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

try:
    import requests
except ImportError:
    requests = None

env_path = "./.env"
webhook_url = None
slack_token = None
slack_channel = None

if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SLACK_WEBHOOK_URL="):
                webhook_url = line.split("=", 1)[1]
            elif line.startswith("SLACK_BOT_TOKEN="):
                slack_token = line.split("=", 1)[1]
            elif line.startswith("SLACK_CHANNEL_ID="):
                slack_channel = line.split("=", 1)[1]

slack_token = os.environ.get("SLACK_BOT_TOKEN", slack_token)
slack_channel = os.environ.get("SLACK_CHANNEL_ID", slack_channel)

if not webhook_url and not slack_token:
    print("Error: Configure SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN in .env")
    exit(0)

public_base_url = os.environ.get("PUBLIC_BASE_URL")
if not public_base_url:
    try:
        req = urllib.request.Request("http://localhost:4040/api/tunnels")
        with urllib.request.urlopen(req, timeout=2) as res:
            data = json.loads(res.read().decode("utf-8"))
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    public_base_url = tunnel["public_url"]
                    break
            if not public_base_url and data.get("tunnels"):
                public_base_url = data["tunnels"][0]["public_url"]
    except Exception:
        pass

post_types = ["NewsCard", "NewsCard", "NewsCard", "SSBCard"]
if os.path.exists("daily_post_plan.json"):
    try:
        with open("daily_post_plan.json", "r", encoding="utf-8") as f:
            post_types = json.load(f).get("post_types", post_types)
    except Exception as e:
        print(f"Error loading plan: {e}")


def extract_caption_for_post(content, num):
    pattern = (
        r"={40,}\s*\n" + str(num) + r"\.\s*(?:NEWS\s*CARD|SSB\s*CARD).*?\n={40,}\s*\nCAPTION:\s*\n(.*?)"
        r"(?=\n={40,}|\Z)"
    )
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


captions = {}
if os.path.exists("./instagram_posts_today.txt"):
    with open("./instagram_posts_today.txt", "r", encoding="utf-8") as f:
        content = f.read()
    for idx in range(len(post_types)):
        captions[idx + 1] = extract_caption_for_post(content, idx + 1)


def upload_to_tmpfiles(image_path):
    """Upload PNG to tmpfiles.org and return a direct public URL for Slack."""
    if not requests or not os.path.exists(image_path):
        return None
    for attempt in range(1, 4):
        try:
            with open(image_path, "rb") as f:
                res = requests.post(
                    "https://tmpfiles.org/api/v1/upload",
                    files={"file": f},
                    timeout=30,
                )
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    view_url = data["data"]["url"]
                    page_res = requests.get(view_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                    if page_res.status_code == 200:
                        match = re.search(r'href=["\'](https://tmpfiles.org/dl/[^"\']+)["\']', page_res.text)
                        if match:
                            direct = match.group(1)
                            print(f"  Uploaded to tmpfiles: {direct}")
                            return direct
                    direct = view_url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
                    print(f"  Uploaded to tmpfiles (fallback): {direct}")
                    return direct
        except Exception as e:
            print(f"  tmpfiles upload attempt {attempt} failed: {e}")
        if attempt < 3:
            time.sleep(3)
    return None


def get_public_image_url(image_path):
    if public_base_url and public_base_url.startswith("https") and os.path.exists(image_path):
        clean = image_path.replace("./", "").replace("\\", "/")
        return f"{public_base_url.rstrip('/')}/{clean}"
    return upload_to_tmpfiles(image_path)


def send_webhook(payload):
    if not webhook_url:
        return False
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as res:
            res.read()
            return True
    except Exception as e:
        print(f"Webhook error: {e}")
        return False


def upload_slack_file(file_path, title, initial_comment):
    """Upload image directly via Slack Bot API (files.upload external flow)."""
    if not slack_token or not slack_channel:
        return False
    if not os.path.exists(file_path):
        print(f"  File not found: {file_path}")
        return False

    size = os.path.getsize(file_path)
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        data = urllib.parse.urlencode({
            "filename": os.path.basename(file_path),
            "length": size,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://slack.com/api/files.getUploadURLExternal",
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as res:
            resp = json.loads(res.read().decode("utf-8"))
        if not resp.get("ok"):
            print(f"  Slack upload URL error: {resp.get('error')}")
            return False

        upload_url = resp["upload_url"]
        file_id = resp["file_id"]

        with open(file_path, "rb") as f:
            file_data = f.read()
        req = urllib.request.Request(upload_url, data=file_data, method="POST")
        with urllib.request.urlopen(req) as res:
            if res.status != 200:
                print("  Slack raw upload failed")
                return False

        complete_headers = {
            "Authorization": f"Bearer {slack_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "files": [{"id": file_id, "title": title}],
            "channel_id": slack_channel,
            "initial_comment": initial_comment,
        }
        req = urllib.request.Request(
            "https://slack.com/api/files.completeUploadExternal",
            data=json.dumps(payload).encode("utf-8"),
            headers=complete_headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as res:
            resp = json.loads(res.read().decode("utf-8"))
        if resp.get("ok"):
            print(f"  Uploaded to Slack: {title}")
            return True
        print(f"  Slack complete error: {resp.get('error')}")
    except Exception as e:
        print(f"  Slack file upload error: {e}")
    return False


def send_card_via_webhook(title, caption, image_path):
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title}},
    ]

    image_url = get_public_image_url(image_path)
    if image_url:
        blocks.append({
            "type": "image",
            "image_url": image_url,
            "alt_text": title,
        })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_Image upload failed — PNG saved locally at `" + image_path.replace("./", "") + "`_",
            },
        })

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Caption:*\n{caption}"},
    })

    success = send_webhook({"blocks": blocks, "text": title})
    if not success and image_url:
        print("  Webhook failed with image block, retrying with text only...")
        text_blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": title}},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Caption:*\n{caption}"},
            }
        ]
        return send_webhook({"blocks": text_blocks, "text": title})
    return success


def main():
    print("Delivering card previews to Slack...")

    if webhook_url:
        delay = os.environ.get("INSTAGRAM_DELAY_MINUTES", "60")
        send_webhook({
            "text": (
                f"🔔 *SSB Connect — Daily Cards Generated* (3 News + 1 SSB)\n"
                f"_Instagram will auto-post in ~{delay} minutes — no confirmation needed._"
            ),
        })

    for idx, ptype in enumerate(post_types):
        num = idx + 1
        caption = captions.get(num, "")
        if not caption:
            print(f"No caption for post {num}, skipping")
            continue

        if ptype == "NewsCard":
            png = f"./output/instagram-newscard_{num}.png"
            title = f"📰 News Card {num}"
        else:
            png = f"./output/instagram-ssbcard_{num}.png"
            title = f"🎯 SSB Prep Card ({num})"

        if not os.path.exists(png):
            print(f"Warning: {png} missing — run build_instagram_visuals.cjs first")
            if webhook_url:
                send_webhook({
                    "text": f"*{title}*\n{caption}\n_(image not built yet)_",
                })
            continue

        print(f"Sending post {num} ({ptype})...")
        sent = False
        if slack_token and slack_channel:
            comment = f"*{title}*\n\n*Caption:*\n{caption}"
            sent = upload_slack_file(png, title, comment)

        if not sent and webhook_url:
            sent = send_card_via_webhook(title, caption, png)

        if not sent:
            print(f"  Failed to deliver post {num}")

    print("Slack delivery finished.")


if __name__ == "__main__":
    main()

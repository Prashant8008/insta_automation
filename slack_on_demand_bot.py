"""
slack_on_demand_bot.py

Two modes:
  1) Automatic daily pipeline (run_instagram_pipeline.py) — cards → Slack → Instagram
  2) Slack on-demand — user topic → search → TEXT to Slack → optional card + Instagram

Slack on-demand flow:
  /igpost <topic>  →  web search + caption text  →  Slack preview
  User clicks "Post to Instagram"  →  build card PNG  →  publish
"""
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError:
    print("Install: pip install slack-bolt")
    sys.exit(1)

from on_demand_core import (
    clear_pending,
    publish_on_demand,
    research_text_from_instruction,
    save_pending,
)
from send_to_slack_instagram import upload_to_tmpfiles

for key in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL_ID"):
    if not os.environ.get(key) and os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    os.environ[key] = line.strip().split("=", 1)[1]

BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")

if not BOT_TOKEN or not APP_TOKEN:
    print("Error: Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env")
    sys.exit(1)

app = App(token=BOT_TOKEN)

_gen_lock = threading.Lock()
_busy = False


def _log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(os.path.join(ROOT, "slack_bot.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _ensure_in_channel(client, channel):
    try:
        client.conversations_join(channel=channel)
        _log(f"Joined channel {channel}")
    except Exception as e:
        if "already_in_channel" not in str(e).lower():
            _log(f"Could not join channel {channel}: {e}")


def _safe_post(client, channel, text, **kwargs):
    try:
        return client.chat_postMessage(channel=channel, text=text, **kwargs)
    except Exception as e:
        err = str(e)
        if "not_in_channel" in err:
            print(f"[slack] Bot not in channel {channel} — invite @SSB Connect Bot")
        else:
            print(f"[slack] chat_postMessage failed: {e}")
        return None


def _send_text_preview(client, channel, instruction, result, respond=None):
    """Phase 1 preview: caption text only, no card image yet."""
    caption = result.get("caption", "")
    ptype = result.get("post_type", "NewsCard")
    label = "News" if ptype == "NewsCard" else "SSB Prep"

    web = (result.get("plan") or {}).get("web_search") or {}
    source_text = ""
    if web.get("top_title"):
        source_text = f"\n*Source:* {web.get('top_title', '')}"

    plain = (
        f"*{label} Post Draft*\n"
        f"*Topic:* {instruction}\n"
        f"{source_text}\n\n"
        f"*Caption:*\n{caption}\n\n"
        f"_Click Post to Instagram below to build the card and publish._"
    )

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{label} Post Draft — review caption"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Your topic:*\n>{instruction[:500]}"},
        },
    ]
    if web.get("top_title"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Sources found ({web.get('sources_found', 0)}):*\n{web.get('top_title', '')[:500]}",
            },
        })
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Caption:*\n{caption[:2900]}"},
    })
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "Card image is created only when you click Post to Instagram.",
        }],
    })
    blocks.append({
        "type": "actions",
        "block_id": "on_demand_actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Post to Instagram"},
                "style": "primary",
                "action_id": "confirm_ig_post",
                "value": instruction[:1900],
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Cancel"},
                "style": "danger",
                "action_id": "cancel_ig_post",
            },
        ],
    })

    resp = None
    if respond:
        try:
            respond(text=f"{label} draft ready", blocks=blocks, response_type="in_channel")
            resp = {"ts": "slash_response"}
            _log("Preview sent via slash respond (in_channel)")
        except Exception as e:
            _log(f"slash respond failed: {e}")

    if not resp:
        _ensure_in_channel(client, channel)
        resp = _safe_post(client, channel, text=plain, blocks=blocks)
        if not resp:
            _log("blocks post failed — trying plain text")
            resp = _safe_post(client, channel, text=plain)
        if not resp:
            _log("ERROR: could not deliver preview to Slack")
            return None

    save_pending(
        instruction=instruction,
        channel=channel,
        message_ts=resp.get("ts", "") if isinstance(resp, dict) else "",
        caption=caption,
        post_type=ptype,
        plan=result.get("plan"),
    )
    return resp


def _run_text_research(client, channel, user_id, instruction, respond=None):
    """Phase 1: search web + write caption text (fast, no card render)."""
    global _busy
    started = time.time()
    _log(f"Research started: {instruction[:80]}")
    _ensure_in_channel(client, channel)

    status_ts = None
    if respond:
        try:
            respond(
                text=f"<@{user_id}> Searching the web and writing caption...",
                response_type="in_channel",
            )
        except Exception:
            pass
    else:
        status = _safe_post(
            client,
            channel,
            text=f"<@{user_id}> Searching the web and writing caption...",
        )
        status_ts = status.get("ts") if status else None

    try:
        result = research_text_from_instruction(instruction)
        elapsed = int(time.time() - started)
        _log(f"Research done in {elapsed}s ok={result.get('ok')}")

        if not result.get("ok"):
            err = result.get("error", "unknown")
            _log(f"Research failed: {err}")
            msg = f"<@{user_id}> Failed after {elapsed}s: {err}"
            if respond:
                respond(text=msg, response_type="ephemeral")
            else:
                _safe_post(client, channel, text=msg)
            return

        if status_ts:
            try:
                client.chat_update(
                    channel=channel,
                    ts=status_ts,
                    text=f"<@{user_id}> Caption ready in {elapsed}s — review below.",
                )
            except Exception:
                pass

        preview = _send_text_preview(client, channel, instruction, result, respond=respond)
        if not preview:
            fail_msg = (
                f"<@{user_id}> Caption was generated but could not post to Slack. "
                f"Please add @SSB Connect Bot to this channel and try again."
            )
            if respond:
                respond(text=fail_msg, response_type="ephemeral")
            else:
                _safe_post(client, channel, text=fail_msg)
    except Exception as e:
        _log(f"research error: {e}")
        msg = f"<@{user_id}> Error: {e}"
        if respond:
            respond(text=msg, response_type="ephemeral")
        else:
            _safe_post(client, channel, text=msg)
    finally:
        _busy = False


def _run_instagram_publish(client, channel, user_id):
    """Phase 2: build card + publish to Instagram."""
    global _busy
    started = time.time()
    status = _safe_post(
        client,
        channel,
        text=f"<@{user_id}> Building card image and posting to Instagram...",
    )
    status_ts = status.get("ts") if status else None

    try:
        result = publish_on_demand(immediate=True)
        elapsed = int(time.time() - started)

        if not result.get("ok"):
            _safe_post(
                client,
                channel,
                text=f"<@{user_id}> Instagram post failed after {elapsed}s: {result.get('error', 'unknown')}",
            )
            return

        png = result.get("png")
        image_url = upload_to_tmpfiles(png) if png else None
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}> Posted to Instagram in {elapsed}s.",
                },
            },
        ]
        if image_url:
            blocks.append({
                "type": "image",
                "image_url": image_url,
                "alt_text": "Posted card",
            })

        _safe_post(client, channel, text="Posted to Instagram successfully.", blocks=blocks)
    except Exception as e:
        print(f"[slack] publish error: {e}")
        _safe_post(client, channel, text=f"<@{user_id}> Publish error: {e}")
    finally:
        _busy = False


def _handle_instruction(instruction, client, channel, user_id, respond=None):
    global _busy
    instruction = (instruction or "").strip()
    if not instruction:
        msg = "Please provide a topic. Example: `/igpost DRDO missile test`"
        if respond:
            respond(msg)
        else:
            _safe_post(client, channel, text=msg)
        return

    if _busy:
        msg = "Already working on a post — please wait (~20 sec), then try again."
        if respond:
            respond(msg)
        else:
            _safe_post(client, channel, text=f"<@{user_id}> {msg}")
        return

    if respond:
        respond(f"Researching: _{instruction[:200]}_ ... (caption in ~20 sec)")

    if not _gen_lock.acquire(blocking=False):
        if respond:
            respond("Another request is in progress. Please wait.")
        return

    _busy = True
    try:
        thread = threading.Thread(
            target=_run_text_research,
            args=(client, channel, user_id, instruction, respond),
            daemon=True,
        )
        thread.start()
    finally:
        _gen_lock.release()


@app.command("/igpost")
def slash_igpost(ack, body, client, respond):
    ack()
    _handle_instruction(
        body.get("text", "").strip(),
        client,
        body.get("channel_id"),
        body.get("user_id"),
        respond=respond,
    )


@app.event("app_mention")
def on_mention(event, client):
    text = event.get("text", "")
    instruction = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    if instruction.lower().startswith("post "):
        instruction = instruction[5:].strip()
    _handle_instruction(instruction, client, event["channel"], event["user"])


@app.event("message")
def on_message(event, client):
    if event.get("bot_id") or event.get("subtype"):
        return
    if CHANNEL_ID and event.get("channel") != CHANNEL_ID:
        return

    text = (event.get("text") or "").strip()
    if not text or text.startswith("/"):
        return
    if not text.lower().startswith("igpost:"):
        return

    instruction = text.split(":", 1)[1].strip()
    if len(instruction) < 4:
        return
    _handle_instruction(instruction, client, event["channel"], event["user"])


@app.action("confirm_ig_post")
def on_confirm(ack, body, client):
    global _busy
    ack()
    channel = body["channel"]["id"]
    user = body["user"]["id"]

    if _busy:
        _safe_post(client, channel, text=f"<@{user}> Please wait — another job is running.")
        return

    if not _gen_lock.acquire(blocking=False):
        _safe_post(client, channel, text=f"<@{user}> Please wait — another job is running.")
        return

    _busy = True
    try:
        thread = threading.Thread(
            target=_run_instagram_publish,
            args=(client, channel, user),
            daemon=True,
        )
        thread.start()
    finally:
        _gen_lock.release()


@app.action("cancel_ig_post")
def on_cancel(ack, body, client):
    ack()
    clear_pending()
    _safe_post(client, body["channel"]["id"], text="Cancelled. No post was published.")


if __name__ == "__main__":
    print("Slack on-demand bot starting (Socket Mode)...")
    print("Flow: topic -> text preview -> optional Instagram card post")
    print("Triggers: /igpost, @mention, igpost: <topic>")
    if CHANNEL_ID:
        print(f"Channel filter: {CHANNEL_ID}")
    sys.stdout.flush()
    SocketModeHandler(app, APP_TOKEN).start()

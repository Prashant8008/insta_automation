"""
on_demand_core.py
Generate a single Instagram card from a free-text Slack instruction.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime

from brand_utils import sanitize_brand_text

ROOT = os.path.dirname(os.path.abspath(__file__))
PENDING_PATH = os.path.join(ROOT, "pending_on_demand.json")
STEP_TIMEOUT_SEC = int(os.environ.get("PIPELINE_STEP_TIMEOUT", "90"))
GENERATION_LOCK = os.path.join(ROOT, ".generation.lock")

SSB_KEYWORDS = {
    "tat": "TAT",
    "wat": "WAT",
    "srt": "SRT",
    "ppdt": "PPDT",
    "oir": "OIR",
    "gto": "GTO",
    "ssb": "SSB",
    "picture perception": "PPDT",
    "word association": "WAT",
    "situation reaction": "SRT",
}


def detect_post_type(instruction: str) -> str:
    text = instruction.lower()
    for kw in SSB_KEYWORDS:
        if kw in text:
            return "SSBCard"
    return "NewsCard"


def detect_ssb_topic(instruction: str) -> str:
    text = instruction.lower()
    for kw, topic in SSB_KEYWORDS.items():
        if kw in text and topic != "SSB":
            return topic
    return "TAT"


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def find_matching_article(instruction: str, news_data: list) -> dict | None:
    words = _tokenize(instruction)
    if not words:
        return None
    best, best_score = None, 0
    for item in news_data:
        blob = f"{item.get('title', '')} {item.get('description', '')}".lower()
        score = sum(1 for w in words if len(w) > 3 and w in blob)
        if score > best_score:
            best_score = score
            best = item
    return best if best_score >= 2 else None


def build_on_demand_plan(instruction: str, post_type: str | None = None) -> dict:
    post_type = post_type or detect_post_type(instruction)
    news_data = []
    news_path = os.path.join(ROOT, "ai_news_data.json")
    if os.path.exists(news_path):
        with open(news_path, encoding="utf-8") as f:
            news_data = json.load(f)

    web_research = None
    web_article = None

    plan = {
        "mode": "on_demand",
        "user_instruction": instruction,
        "num_posts": 1,
        "post_types": [post_type],
        "news_assignments": [],
        "ssb_topic": detect_ssb_topic(instruction),
        "reasoning": f"On-demand card from Slack: {instruction[:80]}",
        "web_search": None,
    }

    if post_type == "NewsCard":
        # 1) Search the web first
        try:
            from web_search_news import research_topic
            web_research = research_topic(instruction)
            web_article = web_research.get("article")
            plan["web_search"] = {
                "query": instruction,
                "sources_found": len(web_research.get("all_results", [])),
                "top_title": (web_article or {}).get("title", ""),
                "top_url": (web_article or {}).get("url", ""),
            }
        except Exception as e:
            print(f"[on_demand] web search error: {e}")

        article = web_article or find_matching_article(instruction, news_data)
        if article:
            plan["news_assignments"] = [{
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "url": article.get("url", ""),
                "source": article.get("source", "Web"),
                "pubDate": article.get("pubDate", datetime.now().strftime("%B %d, %Y")),
            }]
            plan["reasoning"] = (
                f"Web search + card for: {instruction[:60]} "
                f"(source: {article.get('source', 'Web')})"
            )
        else:
            plan["news_assignments"] = [{
                "title": instruction[:120],
                "description": (
                    f"User-requested topic: {instruction}. "
                    "Write a defence/current-affairs news card using verified public facts only."
                ),
                "url": "",
                "source": "SSB Connect",
                "pubDate": datetime.now().strftime("%B %d, %Y"),
            }]
    return plan


def save_plan(plan: dict):
    path = os.path.join(ROOT, "daily_post_plan.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)


def save_pending(
    instruction: str,
    channel: str,
    message_ts: str = "",
    caption: str = "",
    post_type: str = "NewsCard",
    plan: dict | None = None,
):
    data = {
        "instruction": instruction,
        "channel": channel,
        "preview_message_ts": message_ts,
        "caption": caption,
        "post_type": post_type,
        "plan": plan,
        "stage": "text_ready",
        "created_at": datetime.now().isoformat(),
    }
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_pending():
    if not os.path.exists(PENDING_PATH):
        return None
    with open(PENDING_PATH, encoding="utf-8") as f:
        return json.load(f)


def clear_pending():
    if os.path.exists(PENDING_PATH):
        os.remove(PENDING_PATH)


def run_step(script: str, extra_args=None, timeout: int | None = None) -> bool:
    cmd = [sys.executable, script] + (extra_args or [])
    try:
        r = subprocess.run(cmd, cwd=ROOT, timeout=timeout or STEP_TIMEOUT_SEC)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[on_demand] TIMEOUT: {script} exceeded {timeout or STEP_TIMEOUT_SEC}s")
        return False


def run_node(script: str, timeout: int | None = None) -> bool:
    try:
        r = subprocess.run(
            ["node", script],
            cwd=ROOT,
            timeout=timeout or STEP_TIMEOUT_SEC,
        )
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[on_demand] TIMEOUT: {script} exceeded {timeout or STEP_TIMEOUT_SEC}s")
        return False


def ensure_news_feed():
    if not os.path.exists(os.path.join(ROOT, "ai_news_data.json")):
        run_step("fetch_ai_news_rss.py")


def _read_caption_from_posts_file() -> str:
    posts_file = os.path.join(ROOT, "instagram_posts_today.txt")
    if not os.path.exists(posts_file):
        return ""
    with open(posts_file, encoding="utf-8") as f:
        content = f.read()
    m = re.search(
        r"CAPTION:\s*\n(.*?)(?=\n={40,}|\Z)",
        content,
        re.DOTALL,
    )
    return sanitize_brand_text(m.group(1).strip()) if m else ""


def research_text_from_instruction(instruction: str, post_type: str | None = None) -> dict:
    """
    Phase 1 (Slack on-demand): web search + AI caption text only.
    No card image rendering yet.
    """
    ensure_news_feed()
    plan = build_on_demand_plan(instruction, post_type)
    save_plan(plan)

    if not run_step("generate_instagram_posts.py"):
        return {"ok": False, "error": "Caption generation failed"}

    caption = _read_caption_from_posts_file()
    if not caption:
        return {"ok": False, "error": "No caption generated"}

    ptype = plan["post_types"][0]
    return {
        "ok": True,
        "instruction": instruction,
        "post_type": ptype,
        "caption": caption,
        "plan": plan,
        "stage": "text_ready",
    }


def build_card_from_pending() -> dict:
    """
    Phase 2 (Slack on-demand): render card PNG from saved plan + JSON.
    """
    pending = load_pending()
    if not pending:
        return {"ok": False, "error": "No pending post — request a topic first"}

    plan_path = os.path.join(ROOT, "daily_post_plan.json")
    if not os.path.exists(plan_path):
        return {"ok": False, "error": "Post plan missing — request a topic again"}

    if not run_step("fetch_card_images.py"):
        return {"ok": False, "error": "Background image fetch failed"}

    if not run_step("build_instagram_visuals.py"):
        return {"ok": False, "error": "Card rendering failed"}

    ptype = pending.get("post_type", "NewsCard")
    png = (
        os.path.join(ROOT, "output", "instagram-newscard_1.png")
        if ptype == "NewsCard"
        else os.path.join(ROOT, "output", "instagram-ssbcard_1.png")
    )
    if not os.path.exists(png):
        return {"ok": False, "error": f"Card image not created: {png}"}

    return {
        "ok": True,
        "png": png,
        "caption": pending.get("caption", _read_caption_from_posts_file()),
        "post_type": ptype,
        "instruction": pending.get("instruction", ""),
    }


def generate_card_from_instruction(instruction: str, post_type: str | None = None) -> dict:
    """Full pipeline in one shot (CLI / testing)."""
    text_result = research_text_from_instruction(instruction, post_type)
    if not text_result.get("ok"):
        return text_result

    save_pending(
        instruction=text_result["instruction"],
        channel="",
        message_ts="",
        caption=text_result["caption"],
        post_type=text_result["post_type"],
        plan=text_result.get("plan"),
    )
    card_result = build_card_from_pending()
    if not card_result.get("ok"):
        return card_result

    return {
        "ok": True,
        "instruction": instruction,
        "post_type": text_result["post_type"],
        "png": card_result["png"],
        "caption": text_result["caption"],
        "plan": text_result.get("plan"),
    }


def publish_on_demand(immediate: bool = True) -> dict:
    card = build_card_from_pending()
    if not card.get("ok"):
        return card

    args = ["--post", "1"]
    if immediate:
        args.append("--immediate")
    if not run_step("publish_to_instagram.py", args):
        return {"ok": False, "error": "Instagram publish failed"}
    if os.path.exists(os.path.join(ROOT, "cleanup_pipeline.py")):
        run_step("cleanup_pipeline.py", ["--stage", "after_publish"])
    clear_pending()
    return {"ok": True, "png": card.get("png"), "caption": card.get("caption")}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("instruction", help="What to post about")
    parser.add_argument("--type", choices=["NewsCard", "SSBCard"])
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    result = generate_card_from_instruction(args.instruction, args.type)
    print(json.dumps({k: v for k, v in result.items() if k != "plan"}, indent=2))
    if args.publish and result.get("ok"):
        print(publish_on_demand())

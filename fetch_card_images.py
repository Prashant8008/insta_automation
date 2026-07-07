"""
fetch_card_images.py
Downloads background images for news/SSB cards from article og:image tags.
Falls back to a branded gradient placeholder when no image is found.
"""
import json
import os
import re
import ssl
import urllib.request
from html.parser import HTMLParser

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SSBConnectBot/1.0)",
}


class OgImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_image = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        attr = dict(attrs)
        prop = (attr.get("property") or attr.get("name") or "").lower()
        if prop in ("og:image", "twitter:image"):
            content = attr.get("content", "").strip()
            if content and content.startswith("http"):
                self.og_image = content


def _fetch_og_image(url):
    if not url or not url.startswith("http"):
        return None
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=8) as res:
            html = res.read(250_000).decode("utf-8", errors="ignore")
        parser = OgImageParser()
        parser.feed(html)
        return parser.og_image
    except Exception as e:
        print(f"[fetch_card_images] og:image fetch failed for {url}: {e}")
        return None


def _download_image(image_url, dest_path):
    try:
        req = urllib.request.Request(image_url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=20) as res:
            data = res.read()
        if len(data) < 5000:
            return False
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"[fetch_card_images] download failed {image_url}: {e}")
        return False


def _write_placeholder(dest_path, label="NEWS"):
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e3a5f"/>
    </linearGradient>
  </defs>
  <rect width="1080" height="1080" fill="url(#g)"/>
  <text x="540" y="520" text-anchor="middle" fill="#84CC16" font-size="72" font-family="Arial Black, sans-serif">{label}</text>
  <text x="540" y="600" text-anchor="middle" fill="#94a3b8" font-size="36" font-family="Arial, sans-serif">@ssb.connect</text>
</svg>"""
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return True


def resolve_card_background(post_num, article_url=None, badge="NEWS"):
    rel_path = f"./assets/card-bg_{post_num}.jpg"
    svg_fallback = f"./assets/card-bg_{post_num}.svg"

    image_url = _fetch_og_image(article_url) if article_url else None
    if image_url and _download_image(image_url, rel_path):
        print(f"[fetch_card_images] Post {post_num}: saved {rel_path}")
        return rel_path

    if _write_placeholder(svg_fallback, badge):
        print(f"[fetch_card_images] Post {post_num}: using placeholder {svg_fallback}")
        return svg_fallback

    return svg_fallback


def main():
    if not os.path.exists("daily_post_plan.json"):
        print("[fetch_card_images] daily_post_plan.json not found — skipping.")
        return

    with open("daily_post_plan.json", "r", encoding="utf-8") as f:
        plan = json.load(f)

    post_types = plan.get("post_types", [])
    news_assignments = plan.get("news_assignments", [])
    news_idx = 0

    for idx, ptype in enumerate(post_types):
        num = idx + 1
        if ptype == "NewsCard" and news_idx < len(news_assignments):
            article = news_assignments[news_idx]
            news_idx += 1
            bg = resolve_card_background(num, article.get("url"), badge="NEWS")
            article["background_image"] = bg
        elif ptype == "SSBCard":
            topic = plan.get("ssb_topic", "SSB")
            bg = resolve_card_background(num, badge=topic)
            plan["ssb_background_image"] = bg

    with open("daily_post_plan.json", "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    print("[fetch_card_images] Background images attached to daily_post_plan.json")


if __name__ == "__main__":
    main()

import os
import json
import re
import html
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(ROOT, 'assets'), exist_ok=True)

CHROME_PATHS = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
]
CHROME_PATH = None
for path in CHROME_PATHS:
    if os.path.exists(path):
        CHROME_PATH = path
        break

if not CHROME_PATH:
    import shutil
    CHROME_PATH = shutil.which("google-chrome") or shutil.which("chromium-browser") or shutil.which("chromium") or shutil.which("chrome")

if not CHROME_PATH:
    print("Error: Google Chrome not found in standard paths or system PATH.")
    sys.exit(1)

def load_plan():
    plan_path = os.path.join(ROOT, 'daily_post_plan.json')
    if not os.path.exists(plan_path):
        return { "post_types": ['NewsCard', 'NewsCard', 'NewsCard', 'SSBCard'] }
    with open(plan_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def escape_html(text):
    return html.escape(str(text or ''))

def apply_highlights(text, phrases, class_name='highlight'):
    escaped_text = escape_html(text)
    for phrase in (phrases or []):
        if not phrase:
            continue
        escaped_phrase = escape_html(phrase)
        pattern = re.escape(escaped_phrase)
        escaped_text = re.sub(pattern, lambda m: f'<span class="{class_name}">{m.group(0)}</span>', escaped_text, flags=re.IGNORECASE)
    return escaped_text

def replace_all(template, replacements):
    out = template
    for key, val in replacements.items():
        out = out.replace(key, str(val) if val is not None else '')
    return out

def resolve_bg_path(rel_path):
    normalized = (rel_path or '').replace('./', '').replace('\\', '/')
    abs_path = os.path.join(ROOT, normalized)
    if os.path.exists(abs_path):
        return 'file:///' + abs_path.replace('\\', '/')
    fallback_path = os.path.join(ROOT, 'assets', 'card-bg_1.svg')
    return 'file:///' + fallback_path.replace('\\', '/')

def build_news_card(num, data):
    template_path = os.path.join(ROOT, 'instagram-newscard-template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    bg_url = resolve_bg_path(data.get("background_image"))
    headline_html = apply_highlights(
        (data.get("headline") or data.get("title") or '').upper(),
        data.get("highlight_phrases", [])
    )
    
    replacements = {
        '{{BACKGROUND_IMAGE}}': bg_url,
        '{{BADGE}}': escape_html(data.get("badge", 'NEWS')),
        '{{HEADLINE_HTML}}': headline_html,
        '{{IMAGE_SOURCE}}': escape_html(data.get("image_source", 'Source: News | @ssb.connect'))
    }
    
    html_content = replace_all(template, replacements)
    out_path = os.path.join(ROOT, f"instagram-newscard_{num}.html")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Built news card HTML: {out_path}")
    return out_path

def build_ssb_card(num, data):
    template_path = os.path.join(ROOT, 'instagram-ssbcard-template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
        
    bg_url = resolve_bg_path(data.get("background_image"))
    
    header_highlight = data.get("header_highlight")
    header_phrases = [header_highlight] if header_highlight else []
    header_html = apply_highlights(data.get("header", ''), header_phrases)
    
    detail_html = apply_highlights(data.get("detail", ''), data.get("detail_highlights", []))
    
    replacements = {
        '{{BACKGROUND_IMAGE}}': bg_url,
        '{{TOPIC}}': escape_html(data.get("topic", 'SSB')),
        '{{HEADER_HTML}}': header_html,
        '{{HEADLINE}}': escape_html(data.get("headline", '')),
        '{{DETAIL_HTML}}': detail_html
    }
    
    html_content = replace_all(template, replacements)
    out_path = os.path.join(ROOT, f"instagram-ssbcard_{num}.html")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Built SSB card HTML: {out_path}")
    return out_path

def capture_screenshot(html_path, png_path):
    file_url = 'file:///' + html_path.replace('\\', '/')
    print(f"Taking screenshot of {file_url} -> {png_path}")
    
    cmd = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        f"--screenshot={png_path}",
        "--window-size=1080,1080",
        "--no-sandbox",
        "--hide-scrollbars",
        file_url
    ]
    try:
        subprocess.run(cmd, check=True)
        if os.path.exists(png_path):
            print(f"Captured {png_path}")
            return True
        else:
            if os.path.exists("screenshot.png"):
                os.rename("screenshot.png", png_path)
                print(f"Captured and moved screenshot.png -> {png_path}")
                return True
            print(f"Error: Screenshot file not found at {png_path}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"Chrome screenshot failed: {e}")
        return False

def main():
    plan = load_plan()
    post_types = plan.get("post_types", [])
    
    for idx, ptype in enumerate(post_types):
        num = idx + 1
        prefix = 'newscard' if ptype == 'NewsCard' else 'ssbcard'
        data_path = os.path.join(ROOT, f"{prefix}_{num}.json")
        if not os.path.exists(data_path):
            print(f"Warning: {data_path} not found")
            continue
        
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        html_path = ""
        if ptype == 'NewsCard':
            html_path = build_news_card(num, data)
        elif ptype == 'SSBCard':
            html_path = build_ssb_card(num, data)
            
        if html_path:
            png_name = f"instagram-newscard_{num}.png" if ptype == 'NewsCard' else f"instagram-ssbcard_{num}.png"
            png_path = os.path.join(OUTPUT_DIR, png_name)
            capture_screenshot(html_path, png_path)
            
    print("All card visuals rendered via Python + local Chrome.")

if __name__ == "__main__":
    main()

"""SSB Connect branding helpers for captions and post text."""
import re

BRAND_FOOTER_LINE = "Follow @ssb.connect for daily SSB prep & defence updates."


def sanitize_brand_text(text: str) -> str:
    if not text:
        return text
    replacements = [
        (r"follow\s+@?founderswing\s+for\s+daily\s+frameworks?\.?", BRAND_FOOTER_LINE),
        (r"follow\s+founders\s+wing\s+for\s+daily\s+frameworks?\.?", BRAND_FOOTER_LINE),
        (r"@founderswing", "@ssb.connect"),
        (r"founders\s+wing", "SSB Connect"),
        (r"founderswing", "ssb.connect"),
    ]
    out = text
    for pattern, repl in replacements:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    if BRAND_FOOTER_LINE.lower() not in out.lower():
        out = out.rstrip() + "\n\n" + BRAND_FOOTER_LINE
    return out

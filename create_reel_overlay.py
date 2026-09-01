import os
from PIL import Image, ImageDraw, ImageFont

def create_reel_overlay(
    badge_text="DEFENCE FLASH",
    headline_text="",
    output_path="temp_overlay.png",
    width=1080,
    height=1920
):
    """
    Creates a 1080x1920 transparent PNG overlay with:
    - Top gradient vignette (for status bar and badge)
    - News category badge pill (e.g. [🔴 DEFENCE FLASH])
    - Clean top headline if provided
    - Bottom gradient vignette (for caption contrast)
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Top Gradient Vignette (0px to 450px)
    for y in range(450):
        alpha = int(220 * (1.0 - (y / 450.0) ** 1.3))
        draw.line([(0, y), (width, y)], fill=(10, 15, 25, alpha))

    # 2. Bottom Gradient Vignette (1400px to 1920px)
    for y in range(1400, height):
        progress = (y - 1400) / 520.0
        alpha = int(230 * (progress ** 1.2))
        draw.line([(0, y), (width, y)], fill=(5, 8, 15, alpha))

    # Try loading bold system fonts, fallback to default
    def get_font(size, bold=True):
        candidates = [
            "arialbd.ttf", "seguisb.ttf", "impact.ttf", "trebucbd.ttf",
            "Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ]
        for c in candidates:
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    badge_font = get_font(36, bold=True)
    
    # 3. Top News Badge Pill & Location Pill
    badge_full = f"🔴 {badge_text.upper().strip()}"
    badge_x = 70
    badge_y = 120
    
    # Measure badge text
    bbox = draw.textbbox((0, 0), badge_full, font=badge_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    pad_x = 24
    pad_y = 14
    pill_w = tw + pad_x * 2
    pill_h = th + pad_y * 2
    
    # Draw glowing pill background
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + pill_w, badge_y + pill_h)],
        radius=pill_h // 2,
        fill=(220, 38, 38, 240), # Vivid Crimson Red
        outline=(255, 255, 255, 200),
        width=2
    )
    draw.text((badge_x + pad_x, badge_y + pad_y - 2), badge_full, font=badge_font, fill=(255, 255, 255, 255))

    # Location pill tag (📍 INDIA)
    loc_full = "📍 INDIA"
    loc_bbox = draw.textbbox((0, 0), loc_full, font=badge_font)
    loc_tw = loc_bbox[2] - loc_bbox[0]
    loc_pill_w = loc_tw + pad_x * 2
    loc_x = badge_x + pill_w + 14

    draw.rounded_rectangle(
        [(loc_x, badge_y), (loc_x + loc_pill_w, badge_y + pill_h)],
        radius=pill_h // 2,
        fill=(15, 23, 42, 230),
        outline=(255, 255, 255, 160),
        width=2
    )
    draw.text((loc_x + pad_x, badge_y + pad_y - 2), loc_full, font=badge_font, fill=(255, 255, 255, 255))

    # 4. If headline provided, draw top headline
    if headline_text:
        head_font = get_font(52, bold=True)
        # Word wrap headline
        words = headline_text.split()
        lines = []
        cur = []
        for w in words:
            cur.append(w)
            bbox = draw.textbbox((0, 0), " ".join(cur), font=head_font)
            if bbox[2] - bbox[0] > width - 140:
                cur.pop()
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))

        hy = badge_y + pill_h + 30
        for line in lines[:3]: # Max 3 lines
            draw.text((70, hy), line, font=head_font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 200))
            hy += 64

    img.save(output_path, "PNG")
    print(f"Overlay created: {output_path}")
    return output_path

if __name__ == "__main__":
    create_reel_overlay("DEFENCE UPDATE", "India Successfully Tests Next-Gen VSHORADS Missile System")

import os
import sys
import json
import asyncio
import subprocess
import re
import math
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
import edge_tts

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def escape_ffmpeg_path(path):
    """Escape Windows file paths for FFmpeg filter strings (subtitles filter)."""
    p = os.path.abspath(path).replace("\\", "/")
    # Escape colon for drive letters in ffmpeg filter graph
    p = p.replace(":", "\\:")
    return p


def create_reel_overlay(
    badge_text="DEFENCE FLASH",
    headline_text="",
    output_path="temp_overlay.png",
    width=1080,
    height=1920
):
    """
    Creates a 1080x1920 transparent PNG overlay with:
    - Top dark gradient vignette (for status bar & headline readability)
    - News category badge pill (e.g. 🔴 DEFENCE UPDATE)
    - Bold headline (if provided)
    - Bottom dark gradient vignette (for caption contrast)
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Top Gradient Vignette (0px to 480px)
    for y in range(480):
        alpha = int(220 * (1.0 - (y / 480.0) ** 1.3))
        draw.line([(0, y), (width, y)], fill=(8, 12, 22, alpha))

    # 2. Bottom Gradient Vignette (1350px to 1920px)
    for y in range(1350, height):
        progress = (y - 1350) / 570.0
        alpha = int(235 * (progress ** 1.2))
        draw.line([(0, y), (width, y)], fill=(5, 8, 15, alpha))

    # Bold font loader
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

    badge_font = get_font(34, bold=True)
    
    # 3. Top News Badge Pill & Location Pill
    badge_full = f"🔴 {badge_text.upper().strip()}"
    badge_x = 70
    badge_y = 130
    
    bbox = draw.textbbox((0, 0), badge_full, font=badge_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    pad_x = 24
    pad_y = 12
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
        fill=(15, 23, 42, 230), # Deep Navy Glassmorphism
        outline=(255, 255, 255, 160),
        width=2
    )
    draw.text((loc_x + pad_x, badge_y + pad_y - 2), loc_full, font=badge_font, fill=(255, 255, 255, 255))

    # 4. Top Headline
    if headline_text:
        head_font = get_font(48, bold=True)
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

        hy = badge_y + pill_h + 24
        for line in lines[:3]: # Max 3 lines
            draw.text((70, hy), line, font=head_font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 220))
            hy += 58

    img.save(output_path, "PNG")
    return output_path


async def generate_voiceover_and_subtitles(
    text,
    voice=None,
    rate=None,
    audio_out="temp_voice.mp3",
    ass_out="temp_subtitles.ass"
):
    """
    Synthesizes speech via edge-tts and outputs:
    1. Clean voiceover mp3
    2. Styled ASS subtitles chunked into 3-5 punchy words
    """
    voice = voice or os.environ.get("REEL_VOICE", "en-IN-NeerjaExpressiveNeural")
    rate = rate or os.environ.get("REEL_VOICE_RATE", "+0%")
    comm = edge_tts.Communicate(text, voice, rate=rate)
    boundaries = []
    
    with open(audio_out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                boundaries.append(chunk)

    # Calculate audio duration via ffmpeg probe
    duration = get_media_duration(audio_out)
    if not boundaries:
        # Fallback if boundaries weren't emitted
        boundaries.append({"offset": 0, "duration": int(duration * 10_000_000), "text": text})

    # Build ASS Subtitles
    create_ass_file(boundaries, duration, ass_out)
    return duration


def get_media_duration(file_path):
    """Get media duration in seconds using ffmpeg probe."""
    cmd = [
        FFMPEG_EXE, "-i", file_path,
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return 15.0


def format_ass_time(seconds):
    """Format seconds into ASS timestamp: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def create_ass_file(boundaries, total_duration, output_path):
    """Generate high-contrast, viral-styled ASS subtitle file."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HormoziYellow, Impact, 68, &H0000FFFF, &H000000FF, &H00000000, &H80000000, -1, 0, 0, 0, 100, 100, 1, 0, 1, 6, 4, 2, 60, 60, 420, 1
Style: HormoziWhite, Impact, 68, &H00FFFFFF, &H000000FF, &H00000000, &H80000000, -1, 0, 0, 0, 100, 100, 1, 0, 1, 6, 4, 2, 60, 60, 420, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    
    # Process sentence boundaries into 3-4 word punchy chunks
    for b in boundaries:
        start_sec = b["offset"] / 10_000_000.0
        dur_sec = b["duration"] / 10_000_000.0
        text = b.get("text", "").strip()
        if not text:
            continue
        
        words = text.split()
        if not words:
            continue

        # Chunk into 3-4 words max
        chunk_size = 4
        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
        chunk_dur = dur_sec / len(chunks)

        for idx, chunk in enumerate(chunks):
            c_start = start_sec + (idx * chunk_dur)
            c_end = c_start + chunk_dur
            chunk_str = " ".join(chunk).upper()
            
            # Alternate style between Yellow highlight and White
            style = "HormoziYellow" if idx % 2 == 0 else "HormoziWhite"
            
            events.append(
                f"Dialogue: 0,{format_ass_time(c_start)},{format_ass_time(c_end)},{style},,0,0,0,,{chunk_str}"
            )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")


def build_news_reel(
    script_text,
    headline,
    badge_text="DEFENCE UPDATE",
    image_path=None,
    output_video="output/reel_1.mp4",
    voice=None,
    bg_music=None
):
    """
    End-to-End Generator:
    1. Synthesizes voiceover + subtitles
    2. Builds 9:16 Ken Burns zoom video from image
    3. Overlays aesthetic news header & glowing subtitles
    4. Renders ready-to-publish 1080x1920 Instagram Reel
    """
    os.makedirs(os.path.dirname(output_video) or ".", exist_ok=True)
    temp_dir = "temp_reel"
    os.makedirs(temp_dir, exist_ok=True)

    audio_file = os.path.join(temp_dir, "voice.mp3")
    ass_file = os.path.join(temp_dir, "subtitles.ass")
    overlay_file = os.path.join(temp_dir, "overlay.png")
    prepared_bg = os.path.join(temp_dir, "bg_prepared.png")

    print(f"\n🎬 Generating AI News Reel: '{headline}'...")
    print(f"🎙️ Synthesizing Voiceover with {voice}...")
    
    # 1. Generate Voiceover + Subtitles
    duration = asyncio.run(
        generate_voiceover_and_subtitles(
            script_text,
            voice=voice,
            audio_out=audio_file,
            ass_out=ass_file
        )
    )
    # Add a slight 0.5s padding at the end for smoothness
    total_duration = math.ceil(duration + 0.6)
    total_frames = int(total_duration * 30)
    print(f"⏱️ Video Duration: {total_duration:.1f}s ({total_frames} frames)")

    # 2. Select & Prepare Background Image
    fallback_assets = [
        "assets/defence_soldiers.png",
        "assets/defence_jet.png",
        "assets/defence_navy.png",
        "assets/defence_tank.png",
        "assets/defence_drone.png"
    ]
    
    valid_bg = None
    if image_path and os.path.exists(image_path) and not image_path.lower().endswith(".svg"):
        valid_bg = image_path
    else:
        for a in fallback_assets:
            if os.path.exists(a):
                valid_bg = a
                break

    prep_background_image(valid_bg, prepared_bg)

    # 3. Create News Graphic Overlay
    create_reel_overlay(
        badge_text=badge_text,
        headline_text=headline,
        output_path=overlay_file,
        width=1080,
        height=1920
    )

    # 4. Render Video via FFmpeg
    print("🎥 Rendering 1080x1920 Reel via FFmpeg...")
    escaped_ass = escape_ffmpeg_path(ass_file)
    escaped_overlay = overlay_file.replace("\\", "/")

    # Filter graph:
    # 1. Ken Burns slow zoom on background
    # 2. Overlay the top badge/gradient overlay PNG
    # 3. Burn in ASS dynamic subtitles
    filter_complex = (
        f"[0:v]zoompan=z='min(zoom+0.0006,1.15)':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30[bg];"
        f"[bg][1:v]overlay=0:0[v_over];"
        f"[v_over]ass='{escaped_ass}'[v_out]"
    )

    cmd = [
        FFMPEG_EXE, "-y",
        "-loop", "1", "-i", prepared_bg,
        "-i", overlay_file,
        "-i", audio_file,
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", "2:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(total_duration),
        output_video
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"❌ FFmpeg Error: {res.stderr}")
        return None

    print(f"✅ Generated Reel Successfully: {output_video}")
    return output_video


def prep_background_image(src_path, dst_path, target_w=1080, target_h=1920):
    """
    Ensures input image fills the 1080x1920 frame perfectly.
    If image is horizontal (e.g. 16:9), it scales with center crop.
    """
    img = None
    if src_path and os.path.exists(src_path):
        try:
            img = Image.open(src_path).convert("RGB")
        except Exception:
            img = None

    if img is None:
        for a in ["assets/defence_soldiers.png", "assets/defence_jet.png", "assets/defence_navy.png"]:
            if os.path.exists(a):
                try:
                    img = Image.open(a).convert("RGB")
                    break
                except Exception:
                    pass

    if img is None:
        # Create gradient image fallback
        img = Image.new("RGB", (target_w, target_h), (15, 23, 42))

    iw, ih = img.size
    
    # Calculate aspect ratios
    target_ratio = target_w / target_h
    img_ratio = iw / ih

    if img_ratio > target_ratio:
        # Wider than 9:16: scale by height, crop sides
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        # Taller than 9:16: scale by width, crop top/bottom
        new_w = target_w
        new_h = int(new_w / img_ratio)

    img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Center crop to 1080x1920
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img_cropped = img_resized.crop((left, top, left + target_w, top + target_h))
    img_cropped.save(dst_path, "PNG")


def render_all_daily_reels():
    """
    Looks for daily_post_plan.json or newscard_*.json / ssbcard_*.json
    and renders output/reel_1.mp4 ... output/reel_4.mp4.
    """
    post_types = ["NewsCard", "NewsCard", "NewsCard", "SSBCard"]
    if os.path.exists("daily_post_plan.json"):
        try:
            with open("daily_post_plan.json", "r", encoding="utf-8") as f:
                post_types = json.load(f).get("post_types", post_types)
        except Exception as e:
            print(f"Warning reading plan: {e}")

    rendered = []
    for idx, ptype in enumerate(post_types):
        num = idx + 1
        prefix = "newscard" if ptype == "NewsCard" else "ssbcard"
        json_file = f"{prefix}_{num}.json"
        
        if not os.path.exists(json_file):
            print(f"Skipping Post {num} (missing {json_file})")
            continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            continue

        # Extract spoken script or fallback
        script = data.get("spoken_script")
        if not script:
            if ptype == "NewsCard":
                script = (
                    f"Breaking defence update. {data.get('headline', '')}. "
                    f"Stay ahead with daily strategic and defence insights. "
                    f"Follow SSB Connect for more updates!"
                )
            else:
                script = (
                    f"SSB preparation tip for {data.get('topic', 'SSB')}. "
                    f"{data.get('headline', '')}. {data.get('detail', '')}. "
                    f"Save this reel and follow SSB Connect for daily SSB success!"
                )

        headline = data.get("headline", data.get("header", ""))
        badge = data.get("badge", "DEFENCE UPDATE" if ptype == "NewsCard" else "SSB TIP")
        bg_image = data.get("background_image")
        out_vid = f"output/reel_{num}.mp4"

        result = build_news_reel(
            script_text=script,
            headline=headline,
            badge_text=badge,
            image_path=bg_image,
            output_video=out_vid
        )
        if result:
            rendered.append(result)

    print(f"\n🎉 Finished rendering {len(rendered)} daily reels in output/")
    return rendered


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate AI Kinetic News Reels")
    parser.add_argument("--all", action="store_true", help="Render all daily reels from JSON files")
    parser.add_argument("--post", type=int, default=None, help="Render specific post number")
    parser.add_argument("--sample", action="store_true", help="Render sample reel")
    args = parser.parse_args()

    if args.sample or (not args.all and args.post is None):
        sample_script = (
            "India has successfully tested its next-generation very short range air defence missile system. "
            "The test demonstrated pinpoint accuracy against high-speed aerial threats at low altitudes, "
            "bolstering border security. Follow SSB Connect for daily defence updates!"
        )
        sample_head = "DRDO Successfully Tests Next-Gen Air Defence System"
        build_news_reel(
            script_text=sample_script,
            headline=sample_head,
            badge_text="DEFENCE UPDATE",
            image_path="assets/defence_jet.png",
            output_video="output/sample_news_reel.mp4"
        )
    elif args.all:
        render_all_daily_reels()
    elif args.post:
        # Render single post
        num = args.post
        for prefix in ("newscard", "ssbcard"):
            json_file = f"{prefix}_{num}.json"
            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                script = data.get("spoken_script", data.get("headline", ""))
                head = data.get("headline", data.get("header", ""))
                badge = data.get("badge", "DEFENCE UPDATE")
                bg = data.get("background_image")
                build_news_reel(script, head, badge, bg, f"output/reel_{num}.mp4")
                break

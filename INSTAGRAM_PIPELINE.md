# Instagram Video Reel & Card Pipeline (SSB Connect)

Daily automation: **3 AI News Reels/Cards + 1 SSB Prep Reel/Card**.

## Post & Video formats

| # | Type | Output Formats | Visual & Audio style |
|---|------|----------------|----------------------|
| 1–3 | **News Reel / Card** | `reel_1.mp4` (1080×1920) + `newscard_1.png` | Ken Burns motion + neural voiceover + glowing synced subtitles + red pill badge |
| 4 | **SSB Reel / Card** | `reel_4.mp4` (1080×1920) + `ssbcard_4.png` | Practical actionable advice + neural voiceover + styled dynamic captions |

## Run

```bash
cd daily-instagram-posts-pipeline
python run_instagram_pipeline.py              # Generate reels & cards + post immediately (5-min interval)
python run_instagram_pipeline.py --generate   # fetch & generate Reels + Cards only (no publish)
python run_instagram_pipeline.py --publish    # publish existing Reels directly
python run_instagram_pipeline.py --immediate  # post Reels to Instagram right away (5-min interval)

# Standalone Reel Generator
python generate_news_reel.py --all            # render all planned reels from JSON
python generate_news_reel.py --sample         # render sample test reel (output/sample_news_reel.mp4)
```

## Pipeline steps

1. `fetch_ai_news_rss.py` + `fetch_additional_sources.py` — news feeds
2. `plan_daily_posts.py` — pick top 3 news + rotate SSB topic
3. `fetch_card_images.py` — article og:image backgrounds
4. `generate_instagram_posts.py` — Gemini spoken scripts + captions + card JSON
5. `build_instagram_visuals.py` — Card HTML → PNG (1080×1080 fallback)
6. `generate_news_reel.py` — Edge-TTS voiceover + Ken Burns 9:16 video render (1080×1920 MP4)
7. `update_logs_today.py` — dedup logs
8. `publish_to_instagram.py` — Meta Graph API (Reels media container)

## Environment (`.env`)

```
GEMINI_API_KEY=...
FACEBOOK_ACCESS_TOKEN=...
INSTAGRAM_BUSINESS_ACCOUNT_ID=...
DRY_RUN=true
PUBLIC_BASE_URL=          # optional ngrok URL for live publishing
```

## Output files

- `output/reel_1.mp4` … `_4.mp4`
- `output/instagram-newscard_1.png` … `_3.png`
- `output/instagram-ssbcard_4.png`
- `newscard_1.json`, `ssbcard_4.json` — card layout data
- `instagram_posts_today.txt` — captions

## Auto-cleanup

After **Generate-only** (`--generate`), temporary build intermediates are deleted automatically:
HTML, JSON, and temp audio/images. Dated captions are kept in `instagram_posts_YYYYMMDD.txt`.

After **Instagram publish**, all post intermediates are cleaned up.

Manual cleanup:
```bash
python cleanup_pipeline.py --stage after_generate --include-media
python cleanup_pipeline.py --stage legacy   # one-time old file purge
```

| Post | Type | Time (IST) |
|------|------|------------|
| Reel 1 | News Reel | **8:00 AM** |
| Reel 2 | News Reel | **10:00 AM** |
| Reel 3 | News Reel | **7:00 PM** |
| Reel 4 | SSB Tip Reel | **9:00 PM** |


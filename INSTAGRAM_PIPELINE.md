# Instagram Card Pipeline (SSB Connect)

Daily automation: **3 news cards + 1 SSB prep card**.

## Post types

| # | Type | Visual style |
|---|------|----------------|
| 1–3 | **NewsCard** | Full-bleed photo + NEWS badge + yellow headline highlights |
| 4 | **SSBCard** | Stacked layout (header → image → yellow band → detail) for TAT/WAT/SRT/PPDT tips |

Replaces the old Carousel, Poll, and chart Infographic pipeline.

## Run

```bash
cd daily-instagram-posts-pipeline
python run_instagram_pipeline.py              # Slack now + Instagram in 1 hour (auto)
python run_instagram_pipeline.py --generate   # fetch, generate, Slack preview only
python run_instagram_pipeline.py --publish    # schedule Instagram from existing PNGs
python run_instagram_pipeline.py --immediate  # post to Instagram right away
```

## Pipeline steps

1. `fetch_ai_news_rss.py` + `fetch_additional_sources.py` — news feeds
2. `plan_daily_posts.py` — pick top 3 news + rotate SSB topic
3. `fetch_card_images.py` — article og:image backgrounds
4. `generate_instagram_posts.py` — Gemini captions + card JSON
5. `build_instagram_visuals.cjs` — HTML → PNG (1080×1080)
6. `update_logs_today.py` — dedup logs
7. `send_to_slack_instagram.py` — preview (needs ngrok for images)
8. `publish_to_instagram.py` — Meta Graph API

## Environment (`.env`)

```
GEMINI_API_KEY=...
SLACK_WEBHOOK_URL=...
FACEBOOK_ACCESS_TOKEN=...
INSTAGRAM_BUSINESS_ACCOUNT_ID=...
DRY_RUN=true
PUBLIC_BASE_URL=          # optional ngrok URL for live publishing
```

## Output files

- `output/instagram-newscard_1.png` … `_3.png`
- `output/instagram-ssbcard_4.png`
- `newscard_1.json`, `ssbcard_4.json` — card layout data
- `instagram_posts_today.txt` — captions

## On-demand from Slack (type topic → preview → confirm → Instagram)

Keeps the scheduled daily pipeline. **Additionally**, run the Slack bot:

```bash
pip install slack-bolt
python slack_on_demand_bot.py
```

**One-time Slack app setup** (api.slack.com):
1. Create app → enable **Socket Mode** → App Token `connections:write` → `SLACK_APP_TOKEN`
2. Bot scopes: `chat:write`, `commands`, `app_mentions:read`, `channels:history`
3. Install to workspace → `SLACK_BOT_TOKEN`
4. Add slash command `/igpost`
5. Add to `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   SLACK_CHANNEL_ID=C...   # optional
   ```

**In Slack:**
```
/igpost DRDO VSHORADS missile test success
/igpost SSB tip: how to approach PPDT picture
@YourBot post Agniveer retention news
igpost: latest Navy helicopter induction
```

Bot generates the card → sends preview with **Post to Instagram** / **Cancel** buttons → posts only after you confirm.

**CLI test (no Slack bot):**
```bash
python on_demand_core.py "DRDO missile test" 
python on_demand_core.py "PPDT picture tips" --publish
```

## Auto-cleanup

After **Slack-only** (`--generate`), temp files are deleted automatically:
HTML, JSON, backgrounds, PNGs. Dated captions kept in `instagram_posts_YYYYMMDD.txt`.

After **Instagram publish**, all post artifacts are removed.

Manual cleanup:
```bash
python cleanup_pipeline.py --stage after_slack --include-pngs
python cleanup_pipeline.py --stage legacy   # one-time old file purge
```

| Post | Time (IST) |
|------|------------|
| News 1 | 9:00 AM |
| News 2 | 1:00 PM |
| News 3 | 5:00 PM |
| SSB | 8:00 PM |

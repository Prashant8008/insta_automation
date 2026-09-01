import os
import sys
import subprocess
import time
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PIPELINE_DIR)
load_dotenv(os.path.join(PIPELINE_DIR, ".env"))


def run_command(args, desc):
    print(f"\n{'=' * 50}")
    print(f"▶ Running: {desc}...")
    print(f"Command: {' '.join(args)}")
    print(f"{'=' * 50}")
    try:
        subprocess.run(args, check=True, cwd=PIPELINE_DIR)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {desc}: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Instagram News + SSB Card & Reel Pipeline")
    parser.add_argument("--generate", action="store_true", help="Fetch and generate Reels and Cards without publishing")
    parser.add_argument("--publish", action="store_true", help="Publish to Instagram")
    parser.add_argument(
        "--immediate",
        action="store_true",
        help="Post to Instagram immediately (skip scheduling delay)",
    )
    parser.add_argument(
        "--require-new",
        action="store_true",
        help="Check if there is new news since last run; exit cleanly if nothing new",
    )
    args = parser.parse_args()

    run_all = not args.generate and not args.publish
    py = sys.executable
    generate_only = args.generate and not args.publish
    delay_minutes = os.environ.get("INSTAGRAM_DELAY_MINUTES", "0")

    print("🚀 STARTING INSTAGRAM PIPELINE (3 News + 1 SSB) 🚀")

    if run_all or args.generate:
        plan_cmd = [py, "plan_daily_posts.py"]
        if args.require_new:
            plan_cmd.append("--require-new")

        steps = [
            ([py, "fetch_ai_news_rss.py"], "Defence & Current Affairs RSS Fetch"),
            ([py, "fetch_additional_sources.py"], "Additional News Sources"),
            (plan_cmd, "Daily Post Planning (3 News + 1 SSB)"),
            ([py, "fetch_card_images.py"], "Card Background Image Fetch"),
            ([py, "generate_instagram_posts.py"], "Caption & Card JSON Generation"),
            ([py, "build_instagram_visuals.py"], "Card HTML Build & PNG Screenshot"),
            ([py, "generate_news_reel.py", "--all"], "AI Kinetic News Reels Video Render"),
            ([py, "update_logs_today.py"], "Update Run Logs"),
        ]

        for cmd, desc in steps:
            script = cmd[1] if len(cmd) > 1 and cmd[0] == py else cmd[-1]
            if not os.path.exists(script):
                print(f"Skipping missing script: {script}")
                continue

            print(f"\n{'=' * 50}")
            print(f"▶ Running: {desc}...")
            print(f"Command: {' '.join(cmd)}")
            print(f"{'=' * 50}")

            res = subprocess.run(cmd, cwd=PIPELINE_DIR)
            if "plan_daily_posts.py" in cmd:
                if res.returncode == 2:
                    print(f"\n{'=' * 50}")
                    print("ℹ️ No new/breaking news found since earlier run today.")
                    print("Pipeline shutting down cleanly without posting.")
                    print(f"{'=' * 50}\n")
                    sys.exit(0)
                elif res.returncode != 0:
                    print(f"❌ Error in post planning. Exiting.")
                    sys.exit(1)
            elif any(script in cmd for script in ("generate_instagram_posts.py", "build_instagram_visuals.py", "generate_news_reel.py")):
                if res.returncode != 0:
                    print(f"❌ {desc} failed. Exiting.")
                    sys.exit(1)

        if generate_only and os.path.exists("cleanup_pipeline.py"):
            run_command(
                [py, "cleanup_pipeline.py", "--stage", "after_generate"],
                "Auto-cleanup temp files",
            )

    if run_all or args.publish:
        publish_cmd = [py, "publish_to_instagram.py"]
        if args.immediate or run_all:
            publish_cmd.append("--immediate")
        elif delay_minutes and delay_minutes != "0":
            publish_cmd.extend(["--delay-minutes", str(delay_minutes)])

        print("\n▶ Starting HTTP server on port 8000 for Meta API...")
        server_process = subprocess.Popen([py, "-m", "http.server", "8000"], cwd=PIPELINE_DIR)
        time.sleep(2)
        try:
            if os.path.exists("publish_to_instagram.py"):
                run_command(publish_cmd, "Instagram Publishing")
        finally:
            print("\n▶ Stopping HTTP server...")
            server_process.terminate()
            server_process.wait()

        # Optional: Deliver to Telegram if configured
        if os.path.exists("publish_to_telegram.py") and os.environ.get("TELEGRAM_BOT_TOKEN"):
            run_command([py, "publish_to_telegram.py"], "Telegram Delivery")

        if os.path.exists("cleanup_pipeline.py"):
            run_command([py, "cleanup_pipeline.py", "--stage", "after_publish"], "Auto-cleanup after publish")

    print("\n✅ PIPELINE COMPLETED SUCCESSFULLY ✅")


if __name__ == "__main__":
    main()


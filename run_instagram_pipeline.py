import os
import sys
import subprocess
import time

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PIPELINE_DIR)


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

    parser = argparse.ArgumentParser(description="Instagram News + SSB Card Pipeline")
    parser.add_argument("--generate", action="store_true", help="Fetch, generate cards, Slack preview only")
    parser.add_argument("--publish", action="store_true", help="Publish to Instagram")
    parser.add_argument(
        "--immediate",
        action="store_true",
        help="Post to Instagram immediately (skip 1-hour delay)",
    )
    args = parser.parse_args()

    run_all = not args.generate and not args.publish
    py = sys.executable
    slack_only = args.generate and not args.publish
    delay_minutes = os.environ.get("INSTAGRAM_DELAY_MINUTES", "60")

    print("🚀 STARTING INSTAGRAM CARD PIPELINE (3 News + 1 SSB) 🚀")

    if run_all or args.generate:
        steps = [
            ([py, "fetch_ai_news_rss.py"], "Defence & Current Affairs RSS Fetch"),
            ([py, "fetch_additional_sources.py"], "Additional News Sources"),
            ([py, "plan_daily_posts.py"], "Daily Post Planning (3 News + 1 SSB)"),
            ([py, "fetch_card_images.py"], "Card Background Image Fetch"),
            ([py, "generate_instagram_posts.py"], "Caption & Card JSON Generation"),
            ([py, "build_instagram_visuals.py"], "Card HTML Build & PNG Screenshot"),
            ([py, "update_logs_today.py"], "Update Run Logs"),
        ]

        for cmd, desc in steps:
            script = cmd[-1]
            if not os.path.exists(script):
                print(f"Skipping missing script: {script}")
                continue
            if cmd[-1] == "generate_instagram_posts.py":
                if not run_command(cmd, desc):
                    print("❌ Generation failed. Exiting.")
                    sys.exit(1)
            elif cmd[-1] == "build_instagram_visuals.py":
                if not run_command(cmd, desc):
                    print("❌ Visual rendering failed. Exiting.")
                    sys.exit(1)
            else:
                run_command(cmd, desc)

        print("\n▶ Starting HTTP server on port 8000 for Slack previews...")
        server_process = subprocess.Popen([py, "-m", "http.server", "8000"], cwd=PIPELINE_DIR)
        time.sleep(2)
        try:
            if os.path.exists("send_to_slack_instagram.py"):
                run_command([py, "send_to_slack_instagram.py"], "Slack Preview Delivery")
        finally:
            print("\n▶ Stopping HTTP server...")
            server_process.terminate()
            server_process.wait()

        if slack_only and os.path.exists("cleanup_pipeline.py"):
            run_command(
                [py, "cleanup_pipeline.py", "--stage", "after_slack", "--include-pngs"],
                "Auto-cleanup temp files",
            )

    if run_all or args.publish:
        publish_cmd = [py, "publish_to_instagram.py"]
        if args.immediate:
            publish_cmd.append("--immediate")
        elif run_all or (args.publish and not args.immediate):
            publish_cmd.extend(["--delay-minutes", str(delay_minutes)])

        print(f"\n▶ Scheduling Instagram posts ({delay_minutes} min after Slack, no user confirmation)...")
        print("▶ Starting HTTP server on port 8000 for Meta API...")
        server_process = subprocess.Popen([py, "-m", "http.server", "8000"], cwd=PIPELINE_DIR)
        time.sleep(2)
        try:
            if os.path.exists("publish_to_instagram.py"):
                run_command(publish_cmd, "Instagram Publishing (scheduled)")
        finally:
            print("\n▶ Stopping HTTP server...")
            server_process.terminate()
            server_process.wait()

        if os.path.exists("cleanup_pipeline.py"):
            run_command([py, "cleanup_pipeline.py", "--stage", "after_publish"], "Auto-cleanup after publish")

    print("\n✅ PIPELINE COMPLETED SUCCESSFULLY ✅")


if __name__ == "__main__":
    main()

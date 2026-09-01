"""
cleanup_pipeline.py
Removes temporary build files so the folder does not pile up.

Stages:
  after_generate — delete HTML/JSON/temp images after generation
                   (keeps dated caption archive in instagram_posts_YYYYMMDD.txt)
  after_publish  — same as after_generate + removes output PNGs/MP4s
  legacy         — one-time purge of old carousel/poll/infographic leftovers
"""
import glob
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))


def _delete(path):
    if not os.path.exists(path):
        return 0
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        print(f"  deleted: {path}")
        return 1
    except Exception as e:
        print(f"  skip {path}: {e}")
        return 0


def _delete_glob(pattern):
    count = 0
    for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
        count += _delete(path)
    return count


def cleanup_after_generate(include_media=False):
    """Remove build intermediates."""
    print("[cleanup] Removing build intermediates...")
    n = 0
    n += _delete_glob("instagram-newscard_*.html")
    n += _delete_glob("instagram-ssbcard_*.html")
    n += _delete_glob("newscard_*.json")
    n += _delete_glob("ssbcard_*.json")
    n += _delete_glob("assets/card-bg_*")
    n += _delete_glob("instagram-infographic_*.html")
    n += _delete_glob("instagram-poll_*.html")
    n += _delete_glob("infographic_data*.json")
    n += _delete_glob("carousel_data_*.json")
    n += _delete_glob("poll_data_*.json")
    n += _delete_glob("spotlight_data_*.json")
    n += _delete_glob("temp_reel/*")
    n += _delete("temp_reel")
    n += _delete_glob("temp_*.*")
    n += _delete("instagram_posts_today.txt")
    if include_media:
        n += _delete_glob("output/instagram-*.png")
        n += _delete_glob("output/reel_*.mp4")
    print(f"[cleanup] Removed {n} items.")
    return n


def cleanup_after_publish():
    """Remove PNGs/MP4s and intermediates after Instagram publish."""
    return cleanup_after_generate(include_media=True)


def cleanup_legacy():
    """One-time removal of old pipeline templates and temp carousel HTML."""
    print("[cleanup] Legacy purge...")
    n = 0
    legacy_templates = [
        "instagram-poll-template.html",
        "instagram-poll.html",
        "instagram-infographic.html",
        "template-status-breakdown.html",
        "template-before-after.html",
        "template-single-spotlight.html",
        "template-timeline.html",
    ]
    for name in legacy_templates:
        n += _delete(os.path.join(ROOT, name))

    n += _delete_glob("carousel-routine/temp/**")
    os.makedirs(os.path.join(ROOT, "carousel-routine", "temp"), exist_ok=True)

    archive = os.path.join(ROOT, "_archive", "legacy")
    os.makedirs(archive, exist_ok=True)

    legacy_scripts = [
        "generate_three_gktoday_posts.py",
        "validate_infographic.py",
        "extract_verified_facts.py",
        "generate_fable_carousel.py",
        "generate_branded_carousel.py",
        "gen_brandstory_carousel.py",
        "gen_perf_carousel_614.py",
        "gen_carousels.py",
        "build_carousel.py",
        "build_carousel_today.cjs",
        "build_carousel_core.cjs",
        "generate_infographic_today.py",
        "cap_infographic_today.cjs",
        "cap_infographic.cjs",
        "generate_instagram_posts_old.py",
    ]
    for name in legacy_scripts:
        src = os.path.join(ROOT, name)
        if os.path.exists(src):
            dst = os.path.join(archive, name)
            try:
                shutil.move(src, dst)
                print(f"  archived: {name}")
                n += 1
            except Exception as e:
                print(f"  skip archive {name}: {e}")
                n += 1

    print(f"[cleanup] Legacy purge done ({n} items).")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clean up pipeline temp files")
    parser.add_argument(
        "--stage",
        choices=["after_generate", "after_slack", "after_publish", "legacy"],
        default="after_generate",
    )
    parser.add_argument(
        "--include-pngs",
        "--include-media",
        action="store_true",
        help="Also delete output PNGs/MP4s",
    )
    args = parser.parse_args()

    if args.stage in ("after_generate", "after_slack"):
        cleanup_after_generate(include_media=args.include_pngs)
    elif args.stage == "after_publish":
        cleanup_after_publish()
    elif args.stage == "legacy":
        cleanup_legacy()


if __name__ == "__main__":
    main()

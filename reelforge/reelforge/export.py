"""Packages finished carousels for hand-scheduling in the Instagram app.

This is the no-Facebook path: Instagram's own in-app scheduler takes carousels,
25 a day, up to 30 days ahead, with no Page, no developer app and no tokens.
You batch a month of posts onto your phone in one sitting.
"""
import re
import shutil
from datetime import datetime

from . import store
from .config import ROOT

EXPORT_DIR = ROOT / "export"


def _slug(text, limit=40):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].rstrip("-")


def caption_text(post):
    tags = " ".join(f"#{t.lstrip('#')}" for t in post.get("hashtags", []))
    return f"{post['caption']}\n\n{tags}".strip()


def run(cfg, count=None, status="rendered"):
    posts = store.by_status(status)
    if not posts:
        raise SystemExit(
            f"No posts with status '{status}'. Run: python -m reelforge run -n 7"
        )
    posts = list(reversed(posts))  # oldest first, so the order reads naturally
    if count:
        posts = posts[:count]

    stamp = datetime.now().strftime("%Y-%m-%d")
    batch_dir = EXPORT_DIR / stamp
    if batch_dir.exists():
        shutil.rmtree(batch_dir)
    batch_dir.mkdir(parents=True)

    index = [
        f"ReelForge batch — {stamp}",
        f"{len(posts)} carousels",
        "",
        "HOW TO SCHEDULE (no Facebook needed):",
        "  1. Put this folder on your phone (AirDrop, Google Drive, cable, whatever).",
        "  2. Instagram app -> + -> Post -> select ALL slides of one folder IN ORDER.",
        "  3. On the caption screen, paste that folder's caption.txt.",
        "  4. Tap 'Advanced settings' -> 'Schedule this post' -> pick a date and time.",
        "  5. Repeat. Instagram allows 25 scheduled posts/day, up to 30 days ahead.",
        "",
        "Slide order matters — 01 is the hook, the last one is the call to action.",
        "",
        "-" * 60,
        "",
    ]

    for i, post in enumerate(posts, 1):
        folder = batch_dir / f"{i:02d}-{_slug(post['hook'])}"
        folder.mkdir()
        slides = sorted(
            p for p in (ROOT / "out" / post["id"]).glob("*.png") if "_v" not in p.name
        )
        for slide in slides:
            shutil.copy2(slide, folder / slide.name)
        (folder / "caption.txt").write_text(caption_text(post), encoding="utf-8")

        index.append(f"{i:02d}. {post['hook']}")
        index.append(f"    {len(slides)} slides · theme {post['theme']} · folder {folder.name}")
        index.append("")

        post["status"] = "exported"
        post["exported_at"] = stamp
        store.save(post)

    (batch_dir / "READ-ME-FIRST.txt").write_text("\n".join(index), encoding="utf-8")

    print(f"\nExported {len(posts)} carousels to:\n  {batch_dir}\n")
    print("Each folder has its slides in order plus caption.txt.")
    print("READ-ME-FIRST.txt explains the scheduling steps.")
    print("\nCopy the folder to your phone and schedule them in the Instagram app.")
    return batch_dir

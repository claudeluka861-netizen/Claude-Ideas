"""Turns a post JSON into finished PNG slides using headless Chromium.

No image generator, no API, no cost — the slides are HTML rendered locally.
"""
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import store
from .config import OUT_DIR

TEMPLATE = Path(__file__).parent / "templates" / "slide.html"

# Playwright normally downloads its own Chromium. If the machine already has one
# (or the download is blocked), point CHROMIUM_PATH at it.
CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH")


def _slides_for(post, cfg):
    """Expand a post into the ordered list of slide payloads."""
    brand = cfg["brand"]
    kicker = cfg["niche"]["name"]
    total = len(post["slides"]) + 2
    payloads = [
        {
            "kind": "hook",
            "hook": post["hook"],
            "subhook": post.get("subhook", ""),
            "kicker": kicker,
            "handle": brand["handle"],
            "theme": post["theme"],
            "index": 0,
            "total": total,
        }
    ]
    for i, slide in enumerate(post["slides"], start=1):
        payloads.append(
            {
                "kind": "item",
                "title": slide["title"],
                "body": slide["body"],
                "kicker": kicker,
                "handle": brand["handle"],
                "theme": post["theme"],
                "index": i,
                "total": total,
            }
        )
    payloads.append(
        {
            "kind": "cta",
            "title": brand["cta_line"],
            "body": brand["cta_sub"],
            "kicker": kicker,
            "handle": brand["handle"],
            "theme": post["theme"],
            "index": len(post["slides"]) + 1,
            "total": total,
        }
    )
    return payloads


def _launch(pw):
    if CHROMIUM_PATH:
        return pw.chromium.launch(executable_path=CHROMIUM_PATH, args=["--no-sandbox"])
    return pw.chromium.launch(args=["--no-sandbox"])


def render_post(post, cfg, browser=None):
    out_dir = OUT_DIR / post["id"]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    sizes = [(cfg["output"]["width"], cfg["output"]["height"], "")]
    if cfg["output"].get("also_vertical"):
        sizes.append((1080, 1920, "_v"))

    payloads = _slides_for(post, cfg)
    written = []

    def _run(brow):
        for width, height, suffix in sizes:
            page = brow.new_page(viewport={"width": width, "height": height})
            page.goto(TEMPLATE.as_uri())
            for i, payload in enumerate(payloads):
                page.evaluate("d => renderSlide(d)", payload)
                path = out_dir / f"{i + 1:02d}{suffix}.png"
                page.screenshot(path=str(path))
                if not suffix:
                    written.append(str(path))
            page.close()

    if browser is not None:
        _run(browser)
    else:
        with sync_playwright() as pw:
            brow = _launch(pw)
            _run(brow)
            brow.close()

    post["images"] = written
    post["out_dir"] = str(out_dir)
    if post.get("status") == "draft":
        post["status"] = "rendered"
    return store.save(post)


def render_all(cfg, posts):
    done = []
    with sync_playwright() as pw:
        browser = _launch(pw)
        for post in posts:
            done.append(render_post(post, cfg, browser=browser))
            print(f"  rendered {post['id']}  ({len(post['images'])} slides, {post['theme']})")
        browser.close()
    return done

"""Checks every prerequisite and says exactly what is missing and where to fix it.

The point is that you never have to guess why the daemon is not posting.
"""
import os
import shutil

import requests

OK, WARN, FAIL = "OK", "WARN", "FAIL"
MARKS = {OK: "  ok  ", WARN: " warn ", FAIL: " FAIL "}


def _check(name, fn):
    try:
        status, detail = fn()
    except Exception as exc:
        status, detail = FAIL, str(exc)[:160]
    print(f"[{MARKS[status]}] {name}\n         {detail}")
    return status


def _playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        return FAIL, "not installed — run: pip install -r requirements.txt"
    from playwright.sync_api import sync_playwright

    path = os.environ.get("CHROMIUM_PATH")
    with sync_playwright() as pw:
        try:
            browser = (
                pw.chromium.launch(executable_path=path, args=["--no-sandbox"])
                if path
                else pw.chromium.launch(args=["--no-sandbox"])
            )
            version = browser.version
            browser.close()
        except Exception as exc:
            return FAIL, (
                f"chromium will not start ({str(exc)[:90]}) — "
                "run: python -m playwright install chromium"
            )
    return OK, f"chromium {version}"


def _writer(cfg):
    provider = cfg["generate"]["provider"]
    if provider == "offline":
        return WARN, (
            "provider is 'offline' — reuses a small local bank and repeats. "
            "Set generate.provider: \"gemini\" in config.yaml for real content."
        )
    env_key = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
    key_name = env_key.get(provider)
    if not key_name:
        return FAIL, f"unknown provider '{provider}'"
    if not os.environ.get(key_name):
        where = {
            "GEMINI_API_KEY": "https://aistudio.google.com/apikey (free, no card)",
            "ANTHROPIC_API_KEY": "https://console.anthropic.com/settings/keys",
            "OPENAI_API_KEY": "https://platform.openai.com/api-keys",
        }[key_name]
        return FAIL, f"{key_name} missing from .env — get one at {where}"

    if provider == "gemini":
        resp = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            timeout=30,
        )
        if resp.status_code >= 400:
            return FAIL, f"Gemini rejected the key ({resp.status_code}) — check it in AI Studio"
        return OK, f"gemini key works, model {cfg['generate']['model']}"
    return OK, f"{provider} key present"


def _uploader(cfg):
    if not cfg["publish"]["enabled"]:
        return WARN, "publishing is off, so slides are not hosted anywhere yet"
    name = cfg["publish"]["uploader"]
    if name == "imgbb":
        if not os.environ.get("IMGBB_API_KEY"):
            return FAIL, "IMGBB_API_KEY missing from .env — free key at https://api.imgbb.com/"
        return OK, "imgbb key present"
    if name == "github":
        missing = [v for v in ("GITHUB_TOKEN", "GITHUB_IMAGE_REPO") if not os.environ.get(v)]
        if missing:
            return FAIL, f"missing from .env: {', '.join(missing)}"
        return OK, f"github uploader -> {os.environ['GITHUB_IMAGE_REPO']}"
    return FAIL, "publish.uploader is 'none' — nowhere to host slides, cannot auto-publish"


def _instagram(cfg):
    from . import auth, publish

    if not cfg["publish"]["enabled"]:
        return WARN, "publish.enabled is false — nothing will be posted"
    if not os.environ.get("IG_USER_ID") or not os.environ.get("IG_ACCESS_TOKEN"):
        return FAIL, (
            "IG_USER_ID / IG_ACCESS_TOKEN missing from .env. You need an Instagram "
            "Professional account, a linked Facebook Page, a Meta app, and the "
            "instagram_business_content_publish permission."
        )
    valid, seconds_left, message = auth.token_info()
    if not valid:
        return FAIL, f"token rejected by Meta: {message}"
    left, used, total = publish.quota_left()
    days = "no expiry" if seconds_left < 0 else f"{seconds_left / 86400:.0f} days left on token"
    return OK, f"connected. {used}/{total} posts used in last 24h, {left} available. {days}"


def _schedule(cfg):
    per_day = cfg["schedule"]["posts_per_day"]
    times = cfg["schedule"]["times"]
    if len(times) < per_day:
        return FAIL, (
            f"posts_per_day is {per_day} but only {len(times)} times are listed in "
            "schedule.times — add more slots in config.yaml"
        )
    note = ""
    if per_day > 5:
        note = "  (high volume — Meta throttles repetitive content, watch your reach)"
    return OK, f"{per_day}/day at {', '.join(times[:per_day])}{note}"


def _dry_run(cfg):
    if not cfg["publish"]["enabled"]:
        return WARN, "publish.enabled: false — run generates and renders only"
    if cfg["publish"].get("dry_run", True):
        return WARN, "dry_run: true — builds the post but stops before publishing. Set false to go live."
    return OK, "live — posts will actually go out"


def _service():
    from . import service

    installed, detail = service.status()
    if installed:
        return OK, detail
    return WARN, detail + "  (run: python -m reelforge service install)"


def run(cfg):
    print("\nReelForge check\n" + "-" * 60)
    results = [
        _check("Renderer (chromium)", _playwright),
        _check("Writer (content generation)", lambda: _writer(cfg)),
        _check("Image hosting", lambda: _uploader(cfg)),
        _check("Instagram connection", lambda: _instagram(cfg)),
        _check("Schedule", lambda: _schedule(cfg)),
        _check("Publish mode", lambda: _dry_run(cfg)),
        _check("Background service", _service),
    ]
    print("-" * 60)
    fails = results.count(FAIL)
    warns = results.count(WARN)
    if fails:
        print(f"{fails} blocking problem(s). Fix those and run this again.")
    elif warns:
        print(f"No blockers. {warns} thing(s) to be aware of above.")
    else:
        print("Everything is wired up. It will post on schedule.")
    return fails

"""Meta access tokens expire after ~60 days. For something that runs unattended
that is a silent death, so we check and refresh before it happens.
"""
import os
import re
import time
from pathlib import Path

import requests

from .config import ROOT

TIMEOUT = 60
GRAPH = "https://graph.facebook.com/v23.0"
REFRESH_WHEN_DAYS_LEFT = 10


def _write_env(key, value):
    """Persist a refreshed token back into .env so the next run picks it up."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")
        return
    text = env_path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(f"{key}={value}", text)
    else:
        text = text.rstrip("\n") + f"\n{key}={value}\n"
    env_path.write_text(text, encoding="utf-8")
    os.environ[key] = value


def token_info(token=None):
    """Ask Meta what it thinks of our token. Returns (valid, seconds_left, message)."""
    token = token or os.environ.get("IG_ACCESS_TOKEN")
    app_id = os.environ.get("IG_APP_ID")
    app_secret = os.environ.get("IG_APP_SECRET")
    if not token:
        return False, 0, "IG_ACCESS_TOKEN is not set"
    if not app_id or not app_secret:
        return True, -1, "IG_APP_ID/IG_APP_SECRET not set — cannot check or auto-refresh expiry"

    resp = requests.get(
        f"{GRAPH}/debug_token",
        params={"input_token": token, "access_token": f"{app_id}|{app_secret}"},
        timeout=TIMEOUT,
    )
    if resp.status_code >= 400:
        return False, 0, f"token check failed: {resp.text[:200]}"
    data = resp.json().get("data", {})
    if not data.get("is_valid"):
        return False, 0, data.get("error", {}).get("message", "token is not valid")
    expires_at = data.get("expires_at", 0)
    if expires_at == 0:
        return True, -1, "token does not expire"
    return True, int(expires_at - time.time()), "ok"


def refresh_if_needed(verbose=True):
    """Swap a long-lived token for a fresh one when it is close to expiring."""
    app_id = os.environ.get("IG_APP_ID")
    app_secret = os.environ.get("IG_APP_SECRET")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not (app_id and app_secret and token):
        return False

    valid, seconds_left, message = token_info(token)
    if not valid:
        if verbose:
            print(f"  token is invalid ({message}) — regenerate it in the Meta dashboard")
        return False
    if seconds_left < 0:
        return False
    days_left = seconds_left / 86400
    if days_left > REFRESH_WHEN_DAYS_LEFT:
        return False

    if verbose:
        print(f"  token expires in {days_left:.1f} days — refreshing")
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        },
        timeout=TIMEOUT,
    )
    if resp.status_code >= 400:
        if verbose:
            print(f"  refresh failed: {resp.text[:200]}")
        return False
    new_token = resp.json().get("access_token")
    if not new_token:
        return False
    _write_env("IG_ACCESS_TOKEN", new_token)
    if verbose:
        print("  token refreshed and saved to .env")
    return True

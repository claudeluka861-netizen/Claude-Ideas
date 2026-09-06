"""One-command Instagram hookup.

Meta's token flow is a three-step dance that is easy to get wrong by hand:
a short-lived token has to be exchanged for a long-lived one, then the Page
token pulled from that, then the Instagram account id resolved from the Page.
This does all of it and writes the result to .env.

Page tokens derived from a long-lived user token do not expire, which is what
you want for something that runs unattended.
"""
import os

import requests

from .auth import _write_env

GRAPH = "https://graph.facebook.com/v23.0"
TIMEOUT = 60


def _get(path, params):
    resp = requests.get(f"{GRAPH}/{path}", params=params, timeout=TIMEOUT)
    if resp.status_code >= 400:
        raise SystemExit(f"\nMeta rejected the request to /{path}:\n  {resp.text[:400]}")
    return resp.json()


def _ask(prompt, env_name):
    existing = os.environ.get(env_name)
    if existing:
        print(f"  using {env_name} from .env")
        return existing
    value = input(f"  {prompt}: ").strip()
    if not value:
        raise SystemExit(f"{env_name} is required.")
    return value


def run(cfg, short_token=None):
    print("\nConnecting ReelForge to Instagram")
    print("-" * 60)
    print("You need these from https://developers.facebook.com/apps -> your app:")
    print("  App ID and App Secret   (Settings -> Basic)")
    print("  A user access token     (Tools -> Graph API Explorer, 'Generate Access Token')")
    print("The token can be the short-lived one; it gets exchanged automatically.\n")

    app_id = _ask("App ID", "IG_APP_ID")
    app_secret = _ask("App Secret", "IG_APP_SECRET")
    if not short_token:
        short_token = input("  User access token: ").strip()
    if not short_token:
        raise SystemExit("A user access token is required.")

    print("\n1/3  exchanging for a long-lived token...")
    long_token = _get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
    )["access_token"]
    print("     done")

    print("2/3  finding your Facebook Pages...")
    pages = _get("me/accounts", {"access_token": long_token, "fields": "id,name,access_token"})
    entries = pages.get("data", [])
    if not entries:
        raise SystemExit(
            "     No Pages found on this account.\n"
            "     Instagram publishing needs a Facebook Page linked to your\n"
            "     Instagram Professional account. Create one, link it in the\n"
            "     Instagram app under Settings -> Account -> Sharing to other apps."
        )

    print("3/3  resolving the Instagram account on each Page...")
    found = []
    for page in entries:
        info = _get(
            page["id"],
            {"fields": "instagram_business_account,name", "access_token": long_token},
        )
        ig = info.get("instagram_business_account")
        if ig:
            found.append((page, ig["id"]))
            print(f"     {page['name']}  ->  instagram account {ig['id']}")
        else:
            print(f"     {page['name']}  ->  no Instagram account linked")

    if not found:
        raise SystemExit(
            "\n     None of your Pages has an Instagram Professional account linked.\n"
            "     In the Instagram app: Settings -> Account type and tools ->\n"
            "     Switch to professional account, then link the Page."
        )

    if len(found) == 1:
        page, ig_id = found[0]
    else:
        print("\n  Several Pages have Instagram accounts. Which one posts?")
        for i, (page, ig_id) in enumerate(found, 1):
            print(f"    {i}. {page['name']} ({ig_id})")
        choice = int(input("  number: ").strip())
        page, ig_id = found[choice - 1]

    # A Page token minted from a long-lived user token does not expire.
    _write_env("IG_APP_ID", app_id)
    _write_env("IG_APP_SECRET", app_secret)
    _write_env("IG_ACCESS_TOKEN", page["access_token"])
    _write_env("IG_USER_ID", ig_id)

    print("\n" + "-" * 60)
    print(f"Connected to '{page['name']}' -> Instagram {ig_id}")
    print("Saved IG_USER_ID, IG_ACCESS_TOKEN, IG_APP_ID and IG_APP_SECRET to .env")
    print("\nNext:  python -m reelforge doctor")

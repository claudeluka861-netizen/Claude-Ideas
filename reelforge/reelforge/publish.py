"""Publishes a rendered carousel to Instagram via the Graph API.

Requires, on Meta's side: an Instagram Professional account, a linked Facebook
Page, a Meta developer app, and the instagram_business_content_publish permission.
A carousel counts as ONE post against the daily publishing limit.
"""
import os
import time

import requests

from . import store, upload

TIMEOUT = 120
API_VERSION = os.environ.get("IG_API_VERSION", "v23.0")
BASE = f"https://graph.facebook.com/{API_VERSION}"


def _creds():
    user_id = os.environ.get("IG_USER_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not user_id or not token:
        raise SystemExit(
            "IG_USER_ID and IG_ACCESS_TOKEN must be set in reelforge/.env to publish."
        )
    return user_id, token


def _post(path, params):
    resp = requests.post(f"{BASE}/{path}", data=params, timeout=TIMEOUT)
    if resp.status_code >= 400:
        raise RuntimeError(f"Instagram API error on {path}: {resp.status_code} {resp.text[:400]}")
    return resp.json()


def quota_left():
    """How many more posts Instagram will accept in the current 24h window."""
    user_id, token = _creds()
    resp = requests.get(
        f"{BASE}/{user_id}/content_publishing_limit",
        params={"access_token": token, "fields": "quota_usage,config"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()["data"][0]
    used = data.get("quota_usage", 0)
    total = data.get("config", {}).get("quota_total", 50)
    return total - used, used, total


def caption_for(post):
    tags = " ".join(f"#{t.lstrip('#')}" for t in post.get("hashtags", []))
    return f"{post['caption']}\n\n{tags}".strip()


def publish_post(post, cfg):
    if not post.get("images"):
        raise SystemExit(f"{post['id']} has no rendered images — run render first.")

    dry = cfg["publish"].get("dry_run", True)
    user_id, token = _creds()

    print(f"  hosting {len(post['images'])} slides via {cfg['publish']['uploader']}...")
    urls = post.get("hosted_urls") or upload.upload(post["images"], cfg)
    post["hosted_urls"] = urls
    store.save(post)

    print("  creating carousel items...")
    children = []
    for url in urls:
        item = _post(
            f"{user_id}/media",
            {"image_url": url, "is_carousel_item": "true", "access_token": token},
        )
        children.append(item["id"])

    container = _post(
        f"{user_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption_for(post),
            "access_token": token,
        },
    )

    if dry:
        post["status"] = "approved"
        post["dry_run_container"] = container["id"]
        store.save(post)
        print(f"  DRY RUN — container {container['id']} built but not published.")
        print("  Set publish.dry_run: false in config.yaml to post for real.")
        return post

    # Meta needs a moment to finish assembling the container.
    time.sleep(5)
    result = _post(
        f"{user_id}/media_publish",
        {"creation_id": container["id"], "access_token": token},
    )
    post["status"] = "published"
    post["ig_media_id"] = result["id"]
    post["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    store.save(post)
    print(f"  published {post['id']} -> IG media {result['id']}")
    return post

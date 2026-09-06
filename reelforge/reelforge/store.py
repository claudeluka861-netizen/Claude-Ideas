"""Post files on disk are the whole database. One JSON per carousel."""
import json
from datetime import datetime, timezone

from .config import POSTS_DIR

# status: draft -> rendered -> approved -> published (or rejected)


def _path(post_id):
    return POSTS_DIR / f"{post_id}.json"


def save(post):
    post["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _path(post["id"]).write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
    return post


def get(post_id):
    path = _path(post_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def all_posts():
    posts = []
    for path in sorted(POSTS_DIR.glob("*.json")):
        try:
            posts.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return posts


def by_status(status):
    return [p for p in all_posts() if p.get("status") == status]


def recent_hooks(limit):
    """Hooks already used — fed back to the writer so it stops repeating itself."""
    return [p["hook"] for p in all_posts()[:limit] if p.get("hook")]


def next_id():
    stamp = datetime.now().strftime("%Y%m%d")
    n = 1
    while _path(f"{stamp}-{n:02d}").exists():
        n += 1
    return f"{stamp}-{n:02d}"

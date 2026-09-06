"""Instagram will not accept a local file — it fetches images from public URLs.
So every slide has to live somewhere reachable before we can publish.
"""
import base64
import os
from pathlib import Path

import requests

TIMEOUT = 120


def _imgbb(paths, cfg):
    key = os.environ.get("IMGBB_API_KEY")
    if not key:
        raise SystemExit(
            "IMGBB_API_KEY is not set in reelforge/.env — needed to host slides.\n"
            "Free key: https://api.imgbb.com/"
        )
    urls = []
    for path in paths:
        payload = base64.b64encode(Path(path).read_bytes())
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": key, "image": payload},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(f"imgbb rejected {path}: {body}")
        urls.append(body["data"]["url"])
    return urls


def _github(paths, cfg):
    """Commit slides to a public repo and serve them from raw.githubusercontent.com.
    Permanent and free, but the images are public in your git history forever."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_IMAGE_REPO")  # "owner/repo"
    branch = os.environ.get("GITHUB_IMAGE_BRANCH", "main")
    if not token or not repo:
        raise SystemExit(
            "GITHUB_TOKEN and GITHUB_IMAGE_REPO must be set in reelforge/.env "
            "to use the github uploader."
        )
    urls = []
    for path in paths:
        path = Path(path)
        dest = f"slides/{path.parent.name}/{path.name}"
        resp = requests.put(
            f"https://api.github.com/repos/{repo}/contents/{dest}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "message": f"slide {path.parent.name}/{path.name}",
                "content": base64.b64encode(path.read_bytes()).decode(),
                "branch": branch,
            },
            timeout=TIMEOUT,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"GitHub upload failed for {path}: {resp.status_code} {resp.text[:200]}")
        urls.append(f"https://raw.githubusercontent.com/{repo}/{branch}/{dest}")
    return urls


def _none(paths, cfg):
    raise SystemExit(
        "publish.uploader is 'none' — there is nowhere to host the slides, so they "
        "cannot be published automatically. Set it to 'imgbb' or 'github', or post by hand."
    )


UPLOADERS = {"imgbb": _imgbb, "github": _github, "none": _none}


def upload(paths, cfg):
    name = cfg["publish"]["uploader"]
    if name not in UPLOADERS:
        raise SystemExit(f"Unknown publish.uploader '{name}' in config.yaml")
    return UPLOADERS[name](paths, cfg)

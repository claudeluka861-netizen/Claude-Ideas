import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
OUT_DIR = ROOT / "out"


def _load_env():
    """Read .env into os.environ without adding a dependency."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def load(path=None):
    _load_env()
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    POSTS_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)
    return cfg


def require_env(name, why):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing {name} in reelforge/.env — needed to {why}.\n"
            f"Copy .env.example to .env and fill it in."
        )
    return value

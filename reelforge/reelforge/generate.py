"""Writes carousel copy. Provider-agnostic: gemini | anthropic | openai | offline."""
import json
import os
import random
import re
from datetime import datetime, timezone

import requests

from . import store
from .config import require_env

TIMEOUT = 90

SCHEMA_HINT = """Respond with ONLY a raw JSON object. No markdown fences, no preamble.
{
  "hook": "the slide-1 title. 4-9 words. Specific and concrete.",
  "subhook": "one short line under the hook, under 8 words",
  "slides": [
    {"title": "3-7 words, the point itself", "body": "1-2 sentences, under 30 words, concrete and useful"}
  ],
  "caption": "2-4 sentences for the Instagram caption. Plain, no hashtags here, ends with a question.",
  "hashtags": ["8-12 lowercase hashtags, no # symbol, mix broad and specific"]
}"""


def build_prompt(cfg, slide_count, avoid):
    niche = cfg["niche"]
    guardrails = "\n".join(f"- {g}" for g in niche.get("guardrails", []))
    avoid_block = ""
    if avoid:
        listed = "\n".join(f"- {h}" for h in avoid)
        avoid_block = (
            "\nThese hooks have already been posted. Do not reuse them, reword them, "
            f"or write anything that lands on the same idea:\n{listed}\n"
        )
    return f"""You write swipeable Instagram carousels for an account in this niche:

NICHE: {niche['name']}
AUDIENCE: {niche['audience']}
VOICE: {niche['voice']}

HARD RULES:
{guardrails}
- Slide 1 is the hook and does 90% of the work. It must promise something specific.
- Write exactly {slide_count} entries in "slides". Each one must stand alone.
- If the hook starts with a number, that number MUST be {slide_count}. Never promise
  more items than you write.
- Every slide must contain real information. No filler, no "believe in yourself".
- Do not number the slides yourself.
{avoid_block}
{SCHEMA_HINT}"""


def _extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model reply: {text[:200]}")
    return json.loads(text[start : end + 1])


def _call_gemini(cfg, prompt):
    key = require_env("GEMINI_API_KEY", "write carousel copy with Gemini")
    model = cfg["generate"]["model"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = requests.post(
        url,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_anthropic(cfg, prompt):
    key = require_env("ANTHROPIC_API_KEY", "write carousel copy with Claude")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": cfg["generate"]["model"],
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return "".join(b.get("text", "") for b in resp.json()["content"])


def _call_openai(cfg, prompt):
    key = require_env("OPENAI_API_KEY", "write carousel copy with OpenAI")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": cfg["generate"]["model"],
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_offline(cfg, prompt, slide_count):
    """No API key. Assembles a real carousel from a local bank so you can see the
    pipeline end to end. Repeats quickly — this is for testing, not for posting daily."""
    bank_path = os.path.join(os.path.dirname(__file__), "seed_content.json")
    with open(bank_path, encoding="utf-8") as fh:
        bank = json.load(fh)
    used = set(store.recent_hooks(len(bank)))
    unused = [p for p in bank if p["hook"] not in used]
    post = random.choice(unused or bank)
    post = json.loads(json.dumps(post))
    post["slides"] = post["slides"][:slide_count]
    return json.dumps(post)


PROVIDERS = {
    "gemini": _call_gemini,
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}


def generate_one(cfg):
    slide_count = cfg["output"]["slides_per_post"] - 2  # minus hook and CTA
    avoid = store.recent_hooks(cfg["generate"]["avoid_last"])
    prompt = build_prompt(cfg, slide_count, avoid)
    provider = cfg["generate"]["provider"]

    if provider == "offline":
        raw = _call_offline(cfg, prompt, slide_count)
    else:
        if provider not in PROVIDERS:
            raise SystemExit(f"Unknown generate.provider '{provider}' in config.yaml")
        raw = PROVIDERS[provider](cfg, prompt)

    data = _extract_json(raw)
    for field in ("hook", "slides", "caption"):
        if not data.get(field):
            raise ValueError(f"Model reply missing '{field}'")
    data["slides"] = data["slides"][:slide_count]

    post = {
        "id": store.next_id(),
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "theme": random.choice(cfg["themes"]),
        "hook": data["hook"],
        "subhook": data.get("subhook", ""),
        "slides": data["slides"],
        "caption": data["caption"],
        "hashtags": data.get("hashtags", []),
        "images": [],
        "provider": provider,
    }
    return store.save(post)


def generate(cfg, count):
    made = []
    for i in range(count):
        try:
            post = generate_one(cfg)
            made.append(post)
            print(f"  drafted {post['id']}  {post['hook']}")
        except Exception as exc:  # keep going; one bad reply shouldn't kill the batch
            print(f"  [{i + 1}/{count}] failed: {exc}")
    return made

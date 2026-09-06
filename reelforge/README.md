# ReelForge

Writes, renders and posts swipeable Instagram carousels on a schedule, from your own machine.

One command makes a finished post: a hook slide, five content slides, a call-to-action
slide, a caption and hashtags — as real PNG files, ready to publish.

**The slides are not AI-generated images.** They are HTML rendered by a headless browser
on your machine. That part is free, offline, and instant. The only thing that needs an AI
is the *writing*, and that runs on a free API tier.

---

## Quick start — 5 minutes, no accounts, no keys

```bash
cd reelforge
pip install -r requirements.txt
python -m playwright install chromium     # one-time, ~150MB

python -m reelforge run -n 3              # uses the built-in offline content bank
python -m reelforge review                # open http://127.0.0.1:8765
```

You now have three finished carousels in `out/`, and a local site to look through them.
Nothing has been posted anywhere. This mode reuses a small bank of hand-written posts, so
it repeats after three — it exists to prove the pipeline works before you wire anything up.

---

## Step 2 — real writing, still free

Get a Gemini API key at <https://aistudio.google.com/apikey>. No credit card.

```bash
cp .env.example .env
# put the key in GEMINI_API_KEY
```

Then in `config.yaml` set `generate.provider: "gemini"`.

The free tier allows roughly 250 requests/day on `gemini-2.5-flash` and 1,000/day on
`gemini-2.5-flash-lite`. One carousel is one request, so ten posts a day uses ten of them.
Google has cut these limits before without notice — check your current quota in AI Studio
if generation starts failing.

Each request is sent the hooks from your last 40 posts with instructions not to repeat
them, which is what stops the account turning into the same post forty times.

---

## Step 3 — automatic posting to Instagram

This is the part with real setup, and none of it can be done from here — it all happens in
your Meta account.

**What Instagram requires**

1. Your Instagram account converted to **Professional** (Business or Creator).
2. A **Facebook Page** linked to it.
3. A **Meta developer app** at <https://developers.facebook.com>.
4. The **`instagram_business_content_publish`** permission approved on that app.
5. A long-lived access token.

Put the token and your numeric Instagram user id into `.env` as `IG_ACCESS_TOKEN` and
`IG_USER_ID`.

**Where the images live.** Instagram does not accept file uploads — it fetches each slide
from a public URL. So slides must be hosted somewhere first. Two options are built in:

- `imgbb` — free API key from <https://api.imgbb.com/>. Easiest.
- `github` — commits slides to a public repo and serves them from `raw.githubusercontent.com`.
  Permanent and free, but every slide is public in that repo's history forever.

Set which one in `config.yaml` under `publish.uploader`.

**Turning it on.** In `config.yaml`:

```yaml
publish:
  enabled: true
  dry_run: true     # leave true for the first run
```

With `dry_run: true` the tool does everything — hosts the images, builds the carousel
container through the API — and stops just before the publish call. When that run is clean,
set `dry_run: false`.

A carousel counts as **one** post against Instagram's limit of 50–100 published posts per
rolling 24 hours, so 5–10/day is well inside it. Check your live number any time with
`python -m reelforge status`.

---

## Running it while you sleep

```bash
python -m reelforge daemon
```

Reads `schedule.times` from `config.yaml` and, at each slot, generates one carousel,
renders it, and publishes it. Leave the terminal open. To survive reboots, wrap it in a
`systemd` unit (Linux), a LaunchAgent (macOS), or Task Scheduler (Windows).

---

## Commands

| Command | What it does |
|---|---|
| `run -n 3` | generate + render (+ publish if enabled) |
| `generate -n 5` | write carousels only |
| `render` | turn drafts into PNGs |
| `review` | local site at `127.0.0.1:8765` to approve/reject/publish |
| `publish --id 20260906-01` | publish one post |
| `status` | what is on disk, plus your live Instagram quota |
| `daemon` | run on the schedule |

## Layout

```
config.yaml     niche, brand, schedule, volume — edit this first
.env            API keys — never commit this
posts/          one JSON per carousel; this is the database
out/<id>/       01.png … 07.png (4:5) and 01_v.png … (9:16 for TikTok/Stories)
```

## Changing the look

`reelforge/templates/slide.html` holds all four themes (`midnight`, `paper`, `forest`,
`ink`) as CSS variables at the top. Change the colours there and everything re-renders.
Fonts are bundled in `templates/fonts/`, so rendering works with no internet.

## TikTok

Not automated, on purpose. TikTok's Content Posting API restricts unaudited apps to
`SELF_ONLY` (private) posts, requires the account itself to be private at post time, and
caps it at 5 users per 24h. Going public needs a full app audit with a demo video. The
tool writes 9:16 copies of every slide to `out/<id>/*_v.png` — upload those by hand.

## Things worth knowing before you scale up

- **Volume is a real risk.** Meta throttles reach on accounts posting repetitive,
  templated, unoriginal content. The config ships at 3/day deliberately. Raise it once you
  have watched your reach hold for a week or two, not on day one.
- **Never automate Instagram through an unofficial library.** Tools that log in as you and
  click buttons violate the Terms of Service and get accounts banned. This uses the
  official API only.
- **The writer can be wrong.** It is told not to invent statistics, revenue figures or
  testimonials, and the prompt enforces that. It is not a guarantee. Read the slides in
  `review` before they go out — that is what the approve button is for.
- **Followers are not customers.** A big account in a niche that does not match what you
  sell converts badly. The niche in `config.yaml` should be the niche your product serves.

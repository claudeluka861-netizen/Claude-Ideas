# ReelForge

Writes, renders and posts swipeable Instagram carousels on a schedule, unattended,
from your own machine.

One command makes a finished post: a hook slide, five content slides, a call-to-action
slide, a caption and hashtags — real PNG files, ready to publish. Installed as a
background service, it keeps doing that while you sleep.

**The slides are not AI-generated images.** They are HTML rendered by a headless browser
on your machine — free, offline, instant. The only thing that needs an AI is the
*writing*, and that runs on a free API tier.

---

## 1. Five minutes, no accounts, no keys

```bash
cd reelforge
pip install -r requirements.txt
python -m playwright install chromium     # one-time, ~150MB

python -m reelforge run -n 3              # 3 finished carousels
python -m reelforge review                # look at them: http://127.0.0.1:8765
```

Nothing was posted anywhere. This uses a built-in bank of seven hand-written carousels,
so it repeats after seven — it exists to prove the machine works before you wire anything
up.

**`python -m reelforge doctor` is the command to remember.** It checks every prerequisite
and tells you exactly what is missing and where to fix it. Run it whenever something
seems wrong.

---

## 2. Real writing — still free

Get a Gemini key at <https://aistudio.google.com/apikey>. No credit card.

```bash
cp .env.example .env      # put the key in GEMINI_API_KEY
```

Then set `generate.provider: "gemini"` in `config.yaml`.

The free tier is roughly 250 requests/day on `gemini-2.5-flash`, 1,000/day on
`gemini-2.5-flash-lite`. One carousel is one request, so even ten posts a day uses ten.
Google has cut these limits before without warning — if generation starts failing, check
your quota in AI Studio.

Each request carries the hooks from your last 40 posts with instructions not to repeat
them. That is what stops the account becoming the same post forty times.

---

## 3a. Posting WITHOUT Facebook (recommended if the Meta path fails)

Instagram's own in-app scheduler takes carousels, 25 a day, up to 30 days ahead — with
no Facebook Page, no developer app, no tokens, and since March 2026 no Professional mode
either. It is free and it is the shortest route to actually posting.

```bash
python -m reelforge run -n 30      # a month of content in one go
python -m reelforge export         # packaged, ready for your phone
```

That writes `export/<date>/` with one folder per carousel — slides numbered in order, a
`caption.txt` beside them, and a `READ-ME-FIRST.txt` with the scheduling steps. Copy it to
your phone, then in Instagram: **+ → Post → select all slides in order → paste the caption
→ Advanced settings → Schedule this post**.

Roughly fifteen minutes of tapping buys you a month of posts. No Meta developer account is
involved at any point.

---

## 3b. Fully automatic posting via the API

This part needs setup in your Meta account, and it is the one thing that cannot be
scripted — Meta requires a real person in a browser.

1. Convert your Instagram account to **Professional** (Business or Creator).
2. Link a **Facebook Page** to it.
3. Create an app at <https://developers.facebook.com>.
4. Get the **`instagram_business_content_publish`** permission approved on it.
5. Generate a long-lived access token.

Fill in `.env`: `IG_USER_ID`, `IG_ACCESS_TOKEN`, and — importantly — `IG_APP_ID` and
`IG_APP_SECRET`. Those last two let the tool refresh its own token. Without them, posting
silently stops after about 60 days when the token expires.

**Where slides live.** Instagram does not accept uploads; it fetches each slide from a
public URL. Two hosts are built in:

- `imgbb` — free key at <https://api.imgbb.com/>. Easiest.
- `github` — commits slides to a public repo, serves from `raw.githubusercontent.com`.
  Free and permanent, but the images live in that repo's history forever.

Then in `config.yaml`:

```yaml
publish:
  enabled: true
  dry_run: true     # leave true for the first run
```

`dry_run: true` does everything — hosts the images, builds the carousel through the API —
and stops one call short of publishing. When a run comes back clean, set it to `false`.

A carousel counts as **one** post against Instagram's 50–100 per rolling 24 hours, so
5–10/day sits well inside the limit. `python -m reelforge status` shows your live number.

---

## 4. Making it run while you sleep

```bash
python -m reelforge service install
```

Detects your OS and installs a real background service — systemd on Linux, a LaunchAgent
on macOS, a Scheduled Task on Windows. It starts on boot, restarts if it crashes, and
writes to `reelforge.log`.

It runs `doctor` first and refuses to install while anything is broken, so you cannot
accidentally leave a dead service running overnight.

```bash
python -m reelforge service status
python -m reelforge service uninstall
```

The daemon is built to survive being left alone: every slot is wrapped so one failure
cannot kill the loop, generation retries three times with backoff, the Meta token is
refreshed automatically, and it stops early if Instagram's daily quota is used up.

**Volume.** `config.yaml` ships at 3 posts/day with ten time slots already listed, so
raising `posts_per_day` to 10 needs no other edit. Meta throttles reach on repetitive
templated content — 3/day is a deliberate starting point, not a limit. Raise it once you
have watched your reach hold.

---

## Commands

| Command | What it does |
|---|---|
| `doctor` | check everything is wired up; says exactly what is missing |
| `run -n 3` | generate + render (+ publish if enabled) |
| `export -n 30` | package carousels for hand-scheduling — the no-Facebook route |
| `generate -n 5` | write carousels only |
| `render` | turn drafts into PNGs |
| `review` | local site at `127.0.0.1:8765` to approve/reject/publish |
| `publish --id 20260906-01` | publish one post |
| `status` | what is on disk, live Instagram quota, service state |
| `service install\|status\|uninstall` | manage the background service |
| `daemon` | the scheduled loop (normally run by the service) |

## Layout

```
config.yaml     niche, brand, schedule, volume — edit this first
export/<date>/  batches packaged for phone scheduling
.env            API keys and tokens — never commit this
posts/          one JSON per carousel; this is the database
out/<id>/       01.png … 07.png (4:5) and 01_v.png … (9:16 for TikTok/Stories)
reelforge.log   what happened while you were asleep
```

## Changing the look

`reelforge/templates/slide.html` holds all four themes (`midnight`, `paper`, `forest`,
`ink`) as CSS variables at the top. Change the colours and everything re-renders. Fonts
are bundled in `templates/fonts/`, so rendering never needs the internet.

## TikTok

Not automated, deliberately. TikTok restricts unaudited apps to `SELF_ONLY` (private)
posts, requires the account itself to be private at post time, and caps it at 5 users per
24h. Public posting needs a full app audit with a demo video. Every slide is also written
as a 9:16 copy at `out/<id>/*_v.png` — upload those by hand.

## Worth knowing

- **Never use an unofficial Instagram automation library.** Anything that logs in as you
  and clicks buttons breaks the Terms of Service and gets accounts banned. This uses the
  official API only.
- **The writer can be wrong.** The prompt forbids invented statistics, revenue figures and
  testimonials. That is not a guarantee. The `review` site and its approve button exist
  for the days you want to read before posting.
- **Followers are not customers.** The niche in `config.yaml` should be the niche your
  product actually serves, or the audience will not convert.

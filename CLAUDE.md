# Claude-Ideas

## Working agreement

**Always end with what's next — including the parts that are mine to do.**

Every time Claude finishes a piece of work, the reply ends with a `Your move` section:

- the next concrete action, even when it belongs to me and not to Claude
- roughly how long it takes
- what it unblocks

Never stop at "done" and wait to be asked. If the next step is mine, say so plainly and
make it mechanical: exact click paths, exact URLs, exact values to paste. If a step is
blocked, say what it is blocked on and what the alternative is.

If several things could come next, recommend one and say why, rather than listing options
and waiting.

### What Claude cannot do for me

Recorded so it does not get re-argued each session:

- **Meta / Instagram account setup.** Converting to a Professional account, linking a
  Facebook Page, creating the developer app, and getting
  `instagram_business_content_publish` approved all require my login, my 2FA, and Meta's
  identity verification against my real identity. Claude cannot and should not operate
  that. There is no Cowork environment on this account either (only `Default`), so a
  browser session is not an option.
- **Posting to Instagram by logging in as me.** Any tool that does this violates the
  Terms of Service and gets accounts banned. Official API only.
- **Anything needing network beyond GitHub and package registries** in Claude Code on the
  web — this environment's egress policy blocks everything else at the proxy.

What Claude *can* do is reduce my part to copy-paste steps, and check my work afterwards
with `python -m reelforge doctor`.

---

## What is in here

| Path | What it is | State |
|---|---|---|
| `reelforge/` | Instagram carousel factory — writes, renders and publishes posts on a schedule | Works. Not yet connected to a real account. |
| `idea-engine-3.html` | Business-idea generator SaaS prototype | **Broken.** Calls the Anthropic API with no auth header; 401s for everyone. Needs a backend proxy before it can be a bio link. |

### ReelForge in one paragraph

Generates carousel copy with a free-tier LLM, renders it to PNG slides with headless
Chromium (no image generator, no cost), and publishes them to Instagram through the
official Graph API. `doctor` checks every prerequisite and names the fix. `service
install` runs it as a background service so it posts unattended. Full setup in
`reelforge/README.md`.

Ships deliberately conservative: 3 posts/day, publishing disabled, offline content bank,
so it runs end to end before any account exists.

---

## Where things stand

**Done and pushed:** the whole content machine. Generation, rendering, review site,
publisher, token auto-refresh, background service, prerequisite checker.

**Blocked on me:**

1. Gemini API key → `.env`, set `generate.provider: "gemini"` (2 min, free)
2. Set `brand.handle` in `reelforge/config.yaml` — still says `@yourhandle`
3. Instagram Professional + Facebook Page (~20 min)
4. Meta app, then `python -m reelforge connect` (~15 min). **App Review is not
   needed** — it only applies to apps serving other people's accounts. Posting to my
   own account needs Standard Access, which is immediate. Full walkthrough in
   `reelforge/SETUP-INSTAGRAM.md`.
5. imgbb key → `.env` (2 min, free)
6. `dry_run: true` test → `dry_run: false` → `service install`

**Known gap:** every CTA slide says "Link in bio" and there is nothing to link to. The
funnel ends at a broken local HTML file. Fixing `idea-engine-3.html` — a Cloudflare Worker
holding the API key, rate limiting, a real URL, an email capture field — is the outstanding
piece of work.

---

## Conventions

- Branch: `claude/instagram-reel-review-c3sgjr`. Commit and push finished work.
- Never commit `.env`, `posts/*.json`, `out/*`, or `reelforge.log`.
- Content rule for anything the account posts: no invented statistics, revenue figures or
  testimonials. The generator prompt enforces this; it is not a guarantee, which is what
  the review site is for.

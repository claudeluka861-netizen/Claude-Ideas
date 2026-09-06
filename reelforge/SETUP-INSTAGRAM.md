# Connecting ReelForge to Instagram

Everything here happens in your browser, in your account. It cannot be scripted or
delegated — Meta verifies a real person. The goal of this document is to make it
mechanical.

**Good news first: you almost certainly do not need Meta App Review.** App Review (the
2–4 week queue) is for apps that serve *other people's* accounts. You are only posting to
your own, which needs Standard Access and nothing more.

---

## 1. Instagram → Professional  (5 min)

Instagram app → **Settings and privacy** → **Account type and tools** →
**Switch to professional account**. Pick Creator or Business; either works.

## 2. Facebook Page, linked  (10 min)

Create a Page at <https://www.facebook.com/pages/create> if you do not have one.

Link it: Instagram app → **Settings** → **Account type and tools** → **Sharing to other
apps** (or **Linked accounts**) → connect the Page.

Publishing does not work without this. Instagram's publishing API is reached *through* the
Page.

## 3. Meta app  (10 min)

<https://developers.facebook.com/apps> → **Create App** → use case **Other** → type
**Business** → name it anything.

In the app: **Add product** → **Instagram** → **Set up**.

Then **App settings → Basic** and note your **App ID** and **App Secret**.

## 4. Decide: Tester role, or take the app Live

Two paths. Which one you need depends on whether your Instagram account sits inside the
same Meta Business that owns the app.

**Path A — Instagram Tester (app stays in Development mode)**

App dashboard → **App roles** → **Roles** → add your Instagram account as an
**Instagram Tester**. Accept the invite in Instagram under **Settings → Apps and
websites → Tester invites**.

**Path B — take the app Live** (do this if Path A fails with *"Unable to add a user with a
role on the app's owning business"* or *"Insufficient developer role"*)

**App settings → Basic** → set a **Privacy Policy URL** (required) and a **Category** →
Save. Then left nav → **Publish** → **Publish**, switching Development → Live.

Going Live is *not* App Review. It is a switch, and it is immediate. You just need a
privacy policy at a real URL — a single static page is fine.

## 5. Generate a token  (2 min)

<https://developers.facebook.com/tools/explorer/>

- **Meta App**: your app
- **User or Page**: User Token
- Add these permissions:
  - `instagram_basic`
  - `instagram_content_publish`
  - `pages_show_list`
  - `pages_read_engagement`
  - `business_management`
- **Generate Access Token**, approve the dialog, copy the token.

It is short-lived (one hour). That is fine — the next step exchanges it.

## 6. Hand it to ReelForge  (30 seconds)

```bash
cd reelforge
python -m reelforge connect
```

It asks for your App ID, App Secret and that token, then:

1. exchanges the short-lived token for a long-lived one,
2. finds your Pages and the Instagram account linked to each,
3. pulls the **Page access token** — which does not expire — and
4. writes `IG_USER_ID`, `IG_ACCESS_TOKEN`, `IG_APP_ID`, `IG_APP_SECRET` into `.env`.

## 7. Image hosting  (2 min)

Instagram fetches slides from public URLs rather than accepting uploads. Free key at
<https://api.imgbb.com/> → into `.env` as `IMGBB_API_KEY`.

## 8. Check, test, go live

```bash
python -m reelforge doctor        # every box should be green
```

In `config.yaml` set `publish.enabled: true`, leave `dry_run: true`, then:

```bash
python -m reelforge run -n 1      # does everything except the final publish call
```

Clean? Set `dry_run: false` and run it again — that one posts for real. Then:

```bash
python -m reelforge service install
```

---

## When it breaks

Run `python -m reelforge doctor` first; it names the failing piece and the fix.

| Symptom | Cause |
|---|---|
| "Insufficient developer role" | Path B above — take the app Live |
| No Pages found | Page is not linked to the Instagram account (step 2) |
| No Instagram account on the Page | account is still Personal, not Professional (step 1) |
| `(#10) requires instagram_content_publish` | permission missing on the token (step 5) |
| Token stops working after ~60 days | you used a User token instead of the Page token — re-run `connect` |

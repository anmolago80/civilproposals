# Blog — setup and how it works

Everything below is one-time setup. Nothing has been deployed; these are the
steps to switch it on.

> The one-shot script that performed this setup lives at
> `scripts/setup_blog.js` (run it from the repo root as
> `node scripts/setup_blog.js`). It has already been run — the KV namespace
> exists — and is kept as a record of how the blog infrastructure was
> created. The manual steps below are the authoritative description.

---

## How it fits together

```
   You, in the app                Cloudflare                    Readers
   ───────────────                ──────────                    ───────
   app.civilproposals.com
   sidebar → "Write / edit blog"
        │
        │  writes drafts to Postgres  (source of truth)
        │
        └── press Publish ──► POST /api/blog/*  ──► KV ──►  /blog/<slug>/
                              (shared secret)              served at the edge
```

Two separate stores, on purpose:

- **Postgres** holds drafts, markdown, images, scheduling — everything the
  editor touches. Only you ever read it.
- **Cloudflare KV** holds the finished HTML readers actually get. Nothing on
  the read path touches Railway, so the blog stays up and stays crawlable
  while the app is redeploying, asleep, or broken.

Publishing always re-renders and re-pushes *everything* rather than patching.
That means the live blog is exactly reproducible from the database, and a
publish that half-failed is fixed by pressing Publish again.

---

## One-time setup

### 1. Create the KV namespace

From the repo root:

```bash
npx wrangler kv namespace create BLOG
```

It prints an id. Paste it into **both** config files, replacing
`REPLACE_WITH_KV_NAMESPACE_ID`:

- `wrangler.toml` (repo root — this is the one real deploys use)
- `landing/wrangler.toml` (the copy for manual deploys from inside `landing/`)

Until this is done `wrangler deploy` fails with an unknown-namespace error.
That's deliberate: a Worker that deployed fine but silently had no KV binding
would 503 on every blog URL and take a while to diagnose.

### 2. Pick a publish secret and set it in both places

Generate one:

```bash
openssl rand -hex 32
```

Cloudflare side:

```bash
npx wrangler secret put BLOG_PUBLISH_SECRET
```

Railway side — add a variable with the **same value**:

```
BLOG_PUBLISH_SECRET = <the same hex string>
```

If they don't match, the Publish button returns a clear
"the site rejected the publish key" rather than failing silently.

Optional Railway variable, only if the site ever moves off
`civilproposals.com`:

```
BLOG_PUBLISH_URL = https://civilproposals.com/api/blog
SITE_ORIGIN      = https://civilproposals.com
```

### 3. Deploy

```bash
npx wrangler deploy          # Cloudflare — the Worker and the landing page
```

Railway redeploys itself from the repo as usual. `markdown>=3.6` has been
added to `app/requirements.txt`; it installs on the next build.

### 4. Write the first post

1. Log in at app.civilproposals.com with an admin account
   (`anmolago@hotmail.com` or `anmolago@icloud.com` — set in
   `auth.ADMIN_ACCOUNTS`).
2. Sidebar → **✍️ Write / edit blog**.
3. Posts tab → title → **Create draft**.
4. Write tab → excerpt, category, body → **Save draft**, then **Publish**.

The post appears at `civilproposals.com/blog/<slug>/`, in the `/blog/`
listing, in its category page, in the homepage strip and in the sitemap.

### 5. Tell Google it exists

- Add `civilproposals.com` as a property in Google Search Console.
- Submit `https://civilproposals.com/sitemap.xml`.

This is also what feeds the "which post should I improve next" data —
impressions, clicks, average position and the real search queries per URL.

### 6. Switch Plausible on (optional, currently inert)

`landing/index.html` has carried a Plausible script tag since before this
change, but the account was never created, so it collects nothing. Creating
`civilproposals.com` at plausible.io activates it for the landing page *and*
every blog post, with no code change. The free alternative is Cloudflare Web
Analytics (dashboard → Analytics & Logs → Web Analytics), also cookieless —
either keeps the Cookie Policy's "no analytics cookies" statement accurate.

---

## How posts are organised

| | |
|---|---|
| `/blog/` | listing, newest first |
| `/blog/<slug>/` | one post |
| `/blog/category/<slug>/` | category listing, only exists while a post uses it |
| `/blog/media/<key>` | an uploaded image |

**Categories** are a fixed list in `blog.CATEGORIES` — Tendering &
Compliance, Fee & Pricing, Bid Strategy, Product Updates. Fixed because
free-form categories reliably sprawl into fifteen near-duplicates and split
your internal linking. Tags stay free-form; sprawl there is harmless.

**States**: Draft (private) → Scheduled (goes live at its time) → Published →
Unpublished (pulled from the live site, text kept).

**Slugs are permanent.** The editor warns before you rename one that has
already been live, because the old URL starts 404ing and any search result
or inbound link pointing at it dies. Pick the phrase you want to rank for.

---

## Statistics

Three sources, deliberately:

1. **Built-in counter** (Stats tab in the editor) — the Worker counts every
   request that reaches Cloudflare, including from readers whose ad blocker
   blocks Plausible. It's a sharded read-modify-write against KV, so it can
   lose a few counts under sudden bursts — close, not exact.
2. **Plausible** — where readers came from and which CTAs they clicked. Every
   in-post CTA is tagged `plausible-event-position=blog-<slug>`, so you can
   see which posts actually drive signups rather than just traffic.
3. **Search Console** — impressions, clicks, position and queries per URL.
   The most useful of the three for deciding what to write next.

---

## Files

**New**

- `app/modules/blog.py` — storage, markdown rendering, page templates, publishing
- `app/modules/pages/15_admin_blog.py` — the editor UI

**Changed**

- `app/modules/db.py` — `BlogPost` + `BlogImage` tables (created automatically on next start)
- `app/modules/pages/_manifest.txt` — registers the new segment
- `app/modules/pages/20_chrome.py` — the sidebar button
- `app/requirements.txt` — `markdown>=3.6`
- `landing/_worker.js` — blog serving, publish API, homepage card injection, counters
- `landing/index.html` — blog strip, nav link, footer Resources column
- `landing/sitemap.xml` — now a fallback; the live one is generated
- `wrangler.toml`, `landing/wrangler.toml` — KV binding

---

## Rollback

The blog is additive. To disable it without reverting code: remove the
`[[kv_namespaces]]` block and redeploy — blog URLs then 503, the homepage
falls back to its placeholder text, and every existing page behaves exactly
as before. To remove it properly, revert the file list above; the two
database tables are harmless if left in place.

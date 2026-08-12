# Deploying CivilProposals

This covers steps 2, 7–10 of the original plan: pushing this code to GitHub,
connecting it to Railway (the app) and Cloudflare Pages (the landing page),
wiring up your `civilproposals.com` domain, and setting up Stripe pricing.

Folder layout in this delivery:

```
civilproposals/
├── app/          Streamlit app -- deploys to Railway, lives at app.civilproposals.com
├── landing/      One-page marketing site -- deploys to Cloudflare Pages, lives at civilproposals.com
└── DEPLOY.md     This file
```

---

## 1. Push to GitHub

One repo, two folders — simpler than two repos, and both Railway and
Cloudflare Pages can be told to deploy from a subfolder of the same repo.

```bash
cd civilproposals
git init
git add app landing DEPLOY.md
git commit -m "Initial CivilProposals SaaS build"
```

Create a new empty repo on GitHub (github.com → New repository → name it
`civilproposals`, don't initialize with a README), then:

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/civilproposals.git
git push -u origin main
```

---

## 2. Connect GitHub to Railway (the app)

1. railway.app → **New Project** → **Deploy from GitHub repo** → pick `civilproposals`.
2. Railway will try to build from the repo root — tell it to use the `app/`
   subfolder instead: in the new service's **Settings → Source**, set
   **Root Directory** to `app`.
3. Railway auto-detects Python via `requirements.txt` and uses the
   `Procfile` I included (`web: streamlit run app.py --server.port=$PORT
   --server.address=0.0.0.0`) to start it — no build config needed.
4. **Add a database**: in the same Railway project, **+ New** → **Database**
   → **PostgreSQL**. Railway automatically injects `DATABASE_URL` into your
   app service — you don't need to copy/paste it yourself.
5. **Set environment variables**: open the app service → **Variables** →
   add each of these (see `app/.env.example` for what each one is):
   - `SAAS_MODE=true`
   - `APP_SECRET_KEY` — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`
   - `APP_BASE_URL` — `https://app.civilproposals.com` (set this once DNS is connected in step 4; until then, Railway's own `*.up.railway.app` URL works)
   - `ANTHROPIC_API_KEY` — your Claude API key (this is the account that gets billed for every user's AI usage, since the plan bundles it)
   - `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` — from step 5 below
6. Railway auto-deploys on every push to `main` from here on — no manual redeploy step.

---

## 3. Connect GitHub to Cloudflare Pages (the landing page)

1. Cloudflare dashboard → **Workers & Pages** → **Create** → **Pages** →
   **Connect to Git** → pick `civilproposals`.
2. Build settings:
   - **Root directory**: `landing`
   - **Build command**: leave blank (it's static HTML, nothing to build)
   - **Build output directory**: `/` (or leave default)
3. Deploy. Cloudflare gives you a `*.pages.dev` URL immediately, and
   auto-redeploys on every push to `main`.

---

## 4. Connect your civilproposals.com domain

You already own the domain in Cloudflare, so DNS is in the same dashboard.

**Landing page (root domain → Cloudflare Pages):**
In the Pages project → **Custom domains** → **Set up a custom domain** →
enter `civilproposals.com`. Cloudflare adds the DNS record for you
automatically since the domain is already on your account — no manual CNAME needed.

**App (subdomain → Railway):**
1. In Railway, open the app service → **Settings → Networking → Custom
   Domain** → enter `app.civilproposals.com`. Railway shows you a CNAME
   target (something like `xyz.up.railway.app`).
2. In Cloudflare → your domain → **DNS** → **Add record**:
   - Type: `CNAME`
   - Name: `app`
   - Target: (the value Railway gave you)
   - Proxy status: **DNS only** (grey cloud, not orange) — Streamlit's
     websocket connection can be finicky through Cloudflare's proxy; if you
     later want the orange-cloud CDN/DDoS protection, test carefully first.
3. Update the `APP_BASE_URL` Railway variable to `https://app.civilproposals.com` and redeploy.

DNS changes usually propagate within a few minutes on Cloudflare, sometimes up to an hour.

---

## 5. Stripe pricing setup

1. Stripe dashboard → **Product catalog** → **Add product**.
   - Name: `CivilProposals Subscription`
   - Pricing: **Recurring**, `$200.00`, **Monthly**
2. Save, then open the product and copy the **Price ID** (starts with
   `price_`, *not* the Product ID which starts with `prod_`) — that's your
   `STRIPE_PRICE_ID`.
3. Developers → **API keys** → copy the **Secret key** (`sk_test_...` while
   testing, `sk_live_...` when you go live) — that's `STRIPE_SECRET_KEY`.
4. Paste both into Railway's Variables (step 2 above) and redeploy.
5. **To change the price later**: Stripe prices are immutable once created
   — you can't edit $200 into a different number on the same Price object.
   Create a *new* Price on the same product, copy its Price ID, update the
   `STRIPE_PRICE_ID` Railway variable, and redeploy. Existing subscribers
   keep paying their original price unless you separately migrate them —
   Stripe's dashboard has a guided flow for that if/when you need it.
6. Test the whole flow with [Stripe's test card `4242 4242 4242 4242`](https://docs.stripe.com/testing),
   any future expiry, any CVC, before flipping to the live key.

---

## 6. Background jobs (multi-user concurrency)

**Why this exists:** Streamlit runs every visitor's session as a thread
inside one shared Python process. Tender Analysis and Draft Generation are
this app's two slowest, heaviest operations (AI calls that can run tens of
seconds, with Draft Generation firing several in parallel) — running them
inline in the web process meant one customer's long analysis could
measurably slow down every *other* customer's concurrent session on the
same process. `app/modules/job_queue.py` moves that work into a separate
background worker process instead, using Redis + [RQ](https://python-rq.org/).

This is opt-in and safe to skip: until `REDIS_URL` is set on the app
service, both operations keep running exactly as they always have (inline,
synchronous, with the same progress bars). Nothing breaks if you deploy the
code change alone and add the worker later.

**Setup (two new pieces of infra, both in the same Railway project):**

1. **Add Redis**: in the `gentle-magic` project → **+ New** → **Database**
   → **Add Redis**. Railway provisions it and exposes a connection URL as
   that service's `REDIS_URL` variable.
2. **Share `REDIS_URL` with both the app and the worker**: open the
   `civilproposals` service → **Variables** → add `REDIS_URL` referencing
   the Redis service, e.g. `${{Redis.REDIS_URL}}` (Railway autocompletes
   this once Redis exists in the project). You'll set the same reference on
   the worker service below.
3. **Create the worker service**: **+ New** → **GitHub repo** → the same
   `civilproposals` repo again (a second service from the same source, like
   the app service already is). Configure it:
   - **Root Directory**: `app` (same as the main app service)
   - **Start command**: `python worker.py` (override the auto-detected
     Streamlit start command — this is *why* it has to be a second service
     rather than reusing the existing one: Railway runs one start command
     per service, and this needs its own)
   - **Variables**: `DATABASE_URL` referencing the same Postgres (e.g.
     `${{Postgres.DATABASE_URL}}`), `REDIS_URL` referencing the same Redis
     as step 2, **and `ANTHROPIC_API_KEY`** referencing the same key as the
     `civilproposals` app service (e.g. `${{civilproposals.ANTHROPIC_API_KEY}}`).
     This app is SaaS-hosted, not BYOK — every job runs against the one
     shared server-side Anthropic key, and that key is deliberately never
     part of the job payload sent to Redis (only a redacted placeholder is —
     see `modules/job_queue.py`'s docstring), so the worker process needs
     its own copy of the real key to actually fill it back in before making
     the AI call.
4. Deploy both. Check the worker service's **Deploy Logs** for `*** Listening
   on civilproposals...` — that confirms it connected to Redis and is ready
   to pick up jobs.

**Before trusting this with live customers**, please test it yourself end
to end (this was built and smoke-tested against a local Redis instance in
an isolated sandbox with synthetic jobs, not against your live Railway
Postgres/Redis or a real AI provider call — that combination can't be
verified from here):

- [ ] With the worker deployed and `REDIS_URL` set on the app service, run
      a real Tender Analysis and a real Draft Generation as a logged-in test
      user → confirm both complete and populate the same way they did before
- [ ] Watch the worker's Deploy Logs while that runs → confirm you see it
      pick up and finish the job (not silently idle)
- [ ] Open two browser sessions as two different test accounts, kick off a
      Draft Generation in one, and confirm the *other* session's UI stays
      fully responsive (this is the actual problem being solved — worth
      seeing it work, not just trusting the code)
- [ ] Temporarily stop the worker service and confirm a queued job surfaces
      a clear error after a few minutes rather than spinning forever (this
      exercises the "worker isn't running" failure path)
- [ ] Redeploy the app service with `REDIS_URL` intentionally left unset (or
      test this on a fresh clone before adding Redis) → confirm both
      operations still work exactly as before, inline — this is the fallback
      path a rollback would land on

**Everything NOT yet covered by this queue**, still running inline in the
main web process today: executive summary / team intro / project
experience intro drafting, CV library reading, discipline re-scanning,
benchmark research, and DOCX/PPTX document export (`export_docx.py`,
`org_chart_pptx.py`, `methodology_pptx.py`, `program_pptx.py`). These are
individually lighter than Tender Analysis/Draft Generation, but the same
`_run_job_or_inline` pattern in `app.py` extends to any of them the same
way if usage shows they need it too — worth revisiting once you can see
real concurrent usage patterns rather than guessing which of these actually
bites first.

**A lower-risk, complementary option** worth knowing about: Railway
supports running multiple **replicas** of the `civilproposals` service
(Service Settings → **Scale** → Regions/replicas), which spreads different
users' sessions across separate processes instead of one. It's a pure
infrastructure toggle (no code change, deployable immediately) and reduces
how often two heavy customers ever share a process at all. The tradeoff:
Streamlit keeps each session's in-memory state (uploads, drafts,
analysis — anything not yet in the "Recent projects" autosave) on
whichever replica that browser tab first connected to; if a user's
connection ever gets rerouted to a different replica mid-session (a
reconnect after a network blip, for instance), that in-memory state is
gone on the new replica and they'd need to reload their autosaved project.
Worth turning on alongside the job queue, not instead of it, and worth
watching for that specific symptom (an unexpected "your work disappeared"
report) if you do.

---

## Go-live checklist (steps 11–15 from the original plan)

- [ ] Landing page loads at civilproposals.com and the "Get Started" button reaches the app
- [ ] Sign up as a brand-new test user → confirm 3-proposal trial shows correctly
- [ ] Run a full proposal end to end on the trial → confirm it counts down correctly, and re-running the SAME project doesn't double-count
- [ ] Use up the trial → confirm the paywall/upgrade prompt appears and blocks further new proposals
- [ ] Click Upgrade → complete a **test-mode** Stripe payment → confirm access unlocks immediately on redirect
- [ ] Archive a proposal to the Library → confirm it only shows up for that user, not others (already covered by an automated check during development, but worth re-confirming live)
- [ ] Get your employment contract reviewed by an employment lawyer before using transportation-specific content live (flagged, not something I can do for you)
- [ ] Get your Terms of Service / disclaimer reviewed by a lawyer (can often be combined with the contract review above)
- [ ] Switch `STRIPE_SECRET_KEY` to the live key, do one real end-to-end test payment yourself, then share the link with your first 5–10 firms

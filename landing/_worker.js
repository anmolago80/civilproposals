// Worker entry point for the civilproposals.com Cloudflare project (see
// wrangler.toml: run_worker_first == true routes EVERY request here first;
// anything not matched below falls through to Cloudflare's static-asset
// serving via the ASSETS binding, per the [assets] config).
//
// Jobs:
//   1. www.civilproposals.com -> redirect (301) to the apex domain, so
//      links/backlinks/search-engine indexing all consolidate on one
//      canonical host instead of splitting signal across two. Only fires
//      if www is actually routed to this Worker in the first place (a DNS
//      question, not a code one) -- harmless no-op otherwise.
//   2. /app and /app/*  -> reverse-proxy to the Streamlit app on Railway,
//      so it WOULD live at civilproposals.com/app if that were the
//      canonical entry point. It is NOT: app.civilproposals.com is set up
//      as its own custom domain pointing straight at the same Railway
//      service (confirmed live), and every CTA on this site (index.html,
//      terms/privacy/cookie pages, the lead-capture confirmation email)
//      links to that subdomain, never to civilproposals.com/app. This
//      block is dead code from an earlier architecture that was never
//      removed -- kept only because it's inert (nothing links to
//      civilproposals.com/app, so it never actually runs) and there's a
//      small chance something external still has it bookmarked/linked; if
//      that risk is judged not worth carrying, this whole block plus
//      BACKEND_HOST below can be deleted with no effect on the live site.
//   3. POST /api/lead -> lead-capture form handler (see index.html's
//      #lead-form) -- validates the email, then sends a notification to
//      the team and a short confirmation to the person who signed up, both
//      via Resend. Requires RESEND_API_KEY (Worker secret -- `wrangler
//      secret put RESEND_API_KEY`, separate from the same-named Railway
//      variable, since this runs on Cloudflare not Railway) and
//      RESEND_FROM_EMAIL (plain var, can go in wrangler.toml [vars] or the
//      Cloudflare dashboard). LEAD_NOTIFY_EMAIL is optional, defaults to
//      hello@civilproposals.com.
//   4. /blog, /blog/* -> the marketing blog. Pages are finished HTML held
//      in the BLOG KV namespace, written by the Streamlit admin's blog
//      editor (app/modules/blog.py) through the authenticated /api/blog/*
//      endpoints below. Nothing on this read path touches Railway or
//      Postgres, so the blog keeps serving -- and stays crawlable -- while
//      the app is redeploying or down.
//   5. /  -> static index.html, but streamed through HTMLRewriter to splice
//      the current blog cards into <div id="blog-cards">. Lets a new post
//      appear on the homepage with no rebuild and no redeploy, while
//      keeping the cards in the server-rendered HTML where crawlers see
//      them (rather than fetching them client-side).
//   6. /es, /es/, /es/index.html -> the same blog-cards splice as above,
//      but serving the static index.es.html (Spanish homepage) instead.
//      /es/security.html, /es/privacy-policy.html, /es/terms-of-service.html,
//      /es/cookie-policy.html -> the matching static *.es.html file. These
//      give the hreflang="es" URLs (https://civilproposals.com/es/, .../es/
//      security.html, etc.) a real route rather than relying on the
//      .es.html filenames directly, mirroring how "/" already resolves to
//      a specific static file above -- the whole Spanish site now lives
//      under one /es/... URL scheme (Audit Round 2, Part 7).
//   7. The bare *.es.html paths (/index.es.html, /security.es.html,
//      /privacy-policy.es.html, /terms-of-service.es.html,
//      /cookie-policy.es.html) 301-redirect to their canonical /es/... form
//      above, instead of serving directly -- so the raw filename can't end
//      up indexed or linked as a second address for the same page (a
//      leftover from before the /es/ scheme existed; the static files
//      still have to exist under these names for Cloudflare's ASSETS
//      binding to find them, they just aren't the address anything should
//      point at any more).
//   8. /sitemap.xml -> the generated version from KV when one exists,
//      falling back to the static file before anything is published.
//   9. anything else that reaches this script anyway (shouldn't normally
//      happen given run_worker_first, but just in case) -> fall back to
//      serving it from static assets via the ASSETS binding.
//
// BACKEND_HOST is Railway's own *.up.railway.app service domain, NOT the
// app.civilproposals.com custom domain and NOT the CNAME target Railway
// gives you for that custom domain (that target hostname only answers
// correctly when the request's Host header is the custom domain itself --
// hitting it directly with its own name as Host returns a 404). The plain
// service domain always routes correctly on its own.
//
// If Railway's generated domain ever changes (e.g. the service is
// recreated), update BACKEND_HOST below to match -- Railway dashboard ->
// service -> Settings -> Networking -> Public Networking shows it, or
// `railway domain` from the CLI.
const BACKEND_HOST = "civilproposals-production.up.railway.app";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// EMAIL_RE only checks for "one @ and a dot, no whitespace" -- it does NOT
// exclude HTML-meaningful characters (<, >, &, ", '), so a submitted value
// like `<img src=x onerror=alert(1)>@x.com` still passes it and would
// otherwise land verbatim inside the notification email's HTML body below.
// Escape before interpolating into any HTML string this Worker builds.
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function sendResendEmail(env, { to, subject, html, headers }) {
  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from: env.RESEND_FROM_EMAIL, to: [to], subject, html, headers }),
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error(`Resend API error (${resp.status}): ${detail}`);
  }
}

// Best-effort per-IP rate limit using the Cache API, which (unlike KV or
// Durable Objects) needs no new Cloudflare resource provisioned -- every
// Worker already has access to caches.default. This is deliberately NOT a
// substitute for a real Cloudflare Rate Limiting Rule (dashboard -> the
// zone -> Security -> WAF -> Rate limiting rules, a few clicks, would
// enforce this far more reliably at the edge across every Cloudflare PoP)
// or a CAPTCHA/Turnstile challenge on the form itself -- both need
// dashboard access this code change doesn't have, and are the stronger
// fix; this just closes the gap in the meantime. Cache API entries are
// best-effort (not guaranteed to be visible from every colo instantly,
// can be evicted early under memory pressure) and CF-Connecting-IP is
// spoofable-adjacent for anyone behind the same NAT/VPN egress, so this
// raises the bar against a naive script hammering the endpoint -- it does
// not stop a determined, distributed abuser.
const LEAD_RATE_LIMIT_WINDOW_SECONDS = 60;

async function isRateLimited(request) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const cacheKey = new Request(`https://civilproposals-internal.invalid/lead-rate-limit/${ip}`);
  const cache = caches.default;
  if (await cache.match(cacheKey)) {
    return true;
  }
  await cache.put(
    cacheKey,
    new Response("1", { headers: { "Cache-Control": `max-age=${LEAD_RATE_LIMIT_WINDOW_SECONDS}` } }),
  );
  return false;
}

async function handleLeadCapture(request, env) {
  if (await isRateLimited(request)) {
    return new Response(JSON.stringify({ error: "too many requests -- please try again in a minute" }), {
      status: 429,
      headers: { "Content-Type": "application/json" },
    });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const email = (body && typeof body.email === "string" ? body.email : "").trim();
  // Honeypot: index.html's form includes a hidden "company" field real
  // users never fill in; the client already skips the request when it's
  // non-empty, but check again server-side since a bot may skip the JS.
  const honeypot = body && typeof body.company === "string" ? body.company.trim() : "";

  if (honeypot) {
    // Pretend success so the bot doesn't learn anything -- don't actually
    // send any email.
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (!email || !EMAIL_RE.test(email) || email.length > 254) {
    return new Response(JSON.stringify({ error: "invalid email" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (!env.RESEND_API_KEY || !env.RESEND_FROM_EMAIL) {
    // Fails closed with a clear signal in the response rather than silently
    // pretending it worked -- same "fail loud so it gets noticed and fixed"
    // pattern as modules/email_utils.py on the Railway side.
    return new Response(
      JSON.stringify({ error: "lead capture isn't configured yet" }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }

  const notifyTo = env.LEAD_NOTIFY_EMAIL || "hello@civilproposals.com";

  // Notify the team first -- if this fails, surface an error so the person
  // doesn't get a false "you're on the list" with no one ever actually
  // seeing the lead.
  await sendResendEmail(env, {
    to: notifyTo,
    subject: "New CivilProposals landing page lead",
    html: `<p>New lead signup from the landing page: <strong>${escapeHtml(email)}</strong></p>`,
  });

  // Confirmation to the person -- best-effort, doesn't fail the request if
  // it errors, since the lead is already captured via the notification
  // above.
  //
  // List-Unsubscribe (RFC 2369) + List-Unsubscribe-Post (RFC 8058) below
  // give this a real one-click "Unsubscribe" action in the major mail
  // clients (Gmail, Outlook, Apple Mail all render one when both headers
  // are present) without needing a hosted unsubscribe page or a Resend
  // Audience set up -- neither of which this code change can provision on
  // its own. It's a mailto: fallback, not automated: any opt-out email
  // hello@ receives has to be manually kept off future sends today, since
  // there's no actual recurring-send/list infrastructure behind this form
  // yet (this confirmation is the only email that goes out right now) --
  // see this file's module docstring / DEPLOY.md if a real Resend Audience
  // + campaign system gets built later, which would replace this with
  // Resend's own hosted unsubscribe link instead.
  try {
    await sendResendEmail(env, {
      to: email,
      subject: "Thanks for your interest in CivilProposals",
      headers: {
        "List-Unsubscribe": "<mailto:hello@civilproposals.com?subject=unsubscribe>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
      },
      html:
        '<div style="font-family:sans-serif;font-size:15px;color:#0F172A;line-height:1.6;">' +
        "<p>Thanks for signing up -- we'll send occasional proposal-writing tips and " +
        "a heads-up whenever we ship something new.</p>" +
        "<p>In the meantime, your first tender analysis is free, no card required.</p>" +
        '<p><a href="https://app.civilproposals.com" style="background:#1D4ED8;color:#fff;' +
        'padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block;">' +
        "Try CivilProposals</a></p>" +
        '<p style="color:#5A6B7A;font-size:12px;margin-top:24px;">Don\'t want these? Reply to this ' +
        'email or write to <a href="mailto:hello@civilproposals.com">hello@civilproposals.com</a> ' +
        "and we'll take you off the list.</p>" +
        "</div>",
    });
  } catch (err) {
    console.error("[lead confirmation email] failed:", err);
  }

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Blog
//
// KV layout (the BLOG namespace -- see wrangler.toml):
//   page:/blog/<slug>/     finished HTML for one post
//   page:/blog/            the listing
//   page:/blog/category/x/ a category listing
//   page:__cards__         inner HTML of the homepage blog strip
//   page:/sitemap.xml      the generated sitemap (served with its own type)
//   asset:<key>            an uploaded image, base64 in a metadata-tagged value
//   stat:<slug>:<date>:<shard>  pageview counters (see bumpViewCount)
//
// Everything under page:/ is written by app/modules/blog.py's publish_all(),
// which always does a FULL re-push rather than patching. That means the KV
// contents are exactly reproducible from the database, and a partial failure
// is fixed by pressing Publish again rather than by reasoning about which
// individual keys got through.
// ---------------------------------------------------------------------------

const BLOG_CACHE_SECONDS = 300;

// Counters are read-modify-write against KV, which is eventually consistent
// and has a ~1 write/sec/key ceiling -- two views landing together can read
// the same number and both write N+1, losing one. Spreading each day's
// counts across a few keys and summing on read cuts that contention without
// needing Durable Objects or Analytics Engine (both of which would need
// resources this config doesn't provision). These numbers are therefore
// "close", not exact -- which is why the admin panel says so, and why
// Plausible and Search Console remain the authoritative sources.
const STAT_SHARDS = 8;

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function isAuthorised(request, env) {
  if (!env.BLOG_PUBLISH_SECRET) return false;
  const header = request.headers.get("Authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  // Constant-time-ish compare: bail on length first, then OR every byte
  // difference together so the loop's duration doesn't depend on where the
  // first mismatch is.
  const expected = env.BLOG_PUBLISH_SECRET;
  if (token.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < token.length; i++) {
    diff |= token.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}

// Post paths are normalised to a single canonical form -- lowercase, one
// leading slash, exactly one trailing slash -- so /blog/Foo, /blog/foo and
// /blog/foo/ can't become three separate KV entries or three separate URLs
// competing for the same search ranking.
function normalisePagePath(pathname) {
  let p = (pathname || "").trim().toLowerCase();
  if (!p.startsWith("/")) p = "/" + p;
  p = p.replace(/\/{2,}/g, "/");
  if (!p.endsWith("/") && !p.includes(".")) p += "/";
  return p;
}

async function bumpViewCount(env, slug, ctx) {
  if (!env.BLOG || !slug) return;
  const day = new Date().toISOString().slice(0, 10);
  const shard = Math.floor(Math.random() * STAT_SHARDS);
  const key = `stat:${slug}:${day}:${shard}`;
  const task = (async () => {
    try {
      const current = parseInt((await env.BLOG.get(key)) || "0", 10) || 0;
      // 90-day TTL: long enough for the admin panel's widest window, short
      // enough that the namespace doesn't accumulate forever.
      await env.BLOG.put(key, String(current + 1), { expirationTtl: 60 * 60 * 24 * 90 });
    } catch (err) {
      console.error("[blog stats] increment failed:", err);
    }
  })();
  if (ctx && typeof ctx.waitUntil === "function") {
    ctx.waitUntil(task);   // never make a reader wait on analytics
  }
}

async function collectStats(env, days) {
  if (!env.BLOG) return { posts: [] };
  const wanted = new Set();
  const today = new Date();
  for (let i = 0; i < days; i++) {
    const d = new Date(today.getTime() - i * 86400000);
    wanted.add(d.toISOString().slice(0, 10));
  }

  const totals = new Map();
  let cursor;
  do {
    const listing = await env.BLOG.list({ prefix: "stat:", cursor });
    for (const entry of listing.keys) {
      // stat:<slug>:<date>:<shard> -- slug itself never contains a colon
      // (blog.py's slugify only emits [a-z0-9-]), so a plain split is safe.
      const parts = entry.name.split(":");
      if (parts.length !== 4) continue;
      const [, slug, date] = parts;
      if (!wanted.has(date)) continue;
      const value = parseInt((await env.BLOG.get(entry.name)) || "0", 10) || 0;
      totals.set(slug, (totals.get(slug) || 0) + value);
    }
    cursor = listing.list_complete ? undefined : listing.cursor;
  } while (cursor);

  return {
    days,
    posts: [...totals.entries()]
      .map(([slug, views]) => ({ slug, views }))
      .sort((a, b) => b.views - a.views),
  };
}

// The publish API. Four verbs, all requiring the shared secret:
//   POST /api/blog/page    {path, html}                  write a page
//   POST /api/blog/raw     {path, contentType, body}     write non-HTML (sitemap, cards)
//   POST /api/blog/asset   {key, contentType, base64}    write an image
//   POST /api/blog/remove  {path}                        delete a page
//   GET  /api/blog/stats?days=30                         read the counters
async function handleBlogApi(request, env, url) {
  if (!isAuthorised(request, env)) {
    return jsonResponse({ error: "unauthorised" }, 401);
  }
  if (!env.BLOG) {
    return jsonResponse(
      { error: "the BLOG KV namespace isn't bound to this Worker -- see DEPLOY.md" },
      503,
    );
  }

  const action = url.pathname.replace(/^\/api\/blog\/?/, "").replace(/\/$/, "");

  if (request.method === "GET" && action === "stats") {
    const days = Math.min(365, Math.max(1, parseInt(url.searchParams.get("days") || "30", 10) || 30));
    return jsonResponse(await collectStats(env, days));
  }

  if (request.method !== "POST") {
    return jsonResponse({ error: "method not allowed" }, 405);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "invalid JSON body" }, 400);
  }

  if (action === "page") {
    if (typeof body.path !== "string" || typeof body.html !== "string") {
      return jsonResponse({ error: "path and html are required" }, 400);
    }
    await env.BLOG.put(`page:${normalisePagePath(body.path)}`, body.html);
    return jsonResponse({ ok: true });
  }

  if (action === "raw") {
    // __cards__ is a sentinel, not a path -- don't normalise it into
    // "/__cards__/" the way a real page path would be.
    if (typeof body.path !== "string" || typeof body.body !== "string") {
      return jsonResponse({ error: "path and body are required" }, 400);
    }
    const key = body.path === "__cards__" ? "page:__cards__" : `page:${normalisePagePath(body.path)}`;
    await env.BLOG.put(key, body.body, {
      metadata: { contentType: body.contentType || "text/plain" },
    });
    return jsonResponse({ ok: true });
  }

  if (action === "asset") {
    if (typeof body.key !== "string" || typeof body.base64 !== "string") {
      return jsonResponse({ error: "key and base64 are required" }, 400);
    }
    if (!/^[A-Za-z0-9._-]+$/.test(body.key)) {
      return jsonResponse({ error: "invalid asset key" }, 400);
    }
    const binary = Uint8Array.from(atob(body.base64), (c) => c.charCodeAt(0));
    await env.BLOG.put(`asset:${body.key}`, binary, {
      metadata: { contentType: body.contentType || "application/octet-stream" },
    });
    return jsonResponse({ ok: true });
  }

  if (action === "remove") {
    if (typeof body.path !== "string") {
      return jsonResponse({ error: "path is required" }, 400);
    }
    await env.BLOG.delete(`page:${normalisePagePath(body.path)}`);
    return jsonResponse({ ok: true });
  }

  return jsonResponse({ error: "unknown action" }, 404);
}

async function serveBlog(request, env, url, ctx) {
  const path = normalisePagePath(url.pathname);

  // /blog/media/<key> -- an uploaded image.
  const mediaMatch = url.pathname.match(/^\/blog\/media\/([A-Za-z0-9._-]+)\/?$/);
  if (mediaMatch) {
    if (!env.BLOG) return new Response("Not found", { status: 404 });
    const { value, metadata } = await env.BLOG.getWithMetadata(`asset:${mediaMatch[1]}`, {
      type: "arrayBuffer",
    });
    if (!value) return new Response("Not found", { status: 404 });
    return new Response(value, {
      headers: {
        "Content-Type": (metadata && metadata.contentType) || "application/octet-stream",
        // Images are content-addressed by filename and replaced under a new
        // key when changed, so they're safe to cache hard.
        "Cache-Control": "public, max-age=31536000, immutable",
      },
    });
  }

  // Exactly one URL per page serves content; every other spelling of it
  // (no trailing slash, mixed case, doubled slashes) 301s to the canonical
  // form. Serving the same post at two addresses would split its search
  // signal and is the single easiest SEO mistake to make here.
  if (url.pathname !== path) {
    const target = new URL(url);
    target.pathname = path;
    return Response.redirect(target.toString(), 301);
  }

  if (!env.BLOG) {
    return new Response("The blog isn't configured yet.", {
      status: 503,
      headers: { "Content-Type": "text/plain" },
    });
  }

  const html = await env.BLOG.get(`page:${path}`);
  if (html) {
    // Only count views of actual posts -- not the listing, not categories --
    // so the per-post numbers in the admin panel mean what they say.
    const postMatch = path.match(/^\/blog\/([a-z0-9-]+)\/$/);
    if (postMatch && request.method === "GET") {
      await bumpViewCount(env, postMatch[1], ctx);
    }
    return new Response(html, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": `public, max-age=60, s-maxage=${BLOG_CACHE_SECONDS}`,
      },
    });
  }

  // Nothing in KV for this path. Before 404ing, try the static assets --
  // landing/blog/index.html is a styled "no posts yet" placeholder that
  // covers the window between deploying the blog and publishing the first
  // post. Without it, the Blog link in the nav of every page would lead to
  // a bare "Post not found." for as long as the blog stayed empty.
  const asset = await env.ASSETS.fetch(request);
  if (asset.status === 200) {
    return new Response(asset.body, {
      status: 200,
      headers: {
        "Content-Type": asset.headers.get("Content-Type") || "text/html; charset=utf-8",
        "Cache-Control": "public, max-age=60",
      },
    });
  }

  // A category with zero posts has no KV entry -- publish_all() removes it
  // rather than pushing an empty stub (see blog.py) -- and no matching
  // static file either, so the fetch above 404s. That is not a broken
  // link, it's a category nobody has written in yet, so fall back to the
  // same "no posts yet" placeholder /blog/ itself uses rather than a bare
  // 404. The placeholder is already noindex, for the same reason /blog/ is.
  if (/^\/blog\/category\/[a-z0-9-]+\/$/.test(path)) {
    const blogIndexUrl = new URL(url);
    blogIndexUrl.pathname = "/blog/";
    const blogIndexAsset = await env.ASSETS.fetch(new Request(blogIndexUrl.toString(), request));
    if (blogIndexAsset.status === 200) {
      return new Response(blogIndexAsset.body, {
        status: 200,
        headers: {
          "Content-Type": blogIndexAsset.headers.get("Content-Type") || "text/html; charset=utf-8",
          "Cache-Control": "public, max-age=60",
        },
      });
    }
  }

  const notFound = await env.BLOG.get("page:/blog/404/");
  return new Response(notFound || "Post not found.", {
    status: 404,
    headers: { "Content-Type": notFound ? "text/html; charset=utf-8" : "text/plain; charset=utf-8" },
  });
}

// Splices the current blog cards into the static homepage. Falls through
// untouched when there are no published posts yet, leaving index.html's own
// placeholder copy in place.
class BlogCardsInjector {
  constructor(html) {
    this.html = html;
  }
  element(element) {
    element.setInnerContent(this.html, { html: true });
    element.removeAttribute("data-blog-empty");
  }
}

// assetPath, when given, overrides the pathname used to look up the static
// file (e.g. "/index.es.html") while everything else about the request
// (method, headers) is preserved -- needed for /es and /es/, which don't
// correspond to an actual file on disk the way "/" and "/index.html" do.
async function serveHomeWithBlogCards(request, env, assetPath) {
  let assetRequest = request;
  if (assetPath) {
    const assetUrl = new URL(request.url);
    assetUrl.pathname = assetPath;
    assetRequest = new Request(assetUrl.toString(), request);
  }

  const assetResponse = await env.ASSETS.fetch(assetRequest);
  if (!env.BLOG) return assetResponse;

  const contentType = assetResponse.headers.get("Content-Type") || "";
  if (!contentType.includes("text/html")) return assetResponse;

  const cards = await env.BLOG.get("page:__cards__");
  if (!cards) return assetResponse;

  return new HTMLRewriter()
    .on("#blog-cards", new BlogCardsInjector(cards))
    .transform(assetResponse);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.hostname === "www.civilproposals.com") {
      url.hostname = "civilproposals.com";
      return Response.redirect(url.toString(), 301);
    }

    if (request.method === "POST" && url.pathname === "/api/lead") {
      try {
        return await handleLeadCapture(request, env);
      } catch (err) {
        console.error("[lead capture] failed:", err);
        return new Response(JSON.stringify({ error: "internal error" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    // Blog publish/stats API. Checked before the /blog read routes so a
    // post could never be published at a slug that shadows it.
    if (url.pathname === "/api/blog" || url.pathname.startsWith("/api/blog/")) {
      try {
        return await handleBlogApi(request, env, url);
      } catch (err) {
        console.error("[blog api] failed:", err);
        return jsonResponse({ error: "internal error" }, 500);
      }
    }

    if (url.pathname === "/blog" || url.pathname.startsWith("/blog/")) {
      try {
        return await serveBlog(request, env, url, ctx);
      } catch (err) {
        console.error("[blog] failed to serve:", err);
        return new Response("The blog is temporarily unavailable.", {
          status: 503,
          headers: { "Content-Type": "text/plain" },
        });
      }
    }

    // Generated sitemap once anything has been published; the static file
    // in landing/ is the fallback before that.
    if (url.pathname === "/sitemap.xml" && env.BLOG) {
      try {
        const generated = await env.BLOG.get("page:/sitemap.xml");
        if (generated) {
          return new Response(generated, {
            headers: {
              "Content-Type": "application/xml; charset=utf-8",
              "Cache-Control": "public, max-age=3600",
            },
          });
        }
      } catch (err) {
        console.error("[sitemap] KV read failed, falling back to the static file:", err);
      }
    }

    if (url.pathname === "/" || url.pathname === "/index.html") {
      try {
        return await serveHomeWithBlogCards(request, env);
      } catch (err) {
        // A failure to inject cards must never cost us the homepage.
        console.error("[blog cards] injection failed, serving the page as-is:", err);
        return env.ASSETS.fetch(request);
      }
    }

    // Spanish homepage: /es, /es/, /es/index.html all resolve to the same
    // static index.es.html, same blog-cards splice as the English homepage.
    if (url.pathname === "/es" || url.pathname === "/es/" || url.pathname === "/es/index.html") {
      try {
        return await serveHomeWithBlogCards(request, env, "/index.es.html");
      } catch (err) {
        console.error("[es blog cards] injection failed, serving the page as-is:", err);
        const assetUrl = new URL(request.url);
        assetUrl.pathname = "/index.es.html";
        return env.ASSETS.fetch(new Request(assetUrl.toString(), request));
      }
    }

    // Spanish security/legal pages: no blog cards to splice on any of
    // these, just a straight static-asset fetch of the matching *.es.html
    // file under its canonical /es/... URL.
    const ES_STATIC_PAGE_ROUTES = {
      "/es/security.html": "/security.es.html",
      "/es/privacy-policy.html": "/privacy-policy.es.html",
      "/es/terms-of-service.html": "/terms-of-service.es.html",
      "/es/cookie-policy.html": "/cookie-policy.es.html",
    };
    if (Object.prototype.hasOwnProperty.call(ES_STATIC_PAGE_ROUTES, url.pathname)) {
      const assetUrl = new URL(request.url);
      assetUrl.pathname = ES_STATIC_PAGE_ROUTES[url.pathname];
      return env.ASSETS.fetch(new Request(assetUrl.toString(), request));
    }

    // The bare *.es.html filenames -- everything now links to the
    // canonical /es/... form above, but anything that still has one of
    // these bookmarked or indexed (or /index.es.html specifically, which
    // used to be the auto-redirect's own target) gets sent there too,
    // rather than serving a second copy of the same page at a second URL.
    const ES_BARE_FILENAME_REDIRECTS = {
      "/index.es.html": "/es/",
      "/security.es.html": "/es/security.html",
      "/privacy-policy.es.html": "/es/privacy-policy.html",
      "/terms-of-service.es.html": "/es/terms-of-service.html",
      "/cookie-policy.es.html": "/es/cookie-policy.html",
    };
    if (Object.prototype.hasOwnProperty.call(ES_BARE_FILENAME_REDIRECTS, url.pathname)) {
      const target = new URL(request.url);
      target.pathname = ES_BARE_FILENAME_REDIRECTS[url.pathname];
      return Response.redirect(target.toString(), 301);
    }

    if (url.pathname === "/app" || url.pathname.startsWith("/app/")) {
      const backendUrl = new URL(request.url);
      backendUrl.hostname = BACKEND_HOST;
      backendUrl.protocol = "https:";
      backendUrl.port = "";

      // Streamlit itself is configured with server.baseUrlPath = "app"
      // (see app/.streamlit/config.toml), so it expects requests at
      // /app/... and builds its own asset/websocket URLs the same way.
      //
      // It also issues its own redirect from the bare "/app" (no trailing
      // slash) to "/app/" -- and that redirect comes back with an
      // http:// (not https://) Location, which sends browsers into a
      // redirect loop once Cloudflare/HSTS upgrades it back to https and
      // Streamlit redirects again. Sidestep it entirely by always
      // fetching the trailing-slash form ourselves; the client's address
      // bar is unaffected.
      if (backendUrl.pathname === "/app") {
        backendUrl.pathname = "/app/";
      }

      // Passing the original `request` as the second argument to
      // Request() preserves method, headers, and body -- including the
      // `Upgrade: websocket` header Streamlit's live-update connection
      // relies on. Cloudflare's fetch() has built-in support for proxying
      // a WebSocket upgrade this way: it performs the handshake with the
      // origin and hands back a Response whose `.webSocket` is wired
      // straight through to the original client.
      const backendRequest = new Request(backendUrl.toString(), request);
      backendRequest.headers.set("Host", BACKEND_HOST);

      return fetch(backendRequest, { redirect: "follow" });
    }

    // Shouldn't normally be reached (run_worker_first only sends /app
    // paths here), but fall back to static assets rather than erroring.
    return env.ASSETS.fetch(request);
  },
};

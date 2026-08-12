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
//   4. anything else that reaches this script anyway (shouldn't normally
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

export default {
  async fetch(request, env) {
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

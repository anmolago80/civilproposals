// Worker entry point for the civilproposals.com Cloudflare project (see
// wrangler.toml: run_worker_first routes /app and /app/* here; every other
// path is handled by Cloudflare's static-asset serving before this script
// ever runs, per the [assets] config).
//
// Jobs:
//   1. www.civilproposals.com -> redirect (301) to the apex domain, so
//      links/backlinks/search-engine indexing all consolidate on one
//      canonical host instead of splitting signal across two. Only fires
//      if www is actually routed to this Worker in the first place (a DNS
//      question, not a code one) -- harmless no-op otherwise.
//   2. /app and /app/*  -> reverse-proxy to the Streamlit app on Railway,
//      so it lives at civilproposals.com/app instead of a separate
//      app.civilproposals.com subdomain.
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

async function sendResendEmail(env, { to, subject, html }) {
  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from: env.RESEND_FROM_EMAIL, to: [to], subject, html }),
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error(`Resend API error (${resp.status}): ${detail}`);
  }
}

async function handleLeadCapture(request, env) {
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
    html: `<p>New lead signup from the landing page: <strong>${email}</strong></p>`,
  });

  // Confirmation to the person -- best-effort, doesn't fail the request if
  // it errors, since the lead is already captured via the notification
  // above.
  try {
    await sendResendEmail(env, {
      to: email,
      subject: "Thanks for your interest in CivilProposals",
      html:
        '<div style="font-family:sans-serif;font-size:15px;color:#0F172A;line-height:1.6;">' +
        "<p>Thanks for signing up -- we'll send occasional proposal-writing tips and " +
        "a heads-up whenever we ship something new.</p>" +
        "<p>In the meantime, your first tender analysis is free, no card required.</p>" +
        '<p><a href="https://app.civilproposals.com" style="background:#1D4ED8;color:#fff;' +
        'padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block;">' +
        "Try CivilProposals</a></p>" +
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

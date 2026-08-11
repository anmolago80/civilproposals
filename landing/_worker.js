// Worker entry point for the civilproposals.com Cloudflare project (see
// wrangler.toml: run_worker_first routes /app and /app/* here; every other
// path is handled by Cloudflare's static-asset serving before this script
// ever runs, per the [assets] config).
//
// Two jobs:
//   1. /app and /app/*  -> reverse-proxy to the Streamlit app on Railway,
//      so it lives at civilproposals.com/app instead of a separate
//      app.civilproposals.com subdomain.
//   2. anything else that reaches this script anyway (shouldn't normally
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

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

// Cloudflare Pages Function: reverse-proxies everything under
// civilproposals.com/app/* (including this exact path, /app, via the
// [[path]] catch-all) straight through to the Streamlit app running on
// Railway. This is what lets the app live at civilproposals.com/app
// instead of a separate app.civilproposals.com subdomain.
//
// Streamlit itself is configured with server.baseUrlPath = "app" (see
// app/.streamlit/config.toml), so it already expects to receive requests
// at /app/... and generates its own asset/websocket URLs the same way --
// this function just needs to forward the request to Railway unchanged
// (same path, same query string, same headers, same body).
//
// BACKEND_HOST is Railway's own *.up.railway.app service domain, NOT the
// app.civilproposals.com custom domain and NOT the CNAME target Railway
// gives you for that custom domain (that target hostname only answers
// correctly when the request's Host header is the custom domain itself --
// hitting it directly with its own name as Host returns a 404, which is
// what this was pointed at originally). The plain service domain always
// routes correctly on its own.
//
// If Railway's generated domain ever changes (e.g. the service is
// recreated), update BACKEND_HOST below to match --
// Railway dashboard -> service -> Settings -> Networking -> Public
// Networking shows it, or `railway domain` from the CLI.
const BACKEND_HOST = "civilproposals-production.up.railway.app";

export async function onRequest(context) {
  const { request } = context;

  const backendUrl = new URL(request.url);
  backendUrl.hostname = BACKEND_HOST;
  backendUrl.protocol = "https:";
  backendUrl.port = "";

  // Streamlit issues its own redirect from the bare "/app" (no trailing
  // slash) to "/app/" -- and that redirect comes back with an http://
  // (not https://) Location, which sends browsers into a redirect loop
  // once Cloudflare/HSTS upgrades it back to https and Streamlit redirects
  // again. Sidestep it entirely by always fetching the trailing-slash form
  // from the backend ourselves; the client's address bar is unaffected.
  if (backendUrl.pathname === "/app") {
    backendUrl.pathname = "/app/";
  }

  // Passing the original `request` as the second argument to Request()
  // preserves method, headers, and body -- including the `Upgrade:
  // websocket` header Streamlit's live-update connection relies on.
  // Cloudflare's fetch() has built-in support for proxying a WebSocket
  // upgrade this way: it performs the handshake with the origin and hands
  // back a Response whose `.webSocket` is wired straight through to the
  // original client.
  const backendRequest = new Request(backendUrl.toString(), request);
  backendRequest.headers.set("Host", BACKEND_HOST);

  return fetch(backendRequest, { redirect: "follow" });
}

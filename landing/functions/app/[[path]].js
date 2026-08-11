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
// IMPORTANT: this fetches the Railway-issued hostname directly (not the
// app.civilproposals.com custom domain), so a live app request only
// passes through ONE Cloudflare hop (this Function) rather than two. That
// matters for Streamlit's websocket connection, which DEPLOY.md already
// flagged as "finicky" through Cloudflare's proxy -- routing straight to
// Railway keeps that risk to a single hop instead of stacking two.
//
// If Railway's generated domain ever changes (e.g. the service is
// recreated), update BACKEND_HOST below to match.
const BACKEND_HOST = "0bd53o5g.up.railway.app";

export async function onRequest(context) {
  const { request } = context;

  const backendUrl = new URL(request.url);
  backendUrl.hostname = BACKEND_HOST;
  backendUrl.protocol = "https:";
  backendUrl.port = "";

  // Passing the original `request` as the second argument to Request()
  // preserves method, headers, and body -- including the `Upgrade:
  // websocket` header Streamlit's live-update connection relies on.
  // Cloudflare's fetch() has built-in support for proxying a WebSocket
  // upgrade this way: it performs the handshake with the origin and hands
  // back a Response whose `.webSocket` is wired straight through to the
  // original client.
  const backendRequest = new Request(backendUrl.toString(), request);
  backendRequest.headers.set("Host", BACKEND_HOST);

  return fetch(backendRequest);
}

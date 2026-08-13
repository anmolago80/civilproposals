"""
analytics.py

Privacy-respecting product analytics for the signup funnel, via Plausible's
Events API (https://plausible.io/docs/events-api). Plausible is cookieless
and doesn't fingerprint -- consistent with the Cookie Policy's "no analytics
cookies" statement on the marketing site, which uses the same service (see
landing/index.html's analytics snippet).

How it works: Streamlit can't add a <script> tag to the app page itself, so
each event renders a zero-height components.html iframe whose inline script
POSTs the event to Plausible directly -- same data a pageview beacon would
carry (event name, page URL, user agent), nothing else. No cookies, no
localStorage, no user identifier of any kind is sent. The browser's
Do-Not-Track setting is honoured explicitly.

Every function here is best-effort by design: analytics being down, blocked
(ad blockers commonly block plausible.io -- fine), or unconfigured must
never break or slow the app.

Configuration (env vars):
  PLAUSIBLE_DOMAIN     the site id registered in Plausible for the APP
                       (default: app.civilproposals.com). Set to "off" to
                       disable app-side events entirely.
  PLAUSIBLE_API_HOST   for self-hosted Plausible (default: https://plausible.io).

Events currently fired (see call sites):
  "Auth Screen View"   -- someone reached the login/signup screen
  "Signup Completed"   -- a new account was actually created
  "Bid Analysed"       -- a bid was run (the funnel's activation step)
"""

from __future__ import annotations

import json
import os

PLAUSIBLE_DOMAIN = os.environ.get("PLAUSIBLE_DOMAIN", "app.civilproposals.com").strip()
PLAUSIBLE_API_HOST = os.environ.get("PLAUSIBLE_API_HOST", "https://plausible.io").strip().rstrip("/")


def is_enabled() -> bool:
    return bool(PLAUSIBLE_DOMAIN) and PLAUSIBLE_DOMAIN.lower() != "off"


def track_event(event_name: str, once_per_session: bool = True) -> None:
    """Fires a named Plausible event from the user's browser. With
    once_per_session=True (default), re-renders on later reruns are
    deduplicated via st.session_state so a Streamlit rerun storm can't
    inflate the numbers. Never raises."""
    if not is_enabled():
        return
    try:
        import streamlit as st
        import streamlit.components.v1 as components

        if once_per_session:
            fired = st.session_state.setdefault("_analytics_fired", set())
            if event_name in fired:
                return
            fired.add(event_name)

        payload = {
            "name": event_name,
            "domain": PLAUSIBLE_DOMAIN,
            # location.href inside the component iframe is about:srcdoc --
            # useless -- so the parent app page's URL is used instead. Only
            # origin + path (no query string) to keep tokens/session ids in
            # query params out of analytics.
            "url": "__PARENT_URL__",
        }
        script = f"""
        <script>
        (function() {{
            try {{
                if (navigator.doNotTrack === "1" || window.doNotTrack === "1") return;
                var parentUrl = "";
                try {{
                    parentUrl = window.parent.location.origin + window.parent.location.pathname;
                }} catch (e) {{
                    parentUrl = "https://{PLAUSIBLE_DOMAIN}/";
                }}
                var payload = {json.dumps(payload)};
                payload.url = parentUrl;
                fetch("{PLAUSIBLE_API_HOST}/api/event", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify(payload),
                    keepalive: true
                }}).catch(function() {{}});
            }} catch (e) {{}}
        }})();
        </script>
        """
        components.html(script, height=0)
    except Exception:
        pass

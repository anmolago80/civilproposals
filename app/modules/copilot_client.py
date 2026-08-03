"""
copilot_client.py

Real (not placeholder) integration with the Microsoft 365 Copilot Chat API
(Preview), via Microsoft Graph. Split out from ai_interface.py because this
provider is structurally different from the other four: it authenticates a
signed-in user through Entra ID/OAuth rather than a pasted API key, and the
underlying API is a stateful "conversation" (create conversation, then post
chat turns to it) rather than a single stateless completion call.

Setup this module cannot do for you (see README.md "A note on Microsoft 365
Copilot" for the full walkthrough):
  - Registering an application in your organisation's Entra ID tenant
  - Adding "http://localhost" as a Mobile/desktop redirect URI on that app
  - Adding the seven required Graph delegated permissions and getting a
    tenant admin to grant consent for them
  - Each signed-in user holding a Microsoft 365 Copilot add-on licence

What this module does do: run the interactive sign-in (opens the system
browser via MSAL, which spins up its own local loopback listener -- no
webserver code needed here), silently refresh the token on later calls
within the same session, and speak the Chat API's create-conversation /
post-chat-turn shape.

IMPORTANT -- what this API is and isn't: per Microsoft's own documentation,
the Chat API is grounded chat (your M365 mail/files/Teams data, optionally
+ web), not a general-purpose text/JSON completion endpoint. It returns
text only, has no first-class structured-output mode, and is documented as
prone to gateway timeouts on long-running requests. That matters here
because this app's non-Copilot providers are asked for large, strict-JSON
extractions (tender analysis) and long draft text -- exactly the workload
profile the Chat API is not built for. Wired up honestly rather than
silently, so failures show up as a clear error instead of a mysterious
truncation or invalid-JSON error deep in draft_generator/tender_analyser.
"""

from __future__ import annotations

# The seven delegated Graph scopes the Chat API currently requires together
# -- see the Microsoft Learn "Use the Microsoft 365 Copilot Chat API" docs.
# MSAL wants bare scope names; it resolves them against the Graph resource
# itself based on the authority/client configured.
REQUIRED_SCOPES = [
    "Sites.Read.All",
    "Mail.Read",
    "People.Read.All",
    "OnlineMeetingTranscript.Read.All",
    "Chat.Read",
    "ChannelMessage.Read.All",
    "ExternalItem.Read.All",
]

_GRAPH_BASE = "https://graph.microsoft.com/beta/copilot"


class CopilotAuthError(Exception):
    """Sign-in / token acquisition failed."""


class CopilotAPIError(Exception):
    """The Chat API call itself failed (HTTP error, unexpected shape, timeout)."""


def sign_in_interactive(client_id: str, tenant_id: str) -> dict:
    """
    Runs the interactive OAuth flow: opens the system browser to the Microsoft
    sign-in/consent page, and (via MSAL's built-in loopback listener) captures
    the redirect once the user completes it. Blocks until that finishes.

    Returns a dict: {"access_token": str, "username": str, "cache": str} --
    `cache` is MSAL's serialized token cache, kept in st.session_state (never
    written to disk) so `get_token_silent()` can refresh without re-prompting
    for the rest of the session.

    Raises CopilotAuthError with a plain-language reason on failure --
    missing `msal` package, bad client/tenant ID, consent declined, tenant
    admin consent not yet granted, etc.
    """
    try:
        import msal
    except ImportError as exc:
        raise CopilotAuthError(
            "The 'msal' package isn't installed. Add it with `pip install msal` "
            "(it's in requirements.txt) and restart the app."
        ) from exc

    if not client_id or not tenant_id:
        raise CopilotAuthError("Both the Application (client) ID and Directory (tenant) ID are required to sign in.")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    cache = msal.SerializableTokenCache()
    app = msal.PublicClientApplication(client_id, authority=authority, token_cache=cache)

    try:
        result = app.acquire_token_interactive(scopes=REQUIRED_SCOPES)
    except Exception as exc:
        raise CopilotAuthError(
            f"Sign-in failed to launch: {exc}. This needs a graphical browser to complete -- "
            "it won't work in a headless/remote environment."
        ) from exc

    if not result or "access_token" not in result:
        error_desc = (result or {}).get("error_description", "no details returned")
        raise CopilotAuthError(
            f"Sign-in did not succeed: {error_desc}. Common causes: the redirect URI "
            "'http://localhost' isn't registered on the app, the seven required Graph "
            "permissions haven't been admin-consented for this tenant, or the signed-in "
            "user doesn't hold a Microsoft 365 Copilot licence."
        )

    account = (result.get("id_token_claims") or {})
    username = account.get("preferred_username") or account.get("name") or "signed-in user"
    return {"access_token": result["access_token"], "username": username, "cache": cache.serialize()}


def get_token_silent(client_id: str, tenant_id: str, cache_blob: str | None) -> str | None:
    """
    Tries to reuse a cached refresh token from a previous sign-in this session
    to get a fresh access token without prompting the user again. Returns
    None (never raises) if silent refresh isn't possible -- the caller should
    fall back to sign_in_interactive() in that case.
    """
    if not cache_blob:
        return None
    try:
        import msal
    except ImportError:
        return None

    cache = msal.SerializableTokenCache()
    cache.deserialize(cache_blob)
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(client_id, authority=authority, token_cache=cache)
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(REQUIRED_SCOPES, account=accounts[0])
    if result and "access_token" in result:
        return result["access_token"]
    return None


def chat_once(access_token: str, prompt_text: str, time_zone: str = "UTC") -> str:
    """
    One request/response turn against the Chat API: creates a fresh
    conversation, posts the prompt as a single chat message with web
    grounding turned off (this app drafts from what the user supplied, not
    from a live web search folded silently into a "never invented" section),
    and returns the model's reply text.

    Raises CopilotAPIError on any HTTP failure, timeout, or unexpected
    response shape -- callers (ai_interface._call_copilot) surface this as
    a normal AIConfigError-style failure rather than crashing.
    """
    import requests

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    try:
        create_resp = requests.post(f"{_GRAPH_BASE}/conversations", headers=headers, json={}, timeout=30)
        create_resp.raise_for_status()
        conversation_id = create_resp.json()["id"]
    except Exception as exc:
        raise CopilotAPIError(f"Could not start a Copilot conversation: {exc}") from exc

    body = _build_chat_request_body(prompt_text, time_zone)
    try:
        chat_resp = requests.post(
            f"{_GRAPH_BASE}/conversations/{conversation_id}/chat", headers=headers, json=body, timeout=120,
        )
        chat_resp.raise_for_status()
    except Exception as exc:
        raise CopilotAPIError(
            f"Copilot chat request failed: {exc}. Long, structured-extraction-style prompts "
            "are the case Microsoft's own docs warn is prone to gateway timeouts on this API."
        ) from exc

    return _extract_reply_text(chat_resp.json())


# ---------------------------------------------------------------------------
# Pure helpers -- no network calls, safe to unit-test without live credentials
# ---------------------------------------------------------------------------

def _build_chat_request_body(prompt_text: str, time_zone: str = "UTC") -> dict:
    return {
        "message": {"text": prompt_text},
        "locationHint": {"timeZone": time_zone},
        "contextualResources": {"webContext": {"isWebEnabled": False}},
    }


def _extract_reply_text(response_json: dict) -> str:
    messages = response_json.get("messages") or []
    reply_parts = [
        m.get("text", "") for m in messages
        if m.get("@odata.type", "").endswith("copilotConversationResponseMessage") or "text" in m
    ]
    reply_parts = [t for t in reply_parts if t]
    if not reply_parts:
        raise CopilotAPIError(f"Copilot response had no reply text in it: {response_json}")
    return "\n".join(reply_parts)

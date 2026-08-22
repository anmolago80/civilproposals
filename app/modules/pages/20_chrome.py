# modules/pages/20_chrome.py -- one segment of the CivilProposals app script.
# Workflow progress, sidebar (plan status, step list, admin cost panel), account/billing UI (upgrade buttons, top banner, My-projects / export-import popovers), global CSS, tab creation.
#
# HOW THIS FILE RUNS: app.py executes the files in modules/pages/ in order,
# in ONE shared script namespace (see app.py's loader) -- exactly as when
# all of this was a single 315KB app.py, just split along its natural seams
# so each area of the app lives in its own reviewable file. Code here is
# UNCHANGED from the pre-split app.py; names defined in earlier segments
# (helpers, current_user, _access, the tabs list) are used directly, and
# st.session_state remains the single shared state, same as before.
# Deliberately NOT a function-per-page refactor: that would change scoping
# and evaluation order (the thing a mid-tender regression hides in), and is
# better done tab-by-tab with live click-through testing.
from __future__ import annotations
# ---------------------------------------------------------------------------
# Workflow progress -- computed here (before the sidebar renders) so the
# vertical step list below can use it. Purely a "what's been done so far"
# indicator: Streamlit's st.tabs() never tells the Python side which tab is
# currently being viewed (every tab's content runs on every rerun regardless
# of which one is visually active), so this can't highlight a "current"
# step -- only done vs. not-yet-done.
# ---------------------------------------------------------------------------

_stepper_steps = [
    {"label": i18n.t("nav_project_setup"), "done": bool(_project_identifier())},
    {"label": i18n.t("nav_upload_docs"), "done": st.session_state.tender_extracted is not None},
    {"label": i18n.t("nav_tender_analysis"), "done": st.session_state.analysis is not None},
    {"label": i18n.t("nav_structure"), "done": st.session_state.sections is not None},
    {"label": i18n.t("nav_page_allocation"), "done": st.session_state.allocations is not None},
    {"label": i18n.t("nav_draft_responses"), "done": bool(st.session_state.drafts)},
    {"label": i18n.t("nav_graphics_design"), "done": bool(st.session_state.divider_images) or bool(st.session_state.cover_hero_png)},
    {"label": i18n.t("nav_team_resourcing"), "done": any(
        # Not a plain truthiness check on purpose: as soon as Tender Analysis
        # runs, the Team & Resourcing tab's own code (which also runs every
        # rerun regardless of which tab is visually open) auto-populates
        # resource_plan with one empty slot per discipline detected in the
        # brief -- before the user has assigned a single real person. Require
        # an actual assigned name so this only lights up once someone's
        # really been staffed.
        (getattr(a, "person_name", "") or "").strip() for a in (st.session_state.resource_plan or [])
    )},
    {"label": i18n.t("nav_fee_estimate"), "done": (
        # Not a plain truthiness check on purpose: the Fee Estimate tab's own
        # reconcile-on-every-rerun logic (see _reconcile_estimates() further
        # down) always leaves fee_estimates as a non-empty list of zero-value
        # placeholder rows, one per discipline, even with zero user input --
        # and since Streamlit runs every tab's code on every rerun regardless
        # of which tab is visually open, that list is non-empty from the very
        # first page load. Requiring an actual nonzero figure is what
        # distinguishes "the user entered something" from "the tab merely
        # rendered once".
        any((getattr(e, "fee_percentage", 0) or 0) > 0 for e in (st.session_state.fee_estimates or []))
        or any((getattr(l, "fee_amount", 0) or 0) > 0 for l in (st.session_state.discipline_fee_lines or []))
        or any((getattr(f, "fee_amount", 0) or 0) > 0 for f in (st.session_state.scope_item_fees or []))
    )},
    {"label": i18n.t("nav_export_pack"), "done": bool(st.session_state.docx_buffer)},
]


# ---------------------------------------------------------------------------
# Sidebar -- a clean left rail: top-right Upgrade/Log out actions, brand +
# account status, the step list (the app's real navigation), then project
# file management (My projects, export/import) directly in the flow below --
# nothing hidden behind a menu.
# ---------------------------------------------------------------------------

with st.sidebar:
    # Upgrade/Manage billing and Log out used to live here, pinned to the
    # sidebar's own top corner. Moved to a page-level fixed bar in the top
    # right of the browser window instead (see "_topright_actions" below,
    # rendered in the main content area right before the tabs) -- the user
    # asked for these to be static in the window's top right, not just the
    # top of the (left-hand) sidebar column.
    st.markdown(branding.brand_html(logo_size=30, wordmark_size="1.05rem", show_beta=IS_SAAS_MODE,
                                     href="https://civilproposals.com"),
                unsafe_allow_html=True)

    if IS_SAAS_MODE and current_user:
        i18n.language_picker(key="_sidebar_lang_picker", persist_for_user=current_user)
        st.caption(i18n.t("sidebar_signed_in_as", email=current_user.email))
        if _access.get("unlimited"):
            # UNLIMITED_ACCOUNTS (see auth.get_access_status) -- never
            # blocked, never shown a trial/upgrade banner at all.
            st.success(i18n.t("sidebar_unlimited_access"))
        elif _access["past_due"]:
            st.warning(i18n.t("sidebar_past_due"))
        elif _access["subscribed"]:
            # Active subscription -- capped at SUBSCRIPTION_MONTHLY_BID_LIMIT
            # (see auth.SUBSCRIPTION_MONTHLY_BID_LIMIT) bids per real Stripe
            # billing period, not fully unlimited (see
            # auth.get_access_status); bid_credits still work on top of
            # that quota once it runs out, same as for a non-subscriber.
            if _access["subscription_bids_remaining"] > 0:
                st.success(i18n.t(
                    "sidebar_sub_active_remaining",
                    remaining=_access["subscription_bids_remaining"],
                    limit=_access["subscription_bid_limit"],
                ))
            elif _access.get("bid_credits", 0) > 0:
                st.info(i18n.t("sidebar_sub_used_has_credits", credits=_access["bid_credits"]))
            else:
                st.markdown(
                    '<div style="background:#FFF3E0;color:#B8600A;border:1px solid #F3D9AE;'
                    f'border-radius:8px;padding:10px 14px;font-size:.9rem;font-weight:600;">'
                    f'{i18n.t("sidebar_sub_used_no_credits")}</div>',
                    unsafe_allow_html=True,
                )
        elif _access["limit_reached"]:
            st.markdown(
                '<div style="background:#FFF3E0;color:#B8600A;border:1px solid #F3D9AE;'
                f'border-radius:8px;padding:10px 14px;font-size:.9rem;font-weight:600;">'
                f'{i18n.t("sidebar_limit_reached")}</div>',
                unsafe_allow_html=True,
            )
        elif _access["trial_remaining"] <= 0 and _access.get("bid_credits", 0) > 0:
            # Free trial used up, but they've bought pay-as-you-go bid(s)
            # (see billing.create_bid_checkout_session) -- not the same as
            # limit_reached, so a different, non-alarming message.
            st.info(i18n.t("sidebar_trial_used_has_credits", credits=_access["bid_credits"]))
        else:
            st.info(i18n.t(
                "sidebar_trial_remaining",
                remaining=_access["trial_remaining"], limit=_access["trial_limit"],
            ))

    # Vertical progress list -- the sidebar's main focus (see
    # branding.vertical_steps_component_html()). It's also the app's real
    # navigation -- the native tab strip is
    # hidden (see the [data-testid="stTabs"] [role="tablist"] rule further
    # down, right before the tabs are created) and these rows take over
    # clicking between sections. Rendered via components.html (a real
    # iframe), not st.markdown -- see the docstring on
    # vertical_steps_component_html() for why that distinction actually
    # matters here (st.markdown() silently drops onclick handlers). Height
    # is sized for the row count plus a little breathing room; it doesn't
    # need to be exact -- a few px of empty space or an internal scrollbar
    # is harmless.
    components.html(
        branding.vertical_steps_component_html(_stepper_steps),
        height=max(1, len(_stepper_steps)) * 44 + 16,
    )
    # Used to be the full auth.TERMS_TEXT paragraph, permanently pinned in
    # the sidebar on every single screen -- every user already reads and
    # explicitly accepts that exact wording once, at signup / the
    # accept-terms gate (auth.TERMS_TEXT, auth._render_terms_gate), and it's
    # also the footer disclaimer + Terms of Service on the marketing site.
    # Repeating the full liability paragraph forever after that adds
    # nothing legally (nothing here is the only place it's disclosed) and
    # reads as a constant "we don't trust our own output" banner at exactly
    # the moment a subscriber is deciding this is worth $120/mo. A short
    # reminder + a link to the same full text keeps it one click away
    # without following the user around on every tab.
    st.caption(i18n.t("sidebar_ai_disclaimer"))

    # Admin panel entry -- a real button (not just an expander) that opens a
    # full-screen stats dialog. Rendered ONLY for admin accounts (the DB
    # is_admin flag or auth.ADMIN_ACCOUNTS -- see auth.is_admin_user); other
    # users never see the button. Everything inside is READ-ONLY
    # observability (accounts, bids, subscriptions, AI cost) -- it cannot
    # modify any account -- and every query is wrapped so a stats failure
    # can never take the sidebar down with it.
    if IS_SAAS_MODE and current_user and auth.is_admin_user(current_user):

        @st.dialog("Admin -- accounts, usage & AI cost", width="large")
        def _admin_stats_dialog():
            try:
                _stats = db.admin_stats()
                _cost = db.ai_cost_summary()
            except Exception as _exc:
                st.error(f"Stats unavailable right now: {_exc}")
                return

            st.caption(
                "Read-only view across ALL accounts. Visible only to admin accounts "
                "(auth.ADMIN_ACCOUNTS / the users.is_admin flag)."
            )

            _m1, _m2, _m3, _m4 = st.columns(4)
            _m1.metric("Accounts", _stats["total_users"],
                       delta=f"+{_stats['new_users_30d']} in 30d" if _stats["new_users_30d"] else None)
            _m2.metric("Bids run (all time)", _stats["total_bids"],
                       delta=f"+{_stats['bids_30d']} in 30d" if _stats["bids_30d"] else None)
            _m3.metric("Active subscriptions", _stats["active_subscriptions"],
                       delta=(f"{_stats['past_due_subscriptions']} past due"
                              if _stats["past_due_subscriptions"] else None),
                       delta_color="inverse")
            _m4.metric("Unspent bid credits", _stats["outstanding_bid_credits"])

            st.markdown("#### AI cost")
            _c1, _c2 = st.columns(2)
            _c1.metric("Total estimated AI cost", f"${_cost['total_cost_usd']:.2f}")
            _c2.metric("Last 30 days", f"${_stats['ai_cost_30d_usd']:.2f}")
            st.caption(
                f"{_cost['total_calls']} AI calls logged"
                + (f" ({_cost['unpriced_calls']} with unpriced models -- token counts "
                   f"recorded, cost unknown)" if _cost["unpriced_calls"] else "")
                + ". Prices are estimates from ai_interface.MODEL_PRICES_PER_MTOK."
            )
            if _cost["per_project"]:
                st.markdown("**Cost by project**")
                st.dataframe(
                    [
                        {
                            "Project": p["project_name"],
                            "Calls": p["calls"],
                            "Est. cost (USD)": round(p["cost_usd"], 2),
                            "Tokens in": p["input_tokens"],
                            "Tokens out": p["output_tokens"],
                        }
                        for p in _cost["per_project"]
                    ],
                    use_container_width=True, hide_index=True,
                )

            if _stats["recent_bids"]:
                st.markdown("#### Recent bids")
                st.dataframe(
                    [
                        {
                            "When": b["when"].strftime("%d %b %Y %H:%M") if b["when"] else "",
                            "Account": b["email"],
                            "Project": b["project"],
                        }
                        for b in _stats["recent_bids"]
                    ],
                    use_container_width=True, hide_index=True,
                )

            # Part 2 of the trial-limits/AI-spend-backstop fix brief: the two
            # account-level figures that go with it. accounts_ai_cost_summary()
            # returns raw account fields (subscription_status/bid_credits), not
            # a trial/paid verdict -- classified here (mirroring
            # limits.is_paid_tier) rather than in db.py, so db.py doesn't need
            # to import auth (auth already imports db) just for the
            # UNLIMITED_ACCOUNTS exclusion.
            try:
                _account_costs = db.accounts_ai_cost_summary(min_cost_usd=0.0, limit=200)
            except Exception as _exc:
                _account_costs = []
                st.caption(f"Per-account AI cost unavailable right now: {_exc}")

            def _is_trial_row(row: dict) -> bool:
                if row["email"].strip().lower() in {e.lower() for e in auth.UNLIMITED_ACCOUNTS}:
                    return False
                return row["subscription_status"] not in ("active", "past_due") and row["bid_credits"] <= 0

            _trial_rows = [r for r in _account_costs if _is_trial_row(r)]
            _near_or_over = [
                r for r in _trial_rows
                if r["cost_usd"] >= limits.TRIAL_AI_SPEND_CEILING_USD * 0.8
            ]
            st.markdown("#### Trial accounts near/over the AI-spend ceiling")
            st.caption(
                f"Ceiling is ${limits.TRIAL_AI_SPEND_CEILING_USD:.2f} (see modules/limits.py) -- "
                f"shown once a trial account reaches 80% of it."
            )
            if _near_or_over:
                st.dataframe(
                    [
                        {
                            "Account": r["email"],
                            "Est. cost (USD)": round(r["cost_usd"], 2),
                            "Status": "Over ceiling -- AI features blocked" if r["cost_usd"] >= limits.TRIAL_AI_SPEND_CEILING_USD else "Near ceiling",
                            "AI calls": r["calls"],
                        }
                        for r in sorted(_near_or_over, key=lambda r: r["cost_usd"], reverse=True)
                    ],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("No trial accounts are near the ceiling right now.")

            st.markdown("#### Top accounts by estimated AI spend")
            if _account_costs:
                st.dataframe(
                    [
                        {
                            "Account": r["email"],
                            "Est. cost (USD)": round(r["cost_usd"], 2),
                            "Plan": ("Unlimited" if r["email"].strip().lower() in {e.lower() for e in auth.UNLIMITED_ACCOUNTS}
                                     else "Trial" if _is_trial_row(r) else "Paid"),
                            "AI calls": r["calls"],
                        }
                        for r in _account_costs[:15]
                    ],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("No AI calls logged for any account yet.")

        if st.button("📊 Admin stats", key="_admin_stats_btn", use_container_width=True):
            _admin_stats_dialog()

        # Blog editor. Deliberately NOT a dialog like the stats panel above:
        # writing an article needs the full page, so this just flips a flag
        # and reruns -- modules/pages/15_admin_blog.py picks it up on the way
        # through (it runs before this file) and renders the editor
        # full-width, st.stop()ing before the sidebar and workflow tabs are
        # ever built. See that file's docstring.
        if st.button("✍️ Write / edit blog", key="_admin_blog_btn", use_container_width=True):
            st.session_state._blog_admin_mode = True
            st.rerun()

    # Firm profile -- the firm's own standing facts (ABN, insurances, logo,
    # signatory, rates, standing text). Same full-page-and-stop pattern as the
    # blog editor above (modules/pages/17_firm_profile.py runs before this
    # file), but deliberately NOT admin-gated: every account has one, and it
    # is what stops the same details being re-typed, or left red, on every
    # bid this firm writes.
    st.divider()
    if st.button("🏢 Firm profile", key="_firm_profile_btn", use_container_width=True):
        st.session_state._firm_profile_mode = True
        st.rerun()
    if _firm_profile_is_empty():
        st.caption(
            "Not filled in yet -- it removes about ten red placeholders from every pack."
        )

    # "My projects" / "This computer" and "Export / import a file" used to
    # live here, stacked below the steps. Moved into two popovers in the
    # fixed top-right banner instead (see _render_my_projects_popover() and
    # _render_export_import_popover(), called from there) -- the user asked
    # for them up in the banner alongside Upgrade/Log out rather than taking
    # up permanent vertical space in the sidebar.

    if not IS_SAAS_MODE:
        st.divider()
        st.markdown("**Claude API key**")
        _current_claude_key = (
            st.session_state.ai_config.get("api_key", "")
            if st.session_state.ai_config.get("provider") == "Anthropic Claude" else ""
        )
        sidebar_claude_key = st.text_input(
            "Anthropic API key", type="password", key="_sidebar_claude_key",
            value=_current_claude_key,
            help="Same key used everywhere in the app -- this is just a shortcut to the field on the "
                 "AI Provider Settings tab.",
        )
        st.checkbox(
            "Remember this key on this computer", key="_remember_claude_key",
            help="Saves the key to a local .env file next to the app so it's already filled in next "
                 "time you launch it. Left unticked, it's only kept for this session, like before.",
        )
        if sidebar_claude_key:
            prev_model = st.session_state.ai_config.get("model") \
                if st.session_state.ai_config.get("provider") == "Anthropic Claude" else None
            st.session_state.ai_config = {
                "provider": "Anthropic Claude",
                "api_key": sidebar_claude_key,
                "model": prev_model or ai_interface.get_default_model("Anthropic Claude"),
                "endpoint": "",
            }
            if st.session_state._remember_claude_key:
                _save_anthropic_key_to_env(sidebar_claude_key)
                st.caption("Remembered -- this key will be pre-filled automatically next time you open the app.")
        else:
            st.caption("Paste your Anthropic Claude API key here to enable AI-powered steps across the app.")

        with st.expander("Other AI providers (OpenAI, Azure, Gemini, Microsoft 365 Copilot)"):
            st.caption(
                "Only needed if you're not using Anthropic Claude. Picking a provider here replaces "
                "the key above for the rest of this session. Sign-in tokens are never written to disk."
            )
            _other_providers = [p for p in ai_interface.PROVIDERS if p != "Anthropic Claude"]
            _current_other_provider = st.session_state.ai_config.get("provider", "")
            # "Anthropic Claude" is deliberately not one of the choices in THIS dropdown (it has its
            # own field above) -- but that means whenever Claude is the active provider, none of
            # these options match it, so the widget has to default its on-screen selection to
            # _other_providers[0] just to render something. That default must stay purely cosmetic:
            # picking up this section (even collapsed -- Streamlit still executes this code every
            # rerun) must NEVER by itself switch the active provider away from a working Claude
            # config. Only an api_key the user actually typed below (or a completed Copilot
            # sign-in) may overwrite st.session_state.ai_config -- see the two branches below,
            # both gated on real user input, never on this selectbox's mere current value.
            _other_provider_index = (
                _other_providers.index(_current_other_provider) if _current_other_provider in _other_providers else 0
            )
            provider = st.selectbox("AI provider", _other_providers, key="provider_select", index=_other_provider_index)
            # Only pre-fill the fields below from session state when THIS provider is already the
            # active one -- otherwise show blank fields, both so a provider you haven't switched to
            # doesn't silently inherit another provider's secret key into its text box, and so an
            # empty field here can't be mistaken for "this provider is configured".
            _other_provider_is_active = _current_other_provider == provider

            if provider.startswith("Microsoft 365 Copilot"):
                with st.expander("Before you sign in -- one-time setup your organisation's Entra admin needs to do", expanded=not st.session_state.copilot_client_id):
                    st.markdown(
                        "Copilot doesn't take a pasted API key -- it authenticates the signed-in user "
                        "through your organisation's Microsoft Entra ID, and it requests broad delegated "
                        "read access (mail, Teams chats/channels, meeting transcripts, SharePoint sites), "
                        "not just proposal drafting. Someone with Entra admin rights needs to, once:\n\n"
                        "1. Go to **entra.microsoft.com** → App registrations → New registration.\n"
                        "2. Under **Redirect URI**, choose platform **Mobile and desktop applications** "
                        "and add `http://localhost` exactly as written (no port number).\n"
                        "3. Under **API permissions** → Add a permission → Microsoft Graph → **Delegated "
                        "permissions**, add all seven: `Sites.Read.All`, `Mail.Read`, `People.Read.All`, "
                        "`OnlineMeetingTranscript.Read.All`, `Chat.Read`, `ChannelMessage.Read.All`, "
                        "`ExternalItem.Read.All`.\n"
                        "4. Click **Grant admin consent** for your organisation (a tenant admin has to do "
                        "this step -- individual users can't self-consent to these scopes).\n"
                        "5. Copy the **Application (client) ID** and **Directory (tenant) ID** from the "
                        "app's Overview page into the two fields below.\n\n"
                        "Every user who signs in also needs their own Microsoft 365 Copilot add-on licence. "
                        "Sign-in opens your system browser -- it needs a real display, so it won't work "
                        "over a headless/remote connection."
                    )
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Application (client) ID", key="copilot_client_id")
                with col2:
                    st.text_input("Directory (tenant) ID", key="copilot_tenant_id")

                # Access tokens expire in roughly an hour; try a silent refresh from the cached
                # refresh token on every rerun rather than making the user re-click "Sign in"
                # mid-session. Never prompts/opens a browser -- silently does nothing if it can't.
                if st.session_state.copilot_token_cache and st.session_state.copilot_client_id:
                    from modules.copilot_client import get_token_silent
                    refreshed = get_token_silent(
                        st.session_state.copilot_client_id, st.session_state.copilot_tenant_id,
                        st.session_state.copilot_token_cache,
                    )
                    if refreshed:
                        st.session_state.copilot_access_token = refreshed

                sign_in_ready = bool(st.session_state.copilot_client_id and st.session_state.copilot_tenant_id)
                if st.session_state.copilot_access_token:
                    st.success(f"Signed in as {st.session_state.copilot_username}.")
                    if st.button("Sign out", type="primary"):
                        st.session_state.copilot_access_token = ""
                        st.session_state.copilot_token_cache = ""
                        st.session_state.copilot_username = ""
                        st.rerun()
                else:
                    if st.button("Sign in with Microsoft", type="primary", disabled=not sign_in_ready):
                        from modules.copilot_client import sign_in_interactive, CopilotAuthError
                        with st.spinner("Opening your browser to sign in and consent..."):
                            try:
                                result = sign_in_interactive(st.session_state.copilot_client_id, st.session_state.copilot_tenant_id)
                                st.session_state.copilot_access_token = result["access_token"]
                                st.session_state.copilot_token_cache = result["cache"]
                                st.session_state.copilot_username = result["username"]
                                st.success(f"Signed in as {result['username']}.")
                            except CopilotAuthError as exc:
                                st.error(str(exc))
                    if not sign_in_ready:
                        st.info("Enter the Application (client) ID and Directory (tenant) ID above to enable sign-in.")

                # Only switch the active provider to Copilot once sign-in has actually completed --
                # never just because this branch happened to render (see the note above the
                # selectbox for why that would otherwise silently clobber a working Claude config).
                if st.session_state.copilot_access_token:
                    st.session_state.ai_config = {
                        "provider": provider, "api_key": "", "model": "", "endpoint": "",
                        "access_token": st.session_state.copilot_access_token,
                    }
                st.warning(
                    "Even once signed in: Microsoft's own docs describe this API as grounded chat, not a "
                    "general completion endpoint -- text-only replies, no guaranteed structured output, "
                    "and prone to timeouts on long requests. This app's Tender Analysis and Draft "
                    "Responses steps send large, strict-JSON-expecting prompts, which is exactly the kind "
                    "of request that API is documented to struggle with. If a step fails or times out, "
                    "switch providers for that step rather than assuming something else is broken."
                )
            else:
                has_key_already = bool(st.session_state.ai_config.get("api_key")) and _other_provider_is_active
                with st.expander(f"How to get an API key from {provider}", expanded=not has_key_already):
                    st.markdown(PROVIDER_SETUP_STEPS.get(provider, "Steps not available for this provider."))

                api_key = st.text_input(
                    "API key", type="password", key="api_key_input",
                    value=st.session_state.ai_config.get("api_key", "") if _other_provider_is_active else "",
                )
                default_model = ai_interface.get_default_model(provider)
                model = st.text_input(
                    "Model" + (" / deployment name" if provider == "Azure OpenAI" else ""),
                    value=(st.session_state.ai_config.get("model") if _other_provider_is_active else "") or default_model,
                    key="model_input",
                )
                endpoint = ""
                if provider == "Azure OpenAI":
                    endpoint = st.text_input(
                        "Azure endpoint URL", key="endpoint_input",
                        value=st.session_state.ai_config.get("endpoint", "") if _other_provider_is_active else "",
                        placeholder="https://your-resource.openai.azure.com",
                    )
                # Only switch the active provider once the user has actually typed a key for THIS
                # provider -- rendering this section (even just by expanding it) must never by
                # itself replace a working Claude (or other provider's) config with an empty one.
                if api_key:
                    st.session_state.ai_config = {"provider": provider, "api_key": api_key, "model": model, "endpoint": endpoint}
                    st.success(f"{provider} configured for this session.")
                elif _other_provider_is_active:
                    st.warning(f"{provider} API key cleared -- enter it again to keep using {provider} this session.")
                else:
                    st.caption(f"Enter an API key above to switch this session to {provider}.")
    # In SAAS_MODE, nothing renders here at all -- AI drafting runs on
    # the account's own server-side ANTHROPIC_API_KEY (see the module
    # docstring at the top of this file), so there's no API key
    # concept to surface to a subscriber. The "never invents..." disclaimer
    # used to live here, at the very bottom of the sidebar -- moved to sit
    # immediately under the step list instead (see above), per the user's
    # request to have it read right alongside the workflow steps rather
    # than below everything else.
# This CSS is deliberately injected here -- after auth.require_login() has
# already returned above, meaning a user is definitely signed in by this
# point -- rather than in the unconditional page-wide <style> block near
# the top of the file. require_login()'s own login/signup screen also uses
# st.tabs() (the "Log in" / "Create account" pair), and both instances
# share the exact same data-testid -- Streamlit has no way to distinguish
# "the main workflow's tabs" from "some other tabs" in CSS. Injecting the
# hide rule only from here means it's never even present in the page while
# the login tabs are what's showing, so it can't accidentally hide those
# too (confirmed the hard way: an earlier version of this rule in the
# global block broke the "Create account" tab). The sidebar's own nav-row
# styling (hover/active) lives inside vertical_steps_component_html()'s
# iframe instead of here -- a components.html iframe can't see this
# page's stylesheet, so that CSS has to travel with the HTML it styles.
st.markdown(
    """
    <style>
    /* The native tab strip is hidden -- navigation now happens entirely
       through the vertical step list in the sidebar (see
       branding.vertical_steps_component_html(), rendered above). The tabs
       themselves are NOT removed from the underlying code: st.tabs()
       still renders every section's content on every rerun exactly as
       before (several tabs rely on that -- e.g. Team & Resourcing
       auto-seeding, Fee Estimate reconciliation -- see the comments on
       _stepper_steps above), so this is a purely visual change: the real
       tab buttons still exist and still work, just hidden, and get
       "clicked" programmatically by the sidebar's JS bridge instead of by
       the user directly. */
    [data-testid="stTabs"] [role="tablist"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def _render_my_projects_popover_body() -> None:
    """Contents of the top banner's "My Proposals" popover -- the same
    autosave-status + recent-projects-open/delete UI that used to sit
    permanently in the sidebar (see the comment left in its place there),
    just now tucked behind a click instead of always taking up vertical
    space. Local-disk vs. DB-backed branch exactly as before. Also hosts
    the "Export / Import" section (see _render_export_import_popover_body)
    at the bottom, folded in here so the top banner only needs one popover
    for project-level actions instead of two."""
    if not IS_SAAS_MODE:
        # Local-disk autosave -- only correct for the original single-user
        # desktop prototype. In SAAS_MODE this is replaced by the DB-backed
        # branch below (see cloud_project_store.py): writing to a
        # 'projects/' folder on the *server's* disk in a hosted,
        # multi-tenant deployment would be shared across every logged-in
        # user's browser sessions (a real data leak, not just a rough edge),
        # and Railway's container disk is wiped on every redeploy regardless.
        st.checkbox(
            i18n.t("chrome_autosave_checkbox_label"), key="_autosave_enabled",
            help=i18n.t("chrome_autosave_help_local", seconds=AUTOSAVE_INTERVAL_SECONDS),
        )
        if st.session_state._last_autosave_path:
            st.caption(i18n.t(
                "chrome_autosave_last_saved",
                time=datetime.fromtimestamp(st.session_state._last_autosave_ts).strftime('%H:%M:%S'),
            ))
        elif not _project_identifier() and st.session_state.tender_extracted is None:
            st.caption(i18n.t("chrome_autosave_enable_hint"))

        local_projects = local_project_store.list_local_projects()
        if local_projects:
            options = [p["display_name"] for p in local_projects]
            chosen = st.selectbox(i18n.t("chrome_recent_projects_label"), options, key="_local_project_pick")
            chosen_entry = next(p for p in local_projects if p["display_name"] == chosen)
            lcol1, lcol2 = st.columns(2)
            with lcol1:
                if st.button(i18n.t("btn_open"), key="_open_local_project", type="primary"):
                    try:
                        loaded_state = local_project_store.load_local(chosen_entry["path"])
                        _apply_loaded_project(loaded_state, f"'{chosen_entry['display_name']}'")
                    except project_store.ProjectLoadError as exc:
                        st.error(str(exc))
            with lcol2:
                if st.button(i18n.t("btn_delete"), key="_delete_local_project", type="primary"):
                    local_project_store.delete_local(chosen_entry["path"])
                    st.rerun()
        else:
            st.caption(i18n.t("chrome_no_local_saves"))

    elif current_user:
        # DB-backed equivalent of the local-disk branch above, scoped to
        # this user's account (see cloud_project_store.py) -- so uploads,
        # brief analysis, drafts, and team assignments survive a page
        # refresh, a dropped connection, or the app being redeployed,
        # instead of living only in this one browser tab's live session.
        st.checkbox(
            i18n.t("chrome_autosave_checkbox_label"), key="_autosave_enabled",
            help=i18n.t("chrome_autosave_help_cloud", seconds=AUTOSAVE_INTERVAL_SECONDS),
        )
        if st.session_state._last_autosave_error:
            st.warning(i18n.t("chrome_autosave_failed_warning", error=st.session_state._last_autosave_error))
        elif st.session_state._last_autosave_path:
            st.caption(i18n.t(
                "chrome_autosave_last_saved",
                time=datetime.fromtimestamp(st.session_state._last_autosave_ts).strftime('%H:%M:%S'),
            ))
        elif not _project_identifier() and st.session_state.tender_extracted is None:
            st.caption(i18n.t("chrome_autosave_enable_hint"))

        cloud_projects = cloud_project_store.list_cloud_projects(current_user.id)
        if cloud_projects:
            options = [p["display_name"] for p in cloud_projects]
            chosen = st.selectbox(i18n.t("chrome_recent_projects_label"), options, key="_cloud_project_pick")
            chosen_entry = next(p for p in cloud_projects if p["display_name"] == chosen)
            lcol1, lcol2 = st.columns(2)
            with lcol1:
                if st.button(i18n.t("btn_open"), key="_open_cloud_project", type="primary"):
                    try:
                        loaded_state = cloud_project_store.load_cloud(current_user.id, chosen_entry["id"])
                        _apply_loaded_project(loaded_state, f"'{chosen_entry['display_name']}'")
                    except project_store.ProjectLoadError as exc:
                        st.error(str(exc))
            with lcol2:
                if st.button(i18n.t("btn_delete"), key="_delete_cloud_project", type="primary"):
                    cloud_project_store.delete_cloud(current_user.id, chosen_entry["id"])
                    st.rerun()
        else:
            st.caption(i18n.t("chrome_no_cloud_saves"))

    st.divider()
    with st.expander(i18n.t("chrome_export_import_expander")):
        _render_export_import_popover_body()


def _render_export_import_popover_body() -> None:
    """Contents of the "Export / Import" section nested inside the "My
    Proposals" popover (see _render_my_projects_popover_body) -- unchanged
    behaviour from when this was its own top-banner popover, just folded
    in one level so the top banner only shows My Proposals / Proposal
    Library / Project Reference Library."""
    st.caption(i18n.t("chrome_export_import_caption"))
    loaded_file = st.file_uploader(i18n.t("chrome_load_project_file_label"), type=["zip"], key="project_loader")
    if loaded_file is not None and st.session_state._last_loaded_project_name != loaded_file.name:
        try:
            loaded_state = project_store.load_project(loaded_file.getvalue())
            st.session_state._last_loaded_project_name = loaded_file.name
            _apply_loaded_project(loaded_state, f"'{loaded_file.name}'")
        except project_store.ProjectLoadError as exc:
            st.error(str(exc))

    if st.button(i18n.t("chrome_prepare_save_button"), type="primary"):
        st.session_state._project_save_bytes = project_store.save_project(st.session_state)
    if st.session_state._project_save_bytes:
        save_filename = (st.session_state.tender_name or "untitled_project").replace(" ", "_")
        st.download_button(
            i18n.t("chrome_download_project_file_button"), data=st.session_state._project_save_bytes,
            file_name=f"{save_filename}.tenderproj.zip", mime="application/zip",
         type="primary")


def _render_proposal_library_popover_body() -> None:
    """Contents of the top banner's "Proposal Library" popover -- upload,
    browse, and download full proposal packs, organised by discipline.
    Entries land here either automatically (Export Pack tab -> 'Archive to
    Library') or via direct upload (below). Used to live as an
    always-collapsed expander at the bottom of Project Setup; moved up here
    (same popover treatment as "My Proposals" / "Project Reference Library")
    so it's reachable from any tab."""
    with st.expander(i18n.t("chrome_upload_proposal_expander")):
        st.caption(i18n.t("chrome_upload_proposal_caption"))
        _lib_up_file = st.file_uploader(
            i18n.t("chrome_proposal_file_label"), type=["docx"], key="lib_upload_proposal_file",
        )
        _lib_up_col1, _lib_up_col2 = st.columns(2)
        with _lib_up_col1:
            _lib_up_type = st.selectbox(i18n.t("chrome_discipline_label"), PROJECT_TYPES, key="lib_upload_proposal_type")
        with _lib_up_col2:
            _lib_up_pack = st.selectbox(i18n.t("chrome_pack_size_label"), ["Large Scope", "Small Scope"], key="lib_upload_proposal_pack")
        _lib_up_name = st.text_input(
            i18n.t("chrome_project_name_optional_label"), key="lib_upload_proposal_name",
        )
        if st.button(i18n.t("chrome_add_to_library_button"), key="lib_upload_proposal_btn", disabled=_lib_up_file is None, type="primary"):
            try:
                _default_name = _lib_up_file.name.rsplit(".", 1)[0] if _lib_up_file else ""
                proposal_library.archive_proposal(
                    _lib_user_id(),
                    _lib_up_file.getvalue(),
                    project_type=_lib_up_type,
                    pack_type="small_scope" if _lib_up_pack == "Small Scope" else "large_scope",
                    project_name=(_lib_up_name or "").strip() or _default_name,
                )
                st.success(i18n.t("chrome_added_to_library_success", name=_lib_up_file.name, type=_lib_up_type))
                st.rerun()
            except Exception as exc:
                _show_error(i18n.t("chrome_couldnt_upload_action"), exc)

    st.divider()
    st.caption(i18n.t("chrome_browse_library_caption"))
    _lib_pack_type = "small_scope" if _is_letter() else "large_scope"
    _lib_pack_label = "Small Scope" if _is_letter() else "Large Scope"
    _lib_type_filter = st.selectbox(
        i18n.t("chrome_filter_by_discipline_label"), ["All"] + PROJECT_TYPES, key="lib_setup_type_filter",
    )
    st.caption(i18n.t(
        "chrome_showing_pack_caption", pack_label=_lib_pack_label,
        discipline=(i18n.t("chrome_all_disciplines_label") if _lib_type_filter == "All" else _lib_type_filter),
    ))
    _lib_entries = proposal_library.list_library(
        _lib_user_id(),
        None if _lib_type_filter == "All" else _lib_type_filter,
        pack_type=_lib_pack_type,
    )
    if not _lib_entries:
        if _lib_type_filter == "All":
            st.caption(i18n.t("chrome_library_empty_all", pack_label=_lib_pack_label))
        else:
            st.caption(i18n.t("chrome_library_empty_filtered", discipline=_lib_type_filter, pack_label=_lib_pack_label))
    else:
        for _e in _lib_entries:
            _client_bit = f" | client: {_e['client_name']}" if _e.get("client_name") else ""
            st.markdown(
                f"**{_e.get('project_name') or _e.get('tender_name') or 'Untitled'}** -- "
                f"{_e.get('project_type', '')} | archived {_e.get('archived_at', '')}"
                f"{_client_bit}"
            )
            _lcol1, _lcol2 = st.columns(2)
            _lib_bytes = None
            with _lcol1:
                try:
                    _lib_bytes = proposal_library.read_entry_bytes(_lib_user_id(), _e["path"])
                    st.download_button(
                        i18n.t("btn_download"), data=_lib_bytes, file_name=_e.get("filename", "proposal.docx"),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"lib_dl_{_e.get('path')}", width="stretch",
                     type="primary")
                except Exception:
                    st.caption(i18n.t("chrome_file_unavailable"))
            with _lcol2:
                # "Add as reference to project" -- pulls this proposal's text into
                # the CURRENT project's "Previous proposals" company material
                # (Upload Docs), same effect as uploading it there by hand. Used
                # to be its own picker buried in Upload Docs; moved here so it
                # sits right next to the entry it applies to.
                if st.button(i18n.t("chrome_add_as_reference_button"), key=f"lib_addref_{_e.get('path')}", width="stretch", type="primary"):
                    try:
                        _bytes_for_ref = _lib_bytes if _lib_bytes is not None else proposal_library.read_entry_bytes(_lib_user_id(), _e["path"])
                        _doc = document_processor.extract_text_from_docx(_bytes_for_ref, _e.get("filename", "proposal.docx"))
                        if _doc.text:
                            _key = "previous_proposals"
                            _existing = st.session_state.company_material_files.get(_key, {})
                            st.session_state.company_material_files[_key] = document_processor.merge_extracted_material(
                                _existing, {_e.get("filename", "proposal.docx"): _doc.text},
                            )
                            st.session_state.company_material_text[_key] = "\n\n".join(
                                st.session_state.company_material_files[_key].values()
                            )
                            st.success(i18n.t("chrome_added_as_reference_success", filename=_e.get('filename')))
                            st.rerun()
                        else:
                            st.warning(i18n.t("chrome_extract_failed_warning"))
                    except Exception as exc:
                        _show_error(i18n.t("chrome_couldnt_add_as_reference_action"), exc)
            st.divider()


def _render_project_reference_library_popover_body() -> None:
    """Contents of the top banner's "Project Reference Library" popover --
    a separate library from Proposal Library, for firm reference-project
    writeups/case studies (PDF, DOCX, or TXT) uploaded directly, organised
    by discipline the same way Proposal Library is. Nothing lands here
    automatically -- there's no "generate a reference project" step in the
    app to archive from, so upload is the only way in."""
    with st.expander(i18n.t("chrome_upload_reference_expander")):
        st.caption(i18n.t("chrome_upload_reference_caption"))
        _ref_up_file = st.file_uploader(
            i18n.t("chrome_reference_file_label"), type=["pdf", "docx", "txt"], key="reflib_upload_file",
        )
        _ref_up_type = st.selectbox(i18n.t("chrome_discipline_label"), PROJECT_TYPES, key="reflib_upload_type")
        _ref_up_title = st.text_input(
            i18n.t("chrome_title_optional_label"), key="reflib_upload_title",
        )
        if st.button(i18n.t("chrome_add_to_reference_library_button"), key="reflib_upload_btn", disabled=_ref_up_file is None, type="primary"):
            try:
                _default_title = _ref_up_file.name.rsplit(".", 1)[0] if _ref_up_file else ""
                reference_library.upload_reference(
                    _lib_user_id(),
                    _ref_up_file.getvalue(),
                    project_type=_ref_up_type,
                    filename=_ref_up_file.name,
                    title=(_ref_up_title or "").strip() or _default_title,
                )
                st.success(i18n.t("chrome_added_to_reference_library_success", name=_ref_up_file.name, type=_ref_up_type))
                st.rerun()
            except Exception as exc:
                _show_error(i18n.t("chrome_couldnt_upload_action"), exc)

    st.divider()
    st.caption(i18n.t("chrome_browse_reference_library_caption"))
    _ref_type_filter = st.selectbox(
        i18n.t("chrome_filter_by_discipline_label"), ["All"] + PROJECT_TYPES, key="reflib_type_filter",
    )
    _ref_entries = reference_library.list_library(
        _lib_user_id(),
        None if _ref_type_filter == "All" else _ref_type_filter,
    )
    if not _ref_entries:
        if _ref_type_filter == "All":
            st.caption(i18n.t("chrome_reference_library_empty_all"))
        else:
            st.caption(i18n.t("chrome_reference_library_empty_filtered", discipline=_ref_type_filter))
    else:
        for _e in _ref_entries:
            st.markdown(
                f"**{_e.get('title') or _e.get('filename') or 'Untitled'}** -- "
                f"{_e.get('project_type', '')} | uploaded {_e.get('uploaded_at', '')}"
            )
            _rcol1, _rcol2 = st.columns(2)
            _ref_bytes = None
            with _rcol1:
                try:
                    _ref_bytes = reference_library.read_entry_bytes(_lib_user_id(), _e["path"])
                    st.download_button(
                        i18n.t("btn_download"), data=_ref_bytes, file_name=_e.get("filename", "reference_project"),
                        key=f"reflib_dl_{_e.get('path')}", width="stretch",
                     type="primary")
                except Exception:
                    st.caption(i18n.t("chrome_file_unavailable"))
            with _rcol2:
                # "Add to project references" -- pulls this reference project's text
                # into the CURRENT project's "Project references" company material
                # (Upload Docs), same effect as uploading it there by hand.
                if st.button(i18n.t("chrome_add_to_project_references_button"), key=f"reflib_addref_{_e.get('path')}", width="stretch", type="primary"):
                    try:
                        _bytes_for_ref = _ref_bytes if _ref_bytes is not None else reference_library.read_entry_bytes(_lib_user_id(), _e["path"])
                        _doc = _extract_plain_text_from_bytes(_bytes_for_ref, _e.get("filename", "reference_project"))
                        if _doc.text:
                            _key = "project_references"
                            _existing = st.session_state.company_material_files.get(_key, {})
                            st.session_state.company_material_files[_key] = document_processor.merge_extracted_material(
                                _existing, {_e.get("filename", "reference_project"): _doc.text},
                            )
                            st.session_state.company_material_text[_key] = "\n\n".join(
                                st.session_state.company_material_files[_key].values()
                            )
                            st.success(i18n.t("chrome_added_to_project_references_success", filename=_e.get('filename')))
                            st.rerun()
                        else:
                            st.warning(_doc.warning or i18n.t("chrome_extract_failed_warning"))
                    except Exception as exc:
                        _show_error(i18n.t("chrome_couldnt_add_to_project_references_action"), exc)
            st.divider()


# Top banner -- static in the browser window's top right corner (per the
# user's request), not just the top of the left-hand sidebar column.
# Rendered here in the MAIN content area (not inside `with st.sidebar:`)
# specifically so `position: fixed` anchors to the whole viewport rather
# than the sidebar's own stacking context -- no JS-driven position syncing
# needed this time (unlike the old sidebar version), since a viewport
# corner is a fixed target and doesn't move as content scrolls. A little
# top padding is added to the tab content below so the fixed bar never
# overlaps a tab's own heading.
#
# "My Proposals" (which also folds in "Export / Import" as a nested
# expander -- see _render_my_projects_popover_body), "Proposal Library" and
# "Project Reference Library" live here too now, as three compact popovers
# -- laid out horizontally alongside Upgrade/Log out (a flex row, see the
# CSS below) rather than stacked as separate always-expanded sections down
# the sidebar, which was pushing the banner-worthy actions out of easy
# reach and growing the sidebar's height for content most visits don't
# need. Rendered unconditionally (both SaaS and local-disk mode) so the
# popovers are always available; only Upgrade/Manage billing and Log out
# stay gated to signed-in SaaS accounts.
with st.container(key="_topright_actions"):
    with st.popover(i18n.t("btn_my_proposals"), width="content"):
        _render_my_projects_popover_body()
    with st.popover(i18n.t("btn_proposal_library"), width="content"):
        _render_proposal_library_popover_body()
    with st.popover(i18n.t("btn_project_reference_library"), width="content"):
        _render_project_reference_library_popover_body()
    if IS_SAAS_MODE and current_user:
        if _access["subscribed"] or _access["past_due"]:
            # past_due means there's already a real Stripe subscription, just
            # with a failing card -- "Manage" (Stripe's Customer Portal,
            # where they can update payment details) is what actually fixes
            # that. It used to fall into the "Upgrade" branch below instead,
            # which offered to start a SECOND subscription and never
            # surfaced the one place that lets them fix the first one.
            #
            # This top banner (and the portal URL below) renders on
            # literally every rerun across the whole app, so creating a
            # fresh Stripe Billing Portal Session unconditionally here used
            # to mean a live Stripe API call on every single click anywhere
            # in the app for every subscriber -- the paying customers ended
            # up with the slowest experience. Portal Session URLs stay valid
            # well past this cache window, so caching one in session_state
            # for SUBSCRIPTION_REFRESH_INTERVAL_SECONDS and only creating a
            # fresh one once it's stale cuts that down to at most one Stripe
            # call per interval instead of one per rerun -- still always a
            # real, immediately-clickable link, never the vanishing-link
            # two-step pattern _render_upgrade_buttons() deliberately moved
            # away from.
            _now_ts = time.time()
            if _now_ts - st.session_state.get("_portal_url_ts", 0.0) >= SUBSCRIPTION_REFRESH_INTERVAL_SECONDS:
                st.session_state["_portal_url_cache"] = billing.create_customer_portal_session(current_user)
                st.session_state["_portal_url_ts"] = _now_ts
            portal_url = st.session_state.get("_portal_url_cache")
            if portal_url:
                st.link_button(i18n.t("btn_manage"), portal_url, type="primary")
        else:
            with st.popover(i18n.t("btn_upgrade"), width="content"):
                _render_upgrade_buttons(current_user, key_prefix="_topright")
        if st.button(i18n.t("btn_log_out"), key="_topright_logout_btn"):
            auth.log_out()
            st.rerun()
st.markdown(
    """<style>
    .st-key-_topright_actions {
        /* z-index has to clear Streamlit's own header/toolbar bar
           (data-testid="stHeader"), which sits at z-index: 999990 --
           invisible in this app (see the `header [data-testid="stToolbar"]
           {visibility: hidden}` rule near the top of the file) but still
           present and still stacked above ordinary page content, so
           without this our fixed bar renders UNDER it and never appears. */
        position: fixed !important; top: 0.75rem; right: 1.5rem; z-index: 1000000;
        display: flex !important; flex-direction: row !important; gap: 8px;
        align-items: flex-start;
        justify-content: flex-end;
        /* Streamlit's own emotion-cache classes on this container default
           it to width: 100% (fine in normal flow, but once position:fixed
           takes it out of flow that stretches it across the whole
           viewport, pushing its flex-start-aligned children to the LEFT
           edge instead of the right). Shrink it back to its content so
           "right: 1.5rem" actually reads as "hug the right edge". */
        width: fit-content !important; left: auto !important;
        background: transparent;
    }
    /* Compact the popover trigger + Upgrade/Log out buttons so the row
       stays a single slim horizontal strip instead of growing the banner
       -- smaller padding and font than Streamlit's default button size. */
    .st-key-_topright_actions button {
        padding: 0.25rem 0.7rem !important;
        font-size: 0.82rem !important;
        min-height: 0 !important;
    }
    .st-key-_topright_upgrade_btn button, .st-key-_topright_upgrade_btn a {
        background-color: #2563EB !important; color: #fff !important;
        border-color: #2563EB !important;
    }
    .st-key-_topright_upgrade_btn button:hover, .st-key-_topright_upgrade_btn a:hover {
        background-color: #1D4ED8 !important; border-color: #1D4ED8 !important;
    }
    .st-key-_topright_logout_btn button {
        background-color: #DC2626 !important; color: #fff !important;
        border-color: #DC2626 !important;
    }
    .st-key-_topright_logout_btn button:hover {
        background-color: #B91C1C !important; border-color: #B91C1C !important;
    }
    /* Reserve room up top so the fixed bar never sits over a tab's own
       heading -- applied to the main content block specifically, not
       the sidebar, which keeps its own normal top spacing. */
    [data-testid="stAppViewContainer"] > .main [data-testid="stMainBlockContainer"] {
        padding-top: 3.5rem;
    }
    </style>""",
    unsafe_allow_html=True,
)

tabs = st.tabs([
    f"1 · {i18n.t('nav_project_setup')}", f"2 · {i18n.t('tab_upload_documents')}",
    f"3 · {i18n.t('nav_tender_analysis')}", f"4 · {i18n.t('tab_proposal_structure')}", f"5 · {i18n.t('nav_page_allocation')}",
    f"6 · {i18n.t('nav_draft_responses')}", f"7 · {i18n.t('nav_graphics_design')}", f"8 · {i18n.t('nav_team_resourcing')}",
    f"9 · {i18n.t('nav_fee_estimate')}", f"10 · {i18n.t('nav_export_pack')}",
])



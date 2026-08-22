# English catalog -- the reference/authoring language. See translations/__init__.py.
from __future__ import annotations

STRINGS: dict[str, str] = {
    "language_picker_label": "Language",

    # Sidebar navigation (vertical step list labels -- see branding.py /
    # modules/pages/20_chrome.py's _stepper_steps).
    "nav_project_setup": "Project Setup",
    "nav_upload_docs": "Upload Docs",
    "nav_tender_analysis": "Tender Analysis",
    "nav_structure": "Structure",
    "nav_page_allocation": "Page Allocation",
    "nav_draft_responses": "Draft Responses",
    "nav_graphics_design": "Graphics & Design",
    "nav_team_resourcing": "Team & Resourcing",
    "nav_fee_estimate": "Fee Estimate",
    "nav_export_pack": "Export Pack",

    # The numbered tab strip (modules/pages/20_chrome.py's `tabs = st.tabs([...])`)
    # uses slightly different wording than the sidebar step list above for two
    # of the ten steps (this predates i18n -- kept as-is rather than quietly
    # merged, since smoke_test.py's tab-label check pins the exact tab text).
    "tab_upload_documents": "Upload Documents",
    "tab_proposal_structure": "Proposal Structure",

    # Sidebar account/plan status.
    "sidebar_signed_in_as": "Signed in as **{email}**",
    "sidebar_unlimited_access": "Unlimited access",
    "sidebar_past_due": "Payment past due -- update your card to keep access.",
    "sidebar_sub_active_remaining": "Plan: Active subscription -- {remaining} of {limit} bid(s) left this cycle",
    "sidebar_sub_used_has_credits": "Monthly bids used -- {credits} pay-as-you-go credit(s) available",
    "sidebar_sub_used_no_credits": "Monthly bids used -- buy a bid to keep going, or wait for renewal.",
    "sidebar_limit_reached": "Maximum number of free bids reached -- upgrade to keep going.",
    "sidebar_trial_used_has_credits": "Pay-as-you-go: {credits} bid credit(s) available",
    "sidebar_trial_remaining": "Free trial: {remaining} of {limit} bid(s) left",
    "sidebar_ai_disclaimer": "AI-generated content -- review before submitting. [Full Terms of Service](https://civilproposals.com/terms-of-service.html)",

    # Top-right banner.
    "btn_my_proposals": "📁 My Proposals",
    "btn_proposal_library": "📁 Proposal Library",
    "btn_project_reference_library": "📁 Project Reference Library",
    "btn_manage": "Manage",
    "btn_upgrade": "Upgrade",
    "btn_log_out": "Log out",

    # Login / signup screen.
    "auth_headline": "Built by Civil Engineers, for Civil Engineers",
    "auth_subhead": (
        "We know the challenges you face every day because we face them too. Whether it's a small "
        "project with a simple scope, a brief buried in an email, a client who isn't quite sure what "
        "they want, or a major tender that takes days to read and weeks to prepare, CivilProposals is "
        "designed to help. Built by civil engineers, for civil engineers, the platform assists you in "
        "creating professional, well structured proposals faster, allowing you to focus on understanding "
        "client needs and developing winning solutions."
    ),
    "auth_tab_login": "Log in",
    "auth_tab_signup": "Create account",
    "auth_email": "Email",
    "auth_password": "Password",
    "auth_login_submit": "Log in",
    "auth_forgot_password": "Forgot password?",
    "auth_forgot_caption": "Enter your account email and we'll send a link to reset your password.",
    "auth_forgot_submit": "Send reset link",
    "auth_reset_not_configured": "Password reset isn't set up yet -- contact support directly for now.",
    "auth_reset_sent": "If an account exists for that email, we've sent a reset link -- check your inbox (and spam folder). It's valid for 1 hour.",
    "auth_error_bad_login": "Incorrect email or password.",
    "auth_signup_name": "Your name",
    "auth_signup_firm": "Firm name",
    "auth_signup_email": "Work email",
    "auth_signup_password_help": "At least 8 characters.",
    "auth_signup_confirm_password": "Confirm password",
    "auth_signup_trial_caption": "Free trial: {limit} full bid, no card required. Then pay per bid, or subscribe monthly -- see pricing on the homepage.",
    "auth_signup_terms_expander": "Terms you're agreeing to",
    "auth_signup_terms_checkbox": "I have read and accept the terms above and the Terms of Service.",
    "auth_signup_submit": "Create account",
    "auth_error_passwords_no_match": "Passwords don't match -- please re-enter them.",
    "auth_error_must_accept_terms": "Please accept the terms above to create an account.",

    # Terms acceptance gate.
    "terms_gate_title": "### Before you continue",
    "terms_gate_intro": "Please review and accept the terms below -- this only takes a second, and you won't be asked again.",
    "terms_gate_checkbox": "I have read and accept these terms and the Terms of Service.",
    "terms_gate_accept": "Accept and continue",
    "terms_gate_logout": "Log out instead",

    # Password reset screen.
    "pw_reset_success": "Password updated -- you can log in with your new password now.",
    "pw_reset_continue": "Continue to log in",

    # Part B -- one-pass free tier.
    "free_tier_artifact_used": (
        "Your free download of this document has already been used. Buy a bid to download it "
        "again, or to unlock everything else for this project."
    ),
    "free_tier_generate_used": (
        "Your one free generation pass has already been used on this project. Buy a bid to "
        "generate again with your latest changes."
    ),
    "free_tier_paid_only_caption": "Included with a paid bid -- not part of the free trial.",
    "free_tier_whats_included_title": "What's included in your free trial",
    "free_tier_whats_included_body": (
        "One free run of Tender Analysis, and one free download each of the Proposal (DOCX), "
        "the Tender Summary (DOCX), and the Org Chart (PPTX) -- for one project. Everything "
        "else, and any re-download or regeneration, needs a paid bid."
    ),

    # Part B2 -- pass allowances per plan.
    "passes_remaining_caption": "{remaining} of {total} pass(es) left on this project",
    "passes_exhausted": "No passes left on this project. Buy a top-up (+5 passes), or start a new project on your subscription.",
    "passes_topup_button": "Buy 5 more passes ($50)",
    "passes_topup_success": "5 passes added to this project.",
    "subscription_bid_limit_caption": "{limit} proposal projects included per month",

    # Part C -- single-bid rules & rename-confirm dialog.
    "bid_includes_popover_title": "What a bid includes",
    "bid_includes_popover_body": (
        "A single $50 bid covers **one project** (identified by its project name, tender name, "
        "client name, and the uploaded brief together) with **5 generation passes** and "
        "**unlimited downloads** of your current documents. A pass is spent when you run Tender "
        "Analysis, or when you regenerate after changing an input -- re-downloading the same, "
        "unchanged documents never spends a pass. Renaming a project, or swapping in a different "
        "brief, creates a new project identity for billing purposes -- your paid analysis stays "
        "attached to the old identity."
    ),
    "rename_confirm_title": "Rename this project?",
    "rename_confirm_body": (
        "Renaming changes this project's identity -- your paid analysis stays with the old name. "
        "Continue?"
    ),
    "rename_confirm_yes": "Yes, rename",
    "rename_confirm_cancel": "Cancel",
}

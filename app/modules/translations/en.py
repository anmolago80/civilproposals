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

    # Part A2 -- Structure / Page Allocation / Draft Responses tabs
    # (40_structure_allocation.py, 50_drafting.py)

    # --- Tab 4: Proposal Structure ---
    "structure_subheader": "Proposal Structure",
    "structure_caption": (
        "If the brief names its own selection criteria, the structure mirrors those exactly. "
        "Otherwise it falls back to the standard skeleton, ordered by weighting."
    ),
    "structure_run_analysis_first": "Run Tender Analysis first.",
    "structure_generate_button": "Generate Proposal Structure",
    "structure_generated_success": "Generated {n} section(s).",
    "structure_format_stale_warning": (
        "You changed the Proposal format (Project Setup) after these sections were generated, so "
        "the list below is still built for the *previous* format and won't match what "
        "drafting/export expect (e.g. no 'Project Understanding' section for a Small Scope "
        "pack). Click **Generate Proposal Structure** above again to refresh it."
    ),
    "structure_col_number": "#",
    "structure_col_title": "Title",
    "structure_col_fixed": "Fixed",
    "structure_fixed_yes": "Yes",
    "structure_fixed_no": "No",
    "structure_col_weighting": "Weighting",
    "structure_col_weighting_source": "Weighting source",
    "structure_col_pages": "Pages",
    "structure_col_page_source": "Page source",
    "structure_override_weighting_expander": "Manually override a section's weighting",
    "structure_section_label": "Section",
    "structure_new_weighting_label": "New weighting (%)",
    "structure_apply_weighting_button": "Apply weighting override",
    "structure_weighting_applied_success": "Weighting for '{target}' set to {weight:.0f}%. Structure recalculated.",
    "structure_compliance_heading": "#### Compliance matrix",
    "structure_generate_compliance_button": "Generate Compliance Matrix",
    "structure_compliance_col_id": "ID",
    "structure_compliance_col_description": "Description",
    "structure_compliance_col_type": "Type",
    "structure_compliance_col_mapped_section": "Mapped section",
    "structure_compliance_col_priority": "Priority",
    "structure_compliance_col_status": "Status",
    "structure_gap_heading": "#### Gap analysis",
    "structure_generate_gap_button": "Generate Gap Analysis",
    "structure_gap_col_risk": "Risk",
    "structure_gap_col_issue": "Issue",
    "structure_gap_col_impact": "Impact",
    "structure_gap_col_recommended_action": "Recommended action",
    "structure_gap_col_section": "Section",

    # --- Tab 5: Page Allocation ---
    "pageaalloc_subheader": "Page Allocation",
    "pageaalloc_caption": (
        "Priority order: brief's exact section limit > weighted share of a stated total > "
        "default template."
    ),
    "pageaalloc_small_scope_info": (
        "The Small Scope pack doesn't carry a stated page limit to mirror, so this step is "
        "indicative only -- its actual section lengths come from the Sections table (tab "
        "4), not from page allocation."
    ),
    "pageaalloc_generate_structure_first": "Generate the Proposal Structure first.",
    "pageaalloc_col_section": "Section",
    "pageaalloc_col_weighting": "Weighting",
    "pageaalloc_col_source": "Source",
    "pageaalloc_col_allocated_pages": "Allocated pages",
    "pageaalloc_col_reason": "Reason",
    "pageaalloc_override_pages_expander": "Manually override a section's page count",
    "pageaalloc_section_label": "Section",
    "pageaalloc_new_pages_label": "New page count",
    "pageaalloc_apply_pages_button": "Apply page override",
    "pageaalloc_pages_applied_success": "'{target}' set to {pages} page(s). Structure updated.",

    # --- Tab 6: Draft Responses ---
    "drafting_subheader": "Draft Responses",
    "drafting_letter_caption": (
        "The Small Scope pack has two sections that are genuinely free text -- Introduction "
        "and Methodology and Deliverables, both drafted below. Scope of Work comes straight "
        "from the brief, Project Team/Fees/Program have their own dedicated steps "
        "(Team & Resourcing / Fee Estimate), and Terms of Engagement further down is "
        "always your own wording, never AI-drafted."
    ),
    "drafting_standard_caption": (
        "First-pass draft content per section, with red guidance notes and a list of what "
        "still needs real user input."
    ),
    "drafting_generate_structure_and_hint": "Generate the Proposal Structure and {hint}.",
    "drafting_format_stale_warning": (
        "The Proposal format (Project Setup) was changed after the current sections were generated. "
        "Go to Structure and click **Generate Proposal Structure** again before drafting, or "
        "this will silently draft nothing for the sections that only exist in this format."
    ),
    "drafting_generate_button": "Generate First-Pass Drafts",
    "drafting_nothing_to_draft_error": (
        "Nothing to draft -- the current sections don't match any of this format's "
        "AI-drafted section titles. This usually means the Proposal format (Project Setup) was "
        "changed after Proposal Structure was generated. Go to Structure and click "
        "**Generate Proposal Structure** again, then retry this."
    ),
    "drafting_progress_text": "Drafting...",
    "drafting_done_text": "Done.",
    "drafting_progress_detail": "Drafted '{title}' ({done}/{total})...",
    "drafting_queued_text": "Queued for drafting...",
    "drafting_thin_warning": (
        "**Drafting finished, but some sections came back empty or very short:** {sections}"
        ". Re-run drafting for those, or write them yourself -- they will export "
        "as red placeholders until you do."
    ),
    "drafting_generation_complete_success": "Draft generation complete for {n} section(s).",
    "drafting_generation_failed_error": "Draft generation failed",

    "drafting_risk_register_heading": "#### Risk register",
    "drafting_risk_register_caption": (
        "A first-pass risk / impact / mitigation table, structured from the risks the brief "
        "itself raises and the gaps the analysis found. **A mitigation is a commitment your "
        "firm will be held to**, so the AI only ever states one the brief already describes -- "
        "everything else comes back as **TBC** for you to decide. Edit anything below."
    ),
    "drafting_risk_register_button": "Draft risk register",
    "drafting_risk_run_analysis_caption": (
        "Run Tender Analysis first -- the register is built from the brief's own risks."
    ),
    "drafting_risk_register_failed_error": "Drafting the risk register failed",
    "drafting_risk_none_warning": (
        "No risks came back -- the brief may not raise any. Nothing has been "
        "changed; add rows by hand below if you want a register anyway."
    ),
    "drafting_risk_structured_success": "Structured {n} risk(s) -- review below.",
    "drafting_risk_confirm_rerisk_warning": (
        "You already have a risk register, and some of it may be your own edits. Drafting "
        "again replaces every row. Click **Draft risk register** once more to go ahead."
    ),
    "drafting_cancel_button": "Cancel",
    "drafting_risk_col_risk": "Risk",
    "drafting_risk_col_impact": "Impact",
    "drafting_risk_col_mitigation": "Mitigation",
    "drafting_risk_col_source": "Source",
    "drafting_risk_tbc_caption": (
        "Rows left as **TBC** export in red, so nobody submits an unfilled mitigation by "
        "accident."
    ),

    "drafting_design_stages_heading": "#### Design stages",
    "drafting_design_stages_caption": (
        "The delivery stages behind the exported methodology table. The AI assigns your "
        "brief's own scope items and deliverables to stages and rephrases them -- it never "
        "adds a task, activity, deliverable or date that isn't in the brief, and writes "
        "**TBC** wherever the brief doesn't support a cell. Edit anything below; what's here "
        "when you export is exactly what goes into the table."
    ),
    "drafting_stages_button": "Draft methodology stages",
    "drafting_stages_run_analysis_caption": (
        "Run Tender Analysis first -- the stages are built from the brief's own scope and deliverables."
    ),
    "drafting_stages_failed_error": "Drafting the methodology stages failed",
    "drafting_stages_none_warning": (
        "The AI returned no stages -- nothing has been changed. You can fill "
        "the grid in by hand with **Start a blank grid** below."
    ),
    "drafting_stages_drafted_success": "Drafted {n} stage(s) -- review and edit below.",
    "drafting_stages_confirm_restage_warning": (
        "You already have a stage grid below, and some of it may be your own edits. "
        "Drafting again replaces every stage. Click **Draft methodology stages** once "
        "more to go ahead, or edit the grid directly instead."
    ),
    "drafting_blank_grid_button": "Start a blank grid",
    "drafting_no_stages_caption": (
        "No stages yet. Without them the exported methodology table falls back to its "
        "generic four-stage layout with placeholder columns."
    ),
    "drafting_stage_title": "Stage {n}: {name}",
    "drafting_stage_untitled": "Untitled",
    "drafting_stage_name_label": "Stage name",
    "drafting_stage_first_week_label": "First week",
    "drafting_stage_last_week_label": "Last week",
    "drafting_week_numbers_caption": (
        "Week numbers come from the delivery program on the Fees & Program step. "
        "Set an anticipated start date there and these become real dates in the "
        "exported table."
    ),
    "drafting_key_tasks_label": "Key tasks (one per line)",
    "drafting_engagement_activities_label": "Engagement activities (one per line)",
    "drafting_outcome_label": "Outcome",
    "drafting_deliverables_label": "Deliverables (one per line)",
    "drafting_cell_tbc_caption": (
        "Leave a cell as **TBC** where the brief genuinely doesn't say -- it exports "
        "in red so nobody submits it by accident."
    ),
    "drafting_remove_stage_button": "Remove this stage",
    "drafting_add_stage_button": "Add a stage",
    "drafting_wvr_checkbox_label": (
        "Confirm this firm issues Work Verification Records (WVRs) with design deliverables"
    ),
    "drafting_wvr_checkbox_help": (
        "The methodology table used to state this as fact in every export without "
        "anyone having been asked. Leave it unticked and it exports as a red "
        "[CONFIRM WVR / QA STATEMENT] instead."
    ),

    "drafting_diff_pitch_caption": (
        "**Differentiator & sales pitch** -- write these in your own words: what sets this "
        "firm apart for this bid, and the pitch for why it should win. AI review is optional "
        "-- it comments on the text as written and offers a tightened, re-angled rewrite tied "
        "to this brief's real scope, but only ever works with what you've written here, never "
        "invents new claims."
    ),
    "drafting_differentiator_label": "Differentiator",
    "drafting_differentiator_placeholder": "What sets this firm apart for this bid?",
    "drafting_sales_pitch_label": "Sales pitch",
    "drafting_sales_pitch_placeholder": "The pitch for why this firm should win.",
    "drafting_review_ai_button": "Review with AI",
    "drafting_pitch_review_failed_error": "Pitch review failed",
    "drafting_review_complete_success": "Review complete.",
    "drafting_sharpen_heading": "**Sharpen further with follow-up questions**",
    "drafting_sharpen_caption": (
        "Generates a few targeted questions about whatever's still vague or unsupported in what "
        "you've written above (up to 4 per field), then folds your answers straight into a sharper "
        "rewrite -- same rule as everywhere else on this page, nothing added beyond what you type. "
        "Only runs when you click the button, never automatically."
    ),
    "drafting_get_questions_button": "Get sharpening questions",
    "drafting_generate_questions_failed_error": "Couldn't generate questions",
    "drafting_both_specific_caption": (
        "Both already read specific and concrete -- no follow-up questions needed."
    ),
    "drafting_sharpen_with_answers_button": "Sharpen with my answers",
    "drafting_sharpened_success": "Sharpened using your answers -- see the rewrite below.",
    "drafting_sharpening_failed_error": "Sharpening failed",
    "drafting_diff_ai_comment_heading": "**Differentiator -- AI comment**",
    "drafting_suggested_rewrite_heading": "**Suggested rewrite**",
    "drafting_use_rewrite_button": "Use this rewrite",
    "drafting_pitch_ai_comment_heading": "**Sales pitch -- AI comment**",

    "drafting_exec_summary_caption": (
        "**Executive summary** -- an unweighted page that goes straight after the cover, "
        "before the scored sections (Large Scope pack) or straight after the cover (Small "
        "Scope pack). No score of its own, but it's the evaluators' first impression, so it's "
        "drafted warm and sales-forward rather than dry -- catchy titles, short readable "
        "blocks, grounded in the real brief and the real (included) nominated team."
    ),
    "drafting_exec_summary_draft_first_caption": (
        "Draft the sections first -- the summary is written from what the proposal "
        "actually says, so that it can't promise a subject the document doesn't cover."
    ),
    "drafting_generate_exec_summary_button": "Generate Executive Summary (AI)",
    "drafting_exec_summary_empty_warning": (
        "The executive summary came back empty -- nothing has been saved over "
        "what you had. Try again, or write it yourself; the pack's first page "
        "exports as a red placeholder until it exists."
    ),
    "drafting_exec_summary_drafted_success": "Executive summary drafted.",
    "drafting_exec_summary_failed_error": "Executive summary generation failed",
    "drafting_exec_summary_expander": "Executive summary",

    "drafting_team_intro_caption": (
        "**Team introduction** -- a short sales-forward pitch at the very start of Key "
        "Personnel, before the org chart and pen pics: a catchy headline and a couple of "
        "paragraphs connecting the nominated (included) team's real past projects to this "
        "brief's real challenges, closing with a pull-quote line. Grounded entirely in "
        "each person's own value-to-project write-up and relevant projects, entered on the "
        "Team & Resourcing tab -- never invented."
    ),
    "drafting_generate_team_intro_button": "Generate Team Introduction (AI)",
    "drafting_team_intro_empty_warning": (
        "The team introduction came back empty. This usually means the "
        "nominated people have no write-ups yet -- fill in their "
        "\"on this project they will...\" text on Team & Resourcing and "
        "try again."
    ),
    "drafting_team_intro_drafted_success": "Team introduction drafted.",
    "drafting_team_intro_failed_error": "Team introduction generation failed",
    "drafting_assign_person_caption": "Assign at least one person on the Team & Resourcing tab first.",
    "drafting_team_intro_expander": "Team introduction",

    "drafting_experience_intro_caption": (
        "**Project experience introduction** -- a short sales-forward paragraph at the "
        "start of Relevant Project Experience, before the individual project cards: "
        "names the strongest 2-4 comparable reference projects and states plainly why "
        "they prove this firm can deliver the brief, replacing the generic 'selected "
        "past projects' note. Grounded entirely in the real reference projects entered "
        "and drafted in Upload Docs -- never invented."
    ),
    "drafting_generate_experience_intro_button": "Generate Project Experience Introduction (AI)",
    "drafting_experience_intro_help": "Needs at least one drafted reference project -- see below.",
    "drafting_experience_intro_empty_warning": (
        "The project experience introduction came back empty -- the "
        "reference projects may have no description or relevance text yet. "
        "The section falls back to its default note until this exists."
    ),
    "drafting_experience_intro_drafted_success": "Project experience introduction drafted.",
    "drafting_experience_intro_failed_error": "Project experience introduction generation failed",
    "drafting_no_reference_projects_caption": (
        "No drafted reference projects yet. Go to Upload Docs, upload 'Project references' "
        "material if you haven't, then click **Draft reference projects from uploaded "
        "material** there -- or add one manually on that same step."
    ),
    "drafting_experience_intro_expander": "Project experience introduction",

    "drafting_page_limit_prefix": "Page limit: {text}",
    "drafting_evaluation_weighting_prefix": "Evaluation weighting: {text}",
    "drafting_formatting_prefix": "Formatting: {text}",
    "drafting_still_needs_heading": "**Still needs from you:**",

    "drafting_terms_heading": "#### Terms of Engagement",
    "drafting_terms_caption": (
        "Always your own text -- this tool never invents or guesses which contract/commercial "
        "conditions apply, since getting that wrong is a real legal risk."
    ),
    "drafting_terms_label": "Terms of Engagement",
    "drafting_terms_placeholder": (
        "e.g. This offer is made under our current Master Services Agreement with "
        "Townsville City Council, reference ..."
    ),

    "drafting_spinner_risk_register": "Structuring the risk register...",
    "drafting_spinner_stages": "Drafting methodology stages...",
    "drafting_spinner_pitch_review": "Reviewing differentiator & sales pitch...",
    "drafting_spinner_questions": "Coming up with follow-up questions...",
    "drafting_spinner_sharpening": "Sharpening with your answers...",
    "drafting_spinner_exec_summary": "Drafting executive summary...",
    "drafting_spinner_team_intro": "Drafting team introduction...",
    "drafting_spinner_experience_intro": "Drafting project experience introduction...",

    # Part A2 -- Graphics & Design / Team & Resourcing tabs
    # (55_graphics.py, 60_team.py)

    # --- Tab 7: Graphics & Design ---
    "graphics_project_team_subheader": "Project Team",
    "graphics_project_team_caption": (
        "Built entirely from the Team & Resourcing tab (step 8) -- the same people, the same "
        "CV-drafted bios, and the same 'include in proposal' ticks used there also drive this "
        "pack's Project Team section, so there's only one place to build your team, whichever "
        "pack size you're preparing. Head to step 8 to assign people, draft bios from the CV "
        "library, add a team member under a discipline lead (with their own title), and tick "
        "who's included. This is a read-only preview of what the exported pack will show."
    ),
    "graphics_project_team_empty_info": (
        "No one is assigned and ticked 'Include in proposal' yet -- head to step 8 "
        "(Team & Resourcing) to build the team."
    ),
    "graphics_not_assigned": "[not assigned]",
    "graphics_subheader": "Graphics & Design",
    "graphics_caption": (
        "Real, generated divider banners and cover art built from your own uploaded photos and "
        "typed quotes -- never invented imagery. Everything this tool can't build for real "
        "(org charts, methodology diagrams, programme timelines) stays a clearly marked placeholder below."
    ),
    "graphics_need_structure_info": "Generate the Proposal Structure first.",
    "graphics_quotes_heading": "#### 1. Pull-quotes / testimonials (optional)",
    "graphics_quotes_caption": "Only real quotes you type in here -- nothing is invented or pulled from the web.",
    "graphics_quote_label": "Quote",
    "graphics_quote_placeholder": "e.g. \"The team delivered a technically excellent outcome...\"",
    "graphics_quote_attributed_label": "Attributed to",
    "graphics_quote_attributed_placeholder": "e.g. J. Smith, Project Director, XYZ Council",
    "graphics_quote_project_label": "Project (optional)",
    "graphics_quote_project_placeholder": "e.g. Burnett River Bridge",
    "graphics_add_quote_button": "Add quote",
    "graphics_unattributed": "unattributed",
    "graphics_remove_button": "Remove",
    "graphics_photos_heading": "#### 2. Project photos",
    "graphics_photos_caption": (
        "Pick the cover photo. It fills the front page of the pack; the rest stay "
        "available for section dividers below."
    ),
    "graphics_photo_preview_failed": "(photo {n} couldn't be previewed)",
    "graphics_on_cover_caption": "**On the cover**",
    "graphics_use_as_cover_button": "Use as cover",
    "graphics_divider_heading": "#### 3. Divider design per section",
    "graphics_no_photos_info": (
        "No project photos uploaded (Upload Docs) -- sections default to the 'Solid colour' "
        "layout. Upload photos there to unlock photo-based layouts."
    ),
    "graphics_layout_label": "Layout",
    "graphics_photo_select_label": "Photo",
    "graphics_photo_option": "Photo {n}",
    "graphics_none_option": "(none)",
    "graphics_quote_select_label": "Quote",
    "graphics_quote_fallback_label": "Quote",
    "graphics_photo_title_label": "Photo title",
    "graphics_photo_title_placeholder": "e.g. Mangaweka Bridge",
    "graphics_photo_title_help": (
        "Shown bottom-right of the photo itself, not the coloured band. "
        "Only used when this section has a photo."
    ),
    "graphics_current_banner_caption": "Current banner for this section",
    "graphics_font_heading": "#### 3. Document font",
    "graphics_font_label": "Body & heading font",
    "graphics_font_help": "Applied to the exported Word document and the divider text.",
    "graphics_generate_heading": "#### 4. Generate",
    "graphics_generate_button": "Generate Graphics Package",
    "graphics_default_tender_pack_name": "Tender Response Pack",
    "graphics_generated_success": "Generated {banners} divider banner(s) and {recs} graphic recommendation(s).",
    "graphics_remaining_placeholders_heading": "#### Remaining placeholders overview",
    "graphics_col_graphic": "Graphic",
    "graphics_col_type": "Type",
    "graphics_col_placement": "Placement",
    "graphics_col_source_needed": "Source needed",
    "graphics_col_status": "Status",
    "graphics_weighting_dashboard_heading": "#### Evaluation weighting dashboard (generated)",

    # --- Tab 8: Team & Resourcing ---
    "team_subheader": "Team & Resourcing",
    "team_caption": (
        "Identify who staffs each discipline the brief calls for, plus the standing "
        "management roles every job carries, then generate a project org chart for the "
        "Key Personnel section. Names come from your uploaded CV library where possible, "
        "but you can also type in anyone you haven't uploaded a CV for."
    ),
    "team_run_analysis_first_info": "Run the Tender Analysis first -- the required disciplines come from the brief.",
    "team_load_names_button": "Load names from CV library",
    "team_load_names_help": "Upload a CV library (Upload Docs) and {ai_hint}.",
    "team_spinner_load_names": "Reading the whole CV library for names (a few seconds per batch)...",
    "team_names_found_success": "Found {n} name(s): {names}",
    "team_load_names_error": "Could not read names from the CV library",
    "team_available_names_caption": "Available names: {names}",
    "team_no_names_caption": "No names yet -- click 'Load names from CV library', or add people manually below.",
    "team_reupload_cv_tip_caption": (
        "💡 Tip: for the most complete and accurate list, re-upload your CV library files "
        "in Upload Docs -- each filename gives one person's full name instantly, "
        "with no AI guesswork. (Your loaded project kept the CV text but not the filenames.)"
    ),
    "team_management_roles_heading": "#### Management roles",
    "team_management_roles_caption": (
        "The client's PM sits at the top of the chart, then your Project Director and "
        "Project Manager -- those three are always there. Design Manager is optional: "
        "remove it with the ✕ if this commission doesn't have one, and it disappears from "
        "the chart and the pack entirely rather than sitting there as an unresolvable TBC."
    ),
    "team_add_role_button": "+ Add {role}",
    "team_role_off_chart_caption": (
        "{role} is currently off this project's chart. Adding it back "
        "restores an unassigned row here -- nothing else changes."
    ),
    "team_discipline_leads_heading": "#### Discipline leads",
    "team_discipline_leads_caption": (
        "One per discipline the brief requires. Add or remove disciplines as needed. "
        "Project Management isn't listed here -- it's staffed by the Project Manager role "
        "above -- but it still gets its own line in the fee estimate tab."
    ),
    "team_rescan_button": "Re-scan brief for disciplines",
    "team_rescan_help": "Needs the tender brief (Upload Docs) and {ai_hint}.",
    "team_spinner_rescan": "Re-reading the brief for every discipline the scope implies...",
    "team_disciplines_added_success": "Added: {names}",
    "team_no_new_disciplines_info": "No new disciplines found beyond what's already listed.",
    "team_rescan_failed_error": "Discipline re-scan failed",
    "team_rescan_caption": (
        "Reads the brief and infers disciplines the scope implies (environmental, "
        "constructability, rail, survey, etc.), even if they weren't named explicitly."
    ),
    "team_add_discipline_label": "Add a discipline",
    "team_add_discipline_placeholder": "e.g. Landscaping, Surveying, Constructability",
    "team_add_discipline_button": "Add discipline",
    "team_pm_not_separate_warning": (
        "Project Management is staffed by the Project Manager role above, "
        "not added here as a separate discipline. It still has its own line "
        "in the fee estimate tab."
    ),
    "team_add_no_cv_heading": "#### Add someone without a CV",
    "team_add_no_cv_caption": (
        "Names you type here become available in every dropdown above -- for people you "
        "want on the chart who don't have a CV uploaded."
    ),
    "team_person_name_label": "Person's name",
    "team_person_name_placeholder": "e.g. Jordan Lee",
    "team_add_name_button": "Add name",
    "team_key_personnel_heading": "#### Key personnel profile details",
    "team_key_personnel_caption": (
        "Feeds the numbered Key Personnel profiles in the exported pack -- Project Director, "
        "Project Manager, Design Manager (when the project has one), then discipline leads, "
        "in that order. Everything here "
        "is optional, user-entered text (never guessed): leave a field blank and the export "
        "shows a clearly marked placeholder instead."
    ),
    "team_overwrite_checkbox_label": "Overwrite existing values (re-read from CVs, replacing what's there)",
    "team_overwrite_checkbox_help": (
        "Off (default): only fills blank fields, protecting anything you've typed. "
        "On: re-reads every assigned person's CV and replaces the current values -- "
        "use this to fix wrong details left over from an earlier run."
    ),
    "team_fill_profile_button": "Fill profile fields from CVs",
    "team_fill_profile_help": "Assign people to roles above, upload a CV library (Upload Docs), and {ai_hint}.",
    "team_spinner_fill_profile": (
        "Reading each person's CV for registration status, experience and relevance "
        "(a few seconds per batch)..."
    ),
    "team_verb_updated": "Updated",
    "team_verb_filled": "Filled",
    "team_profile_filled_success": (
        "{verb} profile details for: {names}. Review before exporting -- fields left blank "
        "mean the CV didn't clearly state that fact."
    ),
    "team_profile_none_overwrite_info": (
        "No profile details found in the CVs to write -- the CVs don't clearly state these "
        "facts, or no assigned person could be matched to a CV file."
    ),
    "team_profile_none_info": (
        "No new profile details found -- existing entries were left as-is. Tick "
        "'Overwrite existing values' to re-read and replace them."
    ),
    "team_fill_profile_error": "Could not fill profile fields from CVs",
    "team_fill_profile_caption": (
        "Reads each assigned person's own CV file (in isolation, so no one's details get mixed up "
        "with another person's) for their registration/membership status and stated years of "
        "experience, and drafts an \"On this project, [name] will...\" line from their real background."
    ),
    "team_include_caption": (
        "**Include in proposal** -- tick which pen pics actually make it into the exported Key "
        "Personnel section. A full photo + write-up profile takes real page space, so when a "
        "page-limited section is full, untick anyone whose profile isn't essential to include -- "
        "they're still on the job (still in the org chart and fee build-up), they just won't get "
        "a dedicated profile. Whichever leadership roles this project carries are always "
        "recommended (project leadership), every other tick can be pre-set from an AI read of this project's "
        "scope below, and you can always override any tick by hand."
    ),
    "team_suggest_button": "Suggest which personnel to include (AI)",
    "team_suggest_help": "Assign roles above and {ai_hint}.",
    "team_spinner_suggest": "Reading this project's scope to judge which discipline profiles are worth including...",
    "team_suggest_applied_success": "Recommendations applied -- review the ticks and reasons below, then adjust by hand as needed.",
    "team_suggest_error": "Could not get AI recommendations",
    "team_include_checkbox_label": "Include in proposal",
    "team_refresh_button": "Refresh from CV",
    "team_refresh_help": "Assign a name, upload a CV library (Upload Docs), and {ai_hint}.",
    "team_spinner_refresh": "Re-reading {name}'s CV...",
    "team_refresh_success": "Refreshed {name} from their own CV file.",
    "team_refresh_thin_warning": (
        "Read {name}'s CV file but found no details to fill in. This usually means the "
        "text stored for their CV is incomplete (e.g. it was uploaded before a recent "
        "extraction fix) rather than the CV genuinely being empty -- try re-uploading "
        "{name}'s CV file in Upload Docs, then refresh again."
    ),
    "team_refresh_not_found_warning": (
        "Couldn't find/re-read {name}'s CV file -- check their filename "
        "derives to this exact name, or that their CV is in the library (Upload Docs)."
    ),
    "team_refresh_error": (
        "Could not refresh {name} from their CV -- please try again. If it keeps "
        "happening, email hello@civilproposals.com and we'll take a look."
    ),
    "team_ai_note_prefix": "AI note: {reason}",
    "team_stance_recommended": "Recommended",
    "team_stance_not_essential": "Not essential",
    "team_ai_note_stance_prefix": "AI note ({stance}): {reason}",
    "team_details_expander": "Details",
    "team_assign_name_first_caption": "Assign a name to this role above before adding profile details.",
    "team_qualification_label": "Qualification",
    "team_rpeq_label": "RPEQ / registration status",
    "team_years_experience_label": "Years of experience",
    "team_value_to_project_label": "On this project, {person} will...",
    "team_relevant_projects_label": "Relevant project experience (one per line)",
    "team_local_experience_label": "Local district experience (one per line)",
    "team_headshot_label": "Headshot (optional)",
    "team_org_chart_heading": "#### Project organisation chart",
    "team_org_chart_caption": (
        "{assigned} of {total} slots assigned. An unassigned "
        "slot shows as a red TBC on the chart -- a role you removed doesn't show at all."
    ),
    "team_chart_render_failed_caption": (
        "Couldn't draw the chart just now -- your team is unaffected. Try again, and if "
        "it keeps happening email hello@civilproposals.com."
    ),
    "team_use_chart_button": "Use this chart in the exported pack",
    "team_chart_saved_success": "Saved. This chart now appears in the Key Personnel area of the exported pack.",
    "team_chart_none_caption": "The exported pack has no org chart yet -- click to add this one.",
    "team_chart_stale_warning": (
        "**The exported pack still has the "
        "{style} chart.** Click to replace it with the one above."
    ),
    "team_chart_current_caption": "The exported pack has this chart.",

    # Part A2 -- Fee Estimate tabs (70_commercial_small.py, 71_commercial_large.py)

    # --- Tab 9: Fee Estimate -- Small Scope (letter) pack (70_commercial_small.py) ---
    "fee_small_tab_title_fees_program": "Fees & Program",
    "fee_small_tab_title_fee_estimate": "Fee Estimate",
    "fee_small_letter_caption": (
        "The **discipline fee build-up ($)** and **discipline fee split (%)** below are the "
        "two tables that actually go into the pack, along with the delivery program. The "
        "scope-item table is internal tracking only and is never exported."
    ),
    "fee_small_run_analysis_first": (
        "Run the Tender Analysis first -- the fee tables are built from the brief's own "
        "disciplines and scope items."
    ),
    "fee_small_run_tender_scope_items": "Run Tender Analysis to extract scope items first.",
    "fee_small_scope_items_heading": "#### Scope item fees",
    "fee_small_scope_seed_explanation": (
        "How the starting figures are seeded: each scope item gets a weight of "
        "1 + however many tasks it lists (so even a bare item with no tasks gets a "
        "base share), then the ballpark total below is split across items in "
        "proportion to that weight and rounded to the nearest $50. It's a rough "
        "task-count proxy for effort, not a real estimate -- edit every row before "
        "relying on it. This table is for your own internal tracking only; it is "
        "**not** included in the exported pack -- the discipline fee split further "
        "down (which mirrors the fee build-up table) is what's exported."
    ),
    "fee_small_ballpark_total_label": "Ballpark total project value ($, excl. GST)",
    "fee_small_seed_button": "Seed fee table from total",
    "fee_small_scope_note_default": "Enter fee -- no estimate seeded",
    "fee_small_col_scope_item_deliverable": "Scope item / deliverable",
    "fee_small_col_fee_amount": "Fee ($, excl. GST)",
    "fee_small_col_notes": "Notes",
    "fee_small_delete_row_hint": (
        "To delete a row: tick the checkbox on its left, then either press "
        "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
        "above the table."
    ),
    "fee_small_scope_ticked_stale": (
        "The total below is from the last time you ticked the box above -- "
        "tick it again to bring it up to date."
    ),
    "fee_small_scope_ticked_current": "The total below reflects the ticked data above.",
    "fee_small_scope_total": "**Total: ${total}**",
    "fee_small_scope_unpriced_warning": (
        "At least one scope item still has no fee entered -- the exported pack flags this "
        "in red until every row is priced."
    ),
    "fee_small_scope_pm_readded_info": "Project Management is a fixed line item and has been re-added.",
    "fee_small_discipline_heading": "#### First-pass discipline fee build-up",
    "fee_small_discipline_caption": (
        "Your own first-pass fee per discipline, built from hours x rate -- the same "
        "build-up as the Large Scope pack's Fee Estimate tab, and the same figures if "
        "you switch a project between pack sizes. The table is seeded from the "
        "disciplines the brief calls for, plus Project Management (always included). "
        "Enter total hours and an hourly rate per discipline -- the Total column is "
        "calculated automatically. A per-discipline total (not the hours/rates "
        "themselves) is included in the exported pack's Fees section."
    ),
    "fee_small_rate_prefilled": (
        "Filled the rate on {n} discipline(s) from your Firm Profile rate card. Hours "
        "are still yours to enter."
    ),
    "fee_small_col_discipline": "Discipline",
    "fee_small_col_total_hours": "Total hours",
    "fee_small_col_rate_per_hour": "Rate per hour ($)",
    "fee_small_col_total_amount": "Total ($, excl. GST)",
    "fee_small_col_total_amount_help": "Calculated automatically -- total hours x rate per hour.",
    "fee_small_col_note": "Note",
    "fee_small_ticked_stale": (
        "Totals, the chart, and the Excel export below are from the last time "
        "you ticked the box above -- tick it again to bring them up to date."
    ),
    "fee_small_ticked_current": "Totals, the chart, and the Excel export below reflect the ticked data above.",
    "fee_small_disc_total_label": "**Discipline fee total: ${value}**",
    "fee_small_avg_rate_label": "**Average rate across project: {value}**",
    "fee_small_avg_rate_unset": "-- (enter hours to calculate)",
    "fee_small_pm_readded_info": "Project Management is always part of the fee build-up and has been re-added.",
    "fee_small_export_excel_button": "Export to Excel",
    "fee_small_export_hours_help": (
        "Includes a Total row and the average rate across the project (total fee / total hours)."
    ),
    "fee_small_export_unavailable_caption": (
        "Excel export isn't available right now -- please email hello@civilproposals.com if "
        "this keeps happening."
    ),
    "fee_small_scope_expander_title": "Scope item fees (internal tracking only -- not exported)",
    "fee_small_delivery_program_heading": "#### Delivery program",
    "fee_small_num_weeks_label": "Number of weeks",
    "fee_small_start_date_label": "Anticipated start date (optional)",
    "fee_small_start_date_help": (
        "Your own expected start, not something read from the brief. Set it "
        "and every week header becomes a real date (\"Wk 1 - 6 Oct\") in the "
        "program table and the program PowerPoint. Leave it blank to keep "
        "plain week numbers."
    ),
    "fee_small_generate_program_button": "Generate default program",
    "fee_small_col_scope_item": "Scope item",
    "fee_small_program_empty_info": (
        "Click 'Generate default program' for an editable starting grid, sized by how many "
        "tasks each scope item lists -- adjust the weeks freely afterwards."
    ),
    "fee_small_pct_split_expander": "Discipline fee split (%)",
    "fee_small_pct_split_caption": (
        "Its discipline list always matches the discipline fee build-up table above "
        "-- add or remove disciplines up there, not here."
    ),
    "fee_small_total_fee_label": (
        "Total project fee ($, excl. GST) -- used to convert Fee % into a $ figure below"
    ),
    "fee_small_total_fee_help": (
        "Starts prepopulated from the discipline fee build-up total above, then "
        "stays independently editable -- change it here to use a different total "
        "for this % split's $ column, Excel export, and chart only. Doesn't change "
        "the build-up table itself."
    ),
    "fee_small_reset_pct_button": "Reset % from discipline fee build-up",
    "fee_small_benchmark_button": "Estimate from bundled benchmarks",
    "fee_small_enter_hours_first_warning": "Enter hours and rates in the discipline fee build-up table above first.",
    "fee_small_ai_spinner": "Asking the AI how a fee like this typically divides...",
    "fee_small_col_fee_pct": "Fee %",
    "fee_small_col_indicative_amount": "Indicative $",
    "fee_small_col_indicative_amount_help": "Fee % x the total project fee entered above -- recalculated automatically.",
    "fee_small_col_typical_range": "Typical range",
    "fee_small_col_typical_range_help": (
        "The band the source actually supports -- the single Fee % is its "
        "mid-point. Blank where the source gave a point estimate "
        "rather than a range."
    ),
    "fee_small_col_confidence": "Confidence",
    "fee_small_col_source": "Source",
    "fee_small_source_from_buildup": "From discipline fee build-up",
    "fee_small_confidence_user_set": "User-set",
    "fee_small_note_always_included": "Always included -- re-added automatically",
    "fee_small_pie_title_discipline_buildup": "Fee distribution by discipline (hours x rate)",
    "fee_small_pie_title_pct_split": "Discipline fee split",
    "fee_small_pct_total_caption": "Total: {pct}% (doesn't need to sum to exactly 100%).",

    # --- Tab 9: Fee Estimate -- Large Scope pack (71_commercial_large.py) ---
    "fee_large_run_analysis_first": (
        "Run the Tender Analysis first -- the fee tables are built from the brief's own "
        "disciplines and scope items."
    ),
    "fee_large_discipline_heading": "#### First-pass discipline fee build-up",
    "fee_large_discipline_caption": (
        "Your own first-pass fee per discipline, built from hours x rate. The table is "
        "seeded from the disciplines the brief calls for, plus Project Management (always "
        "included). Enter total hours and an hourly rate per discipline -- the Total column "
        "is calculated automatically, not typed in directly. Add or remove rows as needed -- "
        "these are your figures, not an AI estimate."
    ),
    "fee_large_rate_prefilled": (
        "Filled the rate on {n} discipline(s) from your Firm Profile rate card. Hours are "
        "still yours to enter."
    ),
    "fee_large_col_discipline": "Discipline",
    "fee_large_col_total_hours": "Total hours",
    "fee_large_col_rate_per_hour": "Rate per hour ($)",
    "fee_large_col_total_amount": "Total ($, excl. GST)",
    "fee_large_col_total_amount_help": "Calculated automatically -- total hours x rate per hour.",
    "fee_large_col_note": "Note",
    "fee_large_delete_row_hint": (
        "To delete a row: tick the checkbox on its left, then either press "
        "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
        "above the table."
    ),
    "fee_large_ticked_stale": (
        "Totals, the chart, and the Excel export below are from the last time "
        "you ticked the box above -- tick it again to bring them up to date."
    ),
    "fee_large_ticked_current": "Totals, the chart, and the Excel export below reflect the ticked data above.",
    "fee_large_disc_total_label": "**Discipline fee total: ${value}**",
    "fee_large_avg_rate_label": "**Average rate across project: {value}**",
    "fee_large_avg_rate_unset": "-- (enter hours to calculate)",
    "fee_large_pm_readded_info": "Project Management is always part of the fee build-up and has been re-added.",
    "fee_large_export_excel_button": "Export to Excel",
    "fee_large_export_hours_help": (
        "Includes a Total row and the average rate across the project (total fee / total hours)."
    ),
    "fee_large_export_unavailable_caption": (
        "Excel export isn't available right now -- please email hello@civilproposals.com if "
        "this keeps happening."
    ),
    "fee_large_hours_chart_hint_caption": (
        "Enter hours and a rate for at least one discipline above to see the fee "
        "distribution chart."
    ),
    "fee_large_scope_heading": "#### Scope item / deliverable fee build-up",
    "fee_large_scope_run_tender_info": "Run Tender Analysis to extract scope items and deliverables first.",
    "fee_large_scope_caption": (
        "Prepopulated with the scope items/deliverables extracted from the brief, "
        "one row each, so there's a real starting list to price rather than a blank "
        "table -- edit, rename, delete, or add rows freely; nothing here is exported "
        "automatically (the discipline build-up above is what feeds the pack)."
    ),
    "fee_large_scope_note_default": "Enter fee -- no estimate seeded",
    "fee_large_col_scope_item_deliverable": "Scope item / deliverable",
    "fee_large_col_fee_amount": "Fee ($, excl. GST)",
    "fee_large_col_notes": "Notes",
    "fee_large_scope_ticked_stale": (
        "The total below is from the last time you ticked the box above -- "
        "tick it again to bring it up to date."
    ),
    "fee_large_scope_ticked_current": "The total below reflects the ticked data above.",
    "fee_large_scope_pm_readded_info": "Project Management is a fixed line item and has been re-added.",
    "fee_large_scope_total_label": "**Total: ${total}**",
    "fee_large_delivery_program_heading": "#### Delivery program",
    "fee_large_delivery_program_caption": (
        "A starting delivery schedule across your scope items. Unlike the Small Scope "
        "pack, this isn't embedded in the DOCX -- download it as an editable PowerPoint "
        "table from the Export Pack tab instead, to paste into a program/methodology slide."
    ),
    "fee_large_num_weeks_label": "Number of weeks",
    "fee_large_start_date_label": "Anticipated start date (optional)",
    "fee_large_start_date_help": (
        "Your own expected start, not something read from the brief. Set it "
        "and every week header becomes a real date (\"Wk 1 - 6 Oct\") in the "
        "program table and the program PowerPoint. Leave it blank to keep "
        "plain week numbers."
    ),
    "fee_large_generate_program_button": "Generate default program",
    "fee_large_col_scope_item": "Scope item",
    "fee_large_program_empty_info": (
        "Click 'Generate default program' for an editable starting grid, sized by how many "
        "tasks each scope item lists -- adjust the weeks freely afterwards."
    ),
    "fee_large_pct_heading": "#### Indicative fee split by discipline",
    "fee_large_pct_caption": (
        "Its discipline list always matches the discipline fee build-up table above -- add "
        "or remove disciplines up there, not here. Fee % is directly editable below; reset "
        "it from the build-up's own $ split, or seed it from the benchmark/AI buttons "
        "(remapped onto the build-up's discipline list either way)."
    ),
    "fee_large_total_fee_label": "Total project fee ($, excl. GST) -- optional",
    "fee_large_total_fee_help": (
        "Starts prepopulated from the discipline fee build-up total above, then stays "
        "independently editable -- change it here to use a different total for this "
        "split's $ column, Excel export, and chart only. Doesn't change the build-up "
        "table itself."
    ),
    "fee_large_reset_pct_button": "Reset % from discipline fee build-up",
    "fee_large_benchmark_button": "Estimate from bundled benchmarks",
    "fee_large_enter_hours_first_warning": "Enter hours and rates in the discipline fee build-up table above first.",
    "fee_large_ai_spinner": "Asking the AI how a fee like this typically divides...",
    "fee_large_col_fee_pct": "Fee %",
    "fee_large_col_indicative_amount": "Indicative $",
    "fee_large_col_indicative_amount_help": (
        "Fee % x the manual total above (if entered), else x the discipline fee build-up total."
    ),
    "fee_large_col_typical_range": "Typical range",
    "fee_large_col_typical_range_help": (
        "The band the source actually supports -- the single Fee % is its "
        "mid-point. Blank where the source gave a point estimate "
        "rather than a range."
    ),
    "fee_large_col_confidence": "Confidence",
    "fee_large_col_source": "Source",
    "fee_large_source_from_buildup": "From discipline fee build-up",
    "fee_large_confidence_user_set": "User-set",
    "fee_large_note_always_included": "Always included -- re-added automatically",
    "fee_large_pie_title_discipline_buildup": "Fee distribution by discipline (hours x rate)",
    "fee_large_pie_title_pct_split": "Indicative fee split by discipline",
    "fee_large_pct_total_caption": "Total: {pct}% (doesn't need to sum to exactly 100%).",

    # Part A2 -- Project Setup / Upload Documents tabs, plus Tender Analysis
    # stragglers (30_setup_upload_analysis.py)

    # --- Tab 1: Project Setup ---
    "setup_subheader": "Project Setup",
    "setup_caption": "Basic project details -- used throughout the workflow and on the cover page of the exported pack.",
    "setup_format_heading": "**Proposal format**",
    "setup_format_caption": (
        "The tool is agnostic to what the project actually is -- scope, team, and fees always "
        "come from what you upload, never from the format you pick. This only changes the shape "
        "of the output: a bound Large Scope pack with named sections and page limits, or a "
        "shorter Small Scope pack with the same sections just leaner (typical for a small "
        "brief, or an email-based request from the client)."
    ),
    "setup_format_select_label": "Which does this pursuit need?",
    "setup_project_name_label": "Project name",
    "setup_client_name_label": "Client name",
    "setup_tender_name_label": "Tender / EOI name",
    "setup_submission_date_label": "Submission date",
    "setup_submission_date_placeholder": "e.g. 14 July 2026",
    "setup_bidder_name_label": "Bidder / company name",
    "setup_project_type_label": "Project type",
    "setup_proposal_theme_label": "Proposal theme",
    "setup_autosave_caption": "Saved as you type -- there's no separate save step.",
    "setup_date_mismatch_warning": (
        "**Submission date mismatch.** You've entered **{typed_date}**, but the brief's "
        "own stated date reads **{brief_date}**. The date you type here is the one "
        "printed on the cover -- check which is right before exporting."
    ),
    "setup_sender_name_label": "Sender name",
    "setup_sender_name_placeholder": "e.g. Jane Smith",
    "setup_sender_title_label": "Sender title",
    "setup_sender_title_placeholder": "e.g. Project Director",
    "setup_sender_phone_label": "Sender phone",
    "setup_sender_email_label": "Sender email",
    "setup_sender_address_label": "Registered / business address",
    "setup_sender_address_placeholder": "e.g. Level 3, 100 Example St, Brisbane QLD 4000",
    "setup_sender_address_help": (
        "Used to fill the address labels on the client's returnable schedules. "
        "It is deliberately NOT added to the letter sign-off block, which stays "
        "name/title/phone/email by design."
    ),
    "setup_signoff_heading": "#### Sign-off details",
    "setup_signoff_caption": (
        "Who signs this pack off -- shown in the closing \"Regards\" block at the end of "
        "the document. The cover page and footer already carry the project/client/bidder "
        "details entered above, so nothing else is needed here. The address is used only "
        "when filling the client's returnable schedules."
    ),
    "setup_contact_expander": "Contact / signatory details (optional)",
    "setup_contact_expander_caption": (
        "Not used in the Large Scope document itself. These are the values the "
        "returnable-schedule filler puts into the client's own forms against "
        "labels like \"Contact Person\", \"Telephone\", \"Email\" and "
        "\"Registered Office\" -- leave them blank and those labels get a "
        "[TO BE COMPLETED] placeholder instead."
    ),

    # --- Tab 2: Upload Documents ---
    "upload_subheader": "Upload Documents",
    "upload_caption": "The tender brief is required. Everything else is optional but strongly improves draft quality.",
    "upload_brief_intro": (
        "**Tender brief (required)** -- PDF, DOCX, TXT, or a whole tender-package **ZIP**. "
        "Sometimes a brief arrives as several separate documents (e.g. the main RFT plus "
        "addenda, schedules, or annexures) -- upload all of them here and they'll be combined "
        "into one brief. A ZIP gets unpacked and sorted automatically: brief + addenda go into "
        "the analysis, returnable schedules are kept aside for filling, drawings are set aside. "
        "If you've already highlighted/commented on any document while reading, upload that "
        "marked-up copy -- your notes get read too."
    ),
    "upload_tender_files_label": "Upload the tender document(s)",
    "upload_extracting_single": "Extracting text...",
    "upload_extracting_multi": "Extracting text from {n} files...",
    "upload_zip_not_ingested_reason": (
        "**Not ingested -- trial limit.** The free trial analyses up to "
        "{trial_limit} brief/addendum file(s) per upload; this one wasn't "
        "included in the analysis. Paid accounts go up to {paid_limit}. "
        "Original filing: {original_reason}"
    ),
    "upload_zip_skipped_summary": (
        "{n} file(s) inside the uploaded package(s) weren't ingested -- "
        "the free trial analyses up to {trial_limit} brief/addendum files total "
        "(see the breakdown below for which). Paid accounts go up to {paid_limit}."
    ),
    "upload_no_brief_found_error": (
        "No brief or addenda were found in that package (see the breakdown below "
        "for how each file was filed). Upload the brief itself -- as a PDF/DOCX, "
        "or in another ZIP -- to run the analysis."
    ),
    "upload_breakdown_expander": "Tender package breakdown -- how each file was filed",
    "upload_col_file": "File",
    "upload_col_filed_as": "Filed as",
    "upload_col_why_what_to_do": "Why / what to do",
    "upload_schedules_kept_aside_info": (
        "{n} returnable schedule(s) were kept aside -- see the "
        "**Returnable Schedules** section on the Export Pack tab to fill them "
        "from this project's data."
    ),
    "upload_drawings_set_aside_caption": "{n} drawing/image file(s) were set aside -- drawings aren't used in the text analysis.",
    "upload_unreadable_markdown": (
        "{n} file(s) couldn't be read -- each row above says why and how to fix it, "
        "or [email us the file]({mailto}) and we'll process it for you."
    ),
    "upload_ocr_warning": (
        "Parts of this brief were read with text recognition (OCR) from scanned "
        "pages. {ocr_tag}: double-check numbers, dates "
        "and names against the original document."
    ),
    "upload_brief_loaded_success": (
        "Tender brief loaded -- {chars} characters{pages_part}. Found {headings} candidate "
        "headings, {tables} table(s), and {annotations} existing annotation(s)."
    ),
    "upload_brief_loaded_pages_part": " across {pages} pages",
    "upload_clear_all_button": "Clear all",
    "upload_clear_tender_help": "Remove the uploaded tender document(s) and start over",
    "upload_retained_caption": "↩︎ Retained from your saved project (or an earlier upload). Re-upload only if the brief has changed.",
    "upload_annotations_expander": "Preview {n} annotation(s) found in the PDF(s)",
    "upload_annotation_highlight_only": "(highlight only)",
    "upload_company_material_heading": "**Optional company material** -- upload as many files as you like per category. Multiple files per category are combined.",
    "upload_material_uploader_help": (
        "Uploading adds/updates these files; anything already stored for this category "
        "is kept, not replaced. Use 'Clear all' below to wipe the category and start over."
    ),
    "upload_material_limit_warning": (
        "The {tier} plan handles up to {limit:,} {label} "
        "for this project -- {existing} already stored, so "
        "{added_clause} and the rest left out: {dropped}."
    ),
    "upload_material_added_some": "{kept} of the {total} newly selected file(s) were added",
    "upload_material_added_none": "none of the newly selected file(s) were added",
    "upload_extracting_category_spinner": "Extracting {label}...",
    "upload_prev_proposals_caption": (
        "📁 To pull in a proposal you've already archived, use the 'Add as reference to "
        "project' button in the Proposal Library popover (top banner) instead of "
        "re-uploading it here."
    ),
    "upload_project_references_caption": (
        "📁 To pull in a firm reference project you've uploaded to the Project Reference "
        "Library, use its 'Add to project references' button in the top banner instead "
        "of re-uploading it here."
    ),
    "upload_material_file_count_bit": "{n} file(s), ",
    "upload_material_stored_caption": "✅ {label}: {count_bit}{chars:,} characters stored.",
    "upload_clear_category_help": "Remove all {label} and start over",
    "upload_photos_label": "Project photos",
    "upload_photos_loaded_caption": "✅ {n} project photo(s) loaded -- the first is the cover image{retained}.",
    "upload_retained_suffix": " (retained from saved project)",
    "upload_clear_photos_help": "Remove all project photos and start over",
    "upload_branding_label": "Company branding / image library",
    "upload_branding_loaded_caption": "✅ {n} branding image(s) loaded{retained}.",
    "upload_clear_branding_help": "Remove all branding images and start over",
    "upload_refprojects_heading": "#### Reference projects (Relevant Experience section)",
    "upload_refprojects_caption": (
        "Draft, then review and edit, the distinct past projects the exported pack will show in "
        "Relevant Experience -- revised for consistent tone and relevance to THIS tender, not the "
        "raw uploaded text pasted in. Add a photo per project if you have one, and confirm which "
        "of your key personnel worked on each -- that feeds the Section 2 x Section 3 "
        "cross-reference table automatically. Best done here, early, so it's ready before Export."
    ),
    "upload_refprojects_upload_first_info": "Upload 'Project references' material above to draft reference projects from it, or add one manually below.",
    "upload_refprojects_draft_hint_info": (
        "Material uploaded and read. Click **Draft reference projects from uploaded material** "
        "below to have the AI turn it into the individual project entries shown further down -- "
        "uploading alone doesn't create them yet."
    ),
    "upload_draft_refprojects_button": "Draft reference projects from uploaded material",
    "upload_draft_refprojects_help": "Upload 'Project references' material above and {ai_hint}.",
    "upload_draft_refprojects_spinner": "Reading project reference material and drafting revised, relevance-led entries...",
    "upload_refprojects_drafted_success": "Drafted {n} reference project(s). Review and edit every field below before export.",
    "upload_refprojects_no_analysis_info": "Tender Analysis hasn't run yet -- re-run this once it has, so relevance can be tailored to the actual brief.",
    "upload_refprojects_drafting_failed_error": "Reference project drafting failed",
    "upload_refproject_untitled": "Reference project {n}",
    "upload_ref_project_title_label": "Project title",
    "upload_ref_client_label": "Client",
    "upload_ref_description_label": "Description (revised for consistency/relevance)",
    "upload_ref_relevance_label": "Relevance to this tender",
    "upload_ref_personnel_label": "Key personnel who worked on this project",
    "upload_ref_photo_label": "Project photo (optional)",
    "upload_ref_remove_button": "Remove this reference project",
    "upload_add_ref_manual_heading": "**Add a reference project manually**",
    "upload_add_ref_button": "Add reference project",

    # --- Tab 3: Tender Analysis (stragglers not covered by the earlier Part B2 pass) ---
    "analysis_subheader": "Tender Analysis",
    "analysis_caption": "Extracts scope, objectives, mandatory requirements, evaluation criteria, weightings, page limits, deliverables, forms, and risks from the uploaded brief.",
    "analysis_need_project_name_info": "Enter a project name on the Project Setup tab before running Tender Analysis.",
    "analysis_need_brief_and_ai_info": "Upload a tender brief (Upload Docs) and {ai_hint} to run analysis.",
    "analysis_past_due_warning": (
        "Your payment is past due, and you've also used this cycle's "
        "{limit} included bid(s). Update your payment method to keep "
        "your subscription active, or buy a pay-as-you-go bid to keep going right now."
    ),
    "analysis_subscribed_limit_warning": (
        "You've used all {limit} bid(s) included in this billing "
        "cycle's Monthly plan. Buy a pay-as-you-go bid to keep going now, or wait for renewal."
    ),
    "analysis_trial_exhausted_warning": (
        "You've used all {limit} free trial bid(s). "
        "Upgrade to keep going -- pay per bid, or subscribe monthly. See pricing on the homepage."
    ),
    "analysis_subscription_bids_caption": "This will use 1 of your {remaining} remaining bid(s) in this billing cycle.",
    "analysis_payg_caption": "This will use 1 pay-as-you-go bid credit (you have {credits} left).",
    "analysis_trial_remaining_caption": "This will use your {remaining} free trial bid -- make sure this is the right document first.",
    "analysis_run_button": "Run Tender Analysis",
    "analysis_progress_text": "Analysing...",
    "analysis_progress_detail": "Analysing part {done}/{total}...",
    "analysis_queued_text": "Queued for analysis...",
    "analysis_complete_success": "Tender analysis complete.",
    "analysis_failed_error": "Analysis failed",
    "analysis_checkout_failed_error": "Couldn't start checkout",
    "analysis_ocr_warning": (
        "This analysis is based on text read with OCR from scanned pages. "
        "{ocr_tag}: double-check extracted requirements, "
        "dates, and numbers against the original document."
    ),
    "analysis_project_scope_heading": "#### Project scope",
    "analysis_client_objectives_heading": "#### Client objectives",
    "analysis_mandatory_requirements_heading": "#### Mandatory requirements",
    "analysis_deliverables_heading": "#### Deliverables",
    "analysis_not_extracted": "_not extracted_",
    "analysis_none_extracted": "_none extracted_",
    "analysis_submission_date_label": "**Submission date:** {text}",
    "analysis_total_page_limit_label": "**Total page limit:** {text}",
    "analysis_fee_cap_label": "**Fee cap:** {text}",
    "analysis_not_stated": "_not stated_",
    "analysis_uses_named_criteria_label": "**Uses named selection criteria (SC1/SC2 style):** {answer}",
    "analysis_yes": "Yes",
    "analysis_no": "No",
    "analysis_required_forms_heading": "#### Required forms / schedules",
    "analysis_evaluation_criteria_heading": "#### Evaluation / selection criteria",
    "analysis_col_code": "Code",
    "analysis_col_name": "Name",
    "analysis_col_weighting": "Weighting",
    "analysis_mandatory_gate": "Mandatory gate",
    "analysis_col_page_limit": "Page limit",
    "analysis_col_format_rules": "Format rules",
    "analysis_no_evaluation_criteria": "_No evaluation criteria extracted._",
    "analysis_flagged_items_heading": "#### Items you flagged via annotations",
    "analysis_risks_heading": "#### Risks noted in the brief",
    "analysis_extraction_warnings_prefix": "Extraction warnings -- verify these manually against the brief:\n\n",

    # Part A2 -- Export Pack tab (80_export.py)
    "export_subheader": "Export Pack",
    "export_continue_to_payment_button": "Continue to payment",
    "export_readiness_expander": "⚠️ {n} thing(s) still outstanding before this pack is ready",
    "export_readiness_item": "- **{label}** -- go to *{where}*",
    "export_readiness_caption": (
        "You can export anyway -- everything outstanding shows as a red placeholder in "
        "the document, so nothing is silently missing."
    ),
    "export_readiness_all_done_success": "Everything this pack needs has been filled in.",
    "export_letter_intro_caption": "Generates the first-pass Small Scope Proposal Response Pack. Review the checklist page inside before this goes anywhere near a real submission.",
    "export_generate_structure_first_info": "Generate the Proposal Structure first.",
    "export_letter_structure_stale_warning": (
        "The Proposal format (Project Setup) was changed after these sections were generated -- "
        "go to Structure and click **Generate Proposal Structure** again first, or the "
        "exported pack will be missing the Introduction/Methodology drafts even if you "
        "already ran drafting."
    ),
    "export_generate_letter_docx_button": "Generate Small Scope Pack DOCX",
    "export_assembling_spinner": "Assembling document...",
    "export_document_generated_success": "Document generated.",
    "export_formal_intro_caption": "Generates the first-pass DOCX response pack. Review the checklist inside the document before this goes anywhere near a real submission.",
    "export_formal_generate_structure_first_info": "Generate the Proposal Structure first. Drafts, graphics, and fee estimate are optional but recommended before exporting.",
    "export_formal_structure_stale_warning": (
        "The Proposal format (Project Setup) was changed after these sections were generated -- "
        "go to Structure and click **Generate Proposal Structure** again first, or the "
        "exported pack may not match what you drafted."
    ),
    "export_generate_docx_button": "Generate DOCX",
    "export_stale_files_warning": (
        "**These files were generated before your latest edits.** Downloading now gives "
        "you the older pack. Generate again to pick up the changes."
    ),
    "export_download_docx_button": "Download DOCX",
    "export_download_orgchart_button": "Download Org Chart (PPTX)",
    "export_orgchart_caption": (
        "Built from this project's resourcing plan -- each discipline's lead plus "
        "anyone added under them, with red \"TBC\" for unassigned roles and "
        "[CONFIRM TITLE] where a support member has no title yet. The client's own "
        "PM and subconsultant firms aren't shown -- the app holds no data for them. "
        "Fill in the gaps, then paste the finished chart over the first-pass image "
        "in the DOCX."
    ),
    "export_orgchart_build_failed_caption": "Couldn't build the org chart this time -- the DOCX download above is unaffected.",
    "export_download_methodology_button": "Download Methodology Table (PPTX)",
    "export_methodology_caption_has_stages": (
        "Built from the design stages you reviewed on the Draft Responses step -- "
        "every column is real content, with red TBC where the brief didn't support a "
        "cell. Without a reviewed grid it falls back to the generic four-stage layout. "
        "Paste the finished table into the proposal where the red placeholder note "
        "marks its place."
    ),
    "export_methodology_caption_no_stages": (
        "No design stages reviewed yet, so this is the generic four-stage fallback: "
        "column 2 from your real scope items, the rest red placeholders. Run **Draft "
        "methodology stages** on the Draft Responses step to fill all four columns."
    ),
    "export_methodology_build_failed_caption": "Couldn't build the methodology table this time -- the DOCX download above is unaffected.",
    "export_download_program_button": "Download Program (PPTX)",
    "export_program_caption": (
        "Built from the delivery program entered in the Fee Estimate tab -- shows a red "
        "placeholder if no program has been generated there yet."
    ),
    "export_program_build_failed_caption": "Couldn't build the program this time -- the DOCX download above is unaffected.",
    "export_download_tendersummary_button": "Download Tender Summary (DOCX)",
    "export_tendersummary_caption": (
        "Companion internal document -- guidance on the brief's main requirements, plus "
        "the compliance matrix, gap analysis, review checklist, and user input list where "
        "generated. Not part of the proposal itself."
    ),
    "export_tendersummary_pending_caption": "Tender Summary document will be generated alongside the DOCX above.",
    "export_library_heading": "#### Proposal Library",
    "export_library_caption": (
        "Archive this generated proposal into the Proposal Library "
        "(library/{project_type}/) for reuse later -- "
        "as a 'Previous proposals' reference in Upload Docs, or to browse and "
        "download from the 'Proposal Library' button in the top banner. Nothing is archived automatically; click below "
        "whenever you're happy with this version. Only the proposal DOCX itself is archived, "
        "not the Tender Summary or the PowerPoint companions above."
    ),
    "export_library_project_type_placeholder": "<project type>",
    "export_archive_button": "Archive to Library",
    "export_archive_success": "Archived to the library under '{project_type}' as {filename}.",
    "export_archive_failed_error": "Couldn't archive to the library",
    "export_schedules_heading": "#### Returnable schedules",
    "export_schedules_caption": (
        "Fill the client's own response forms from this project's data -- company and contact "
        "details, key personnel, reference projects, fee build-up -- inside their original "
        "document, formatting intact. Anything the project doesn't actually know is left as a "
        "clearly-marked **{placeholder_prefix}: ...]** placeholder, never "
        "a guess. Schedules found in an uploaded tender-package ZIP appear here automatically; "
        "you can also upload more below."
    ),
    "export_add_schedules_label": "Add schedules to fill (DOCX or XLSX)",
    "export_schedule_not_form_info": (
        "'{name}' doesn't look like a response form (its tables are already "
        "full, or it has none) -- it'll still be attempted, but check the "
        "result carefully."
    ),
    "export_no_schedules_caption": "No schedules yet -- upload a tender-package ZIP in Upload Docs, or add files above.",
    "export_schedules_ready_prefix": "**{n} schedule(s) ready:** ",
    "export_remove_file_label": "Remove a file",
    "export_keep_all_option": "(keep all)",
    "export_remove_button": "Remove",
    "export_fill_schedules_button": "Fill schedules from this project's data",
    "export_filling_spinner": "Filling {n} schedule(s)...",
    "export_download_filled_button": "Download filled copy",
    "export_schedule_fill_summary_caption": (
        "{filled} field(s) filled from project data, "
        "{placeholdered} left as clearly-marked placeholders to complete. "
        "Review everything before submitting -- this is a first pass, and the "
        "placeholders are deliberate: the project doesn't know those answers."
    ),
    "export_schedule_detail_expander": "What was filled / placeholdered in {filename}",
    "export_filled_heading": "**Filled from project data:**",
    "export_col_where": "Where",
    "export_col_field": "Field",
    "export_col_value": "Value",
    "export_placeholdered_heading": "**Left as placeholders (complete before submission):**",

    # Part A2 -- limits.py (function-returned strings; module-level string
    # constants themselves stay hardcoded English -- see the TODO comments
    # next to each in limits.py)
    "limits_upgrade_clause": "Paid accounts go up to {paid_limit:,} {label}.",
    "limits_tier_paid": "paid",
    "limits_tier_trial": "free trial",
    "limits_count_limit_message": (
        "The {tier} plan handles up to {limit:,} {label} at a time -- we've used the first "
        "{limit:,} and left out: {shown}."
    ),
    "limits_tender_page_cap_message": (
        "This brief runs to about {page_count:,} pages, and the free trial analyses up to "
        "{trial_limit:,}. Trim the package to the essentials (standard conditions of contract "
        "and similar boilerplate are usually safe to drop), or upgrade to a paid plan "
        "(up to {paid_limit:,} pages) to run this brief as-is."
    ),
    "limits_trial_spend_ceiling_message": "Your free trial's AI allowance is used up -- upgrade to keep going; your work is saved.",
    "limits_ai_rate_limit_trial": "Give it a few minutes -- the trial has a fair-use speed limit.",
    "limits_ai_rate_limit_paid": "Give it a few minutes -- there's a brief fair-use speed limit.",

    # Part A3 -- Project Setup tab, output_language selector (language of the
    # AI-GENERATED proposal content, separate from the app's own UI language)
    "setup_output_language_label": "Output language for generated content",
    "setup_output_language_help": (
        "Language the AI-generated proposal content (drafts, executive summary, and "
        "similar sections) is written in -- this does not change the app's own interface "
        "language, which is the separate switcher in the sidebar."
    ),
}

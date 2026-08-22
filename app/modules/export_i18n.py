# modules/export_i18n.py -- static-scaffolding translations for EXPORTED
# documents (DOCX proposal packs), Part A3 of the EN/ES dual-language brief.
#
# Deliberately separate from modules/i18n.py and modules/translations/en.py|
# es.py:
#   - modules/i18n.py drives the app's own on-screen UI language, chosen per
#     browser session (st.session_state["_lang"]) and persisted to the
#     signed-in user's account. It answers "what language does this person
#     see the Streamlit app in".
#   - export_i18n (this module) drives the STATIC scaffolding text baked
#     into a generated DOCX -- major section headings like "Executive
#     Summary" or "Compliance Matrix" -- chosen per PROJECT
#     (st.session_state["output_language"], set on Project Setup) and baked
#     into that project's exported files. It answers "what language does
#     THIS proposal pack come out in", completely independent of what
#     language the person building it is currently viewing the app in.
#
# The two are never coupled: a Spanish-speaking user could easily be
# preparing an English-language tender pack (or vice versa), so mixing this
# catalog with modules/i18n.py's would silently force one axis to follow the
# other. Kept as one small file (not a translations/ subpackage) because the
# catalog here only needs to cover major document headings, not the whole
# app's UI strings.
from __future__ import annotations

# English is the default/fallback catalog -- every key must exist here.
_EN: dict[str, str] = {
    # -- Shared / used by more than one document --
    "heading_toc": "Table of Contents",
    "heading_executive_summary": "Executive summary",
    "heading_risks_noted_in_brief": "Risks noted in the brief",
    "heading_fee_summary": "Fee summary",
    "heading_fee_by_scope_item": "Fee by scope item",
    "heading_cash_flow": "Cash flow",
    "heading_contractual_arrangements": "Contractual arrangements",
    "heading_local_benefits": "Local benefits",
    "heading_review_checklist": "Review Checklist",

    # -- Large Scope pack (build_docx) --
    "heading_page_allocation_plan": "Page Allocation Plan",
    "heading_fee_estimate_by_discipline": "Indicative Fee Estimate by Discipline",
    "heading_org_chart": "Project organisation chart",
    "heading_key_personnel_profiles": "Key personnel profiles",
    "heading_methodology_summary": "Methodology summary",
    "heading_relevant_experience_compact": "Relevant project experience",
    "heading_relevant_experience": "Our relevant project experience",
    "heading_personnel_experience_matrix": "Key personnel x relevant experience",
    "heading_relationship_management": "Our approach to relationship management",

    # -- Small Scope pack (build_letter_docx) --
    "heading_letter_intro": "1. Introduction",
    "heading_letter_scope_of_work": "2. Scope of Work",
    "heading_letter_methodology": "3. Methodology and Deliverables",
    "heading_letter_team": "4. Project Team",
    "heading_letter_fees": "5. Fees",
    "heading_letter_program": "6. Program",
    "heading_letter_assumptions": "7. Assumptions and Clarifications",
    "heading_letter_terms": "8. Terms of Engagement",
    "heading_risks_mitigation": "Risks and mitigation",
    "heading_discipline_fee_buildup": "Discipline fee build-up",
    "heading_fee_split_by_discipline": "Indicative fee split by discipline",
    "heading_letter_review_checklist": "Review Checklist (delete this page before sending)",

    # -- Tender Summary companion document (build_tender_summary_docx) --
    "heading_tender_summary": "Tender Summary",
    "heading_client_objectives": "Client objectives",
    "heading_mandatory_requirements": "Mandatory requirements",
    "heading_deliverables": "Deliverables",
    "heading_required_forms": "Required forms / returnable schedules",
    "heading_assumptions": "Assumptions",
    "heading_evaluation_weighting_dashboard": "Evaluation weighting dashboard",
    "heading_extraction_warnings": "Extraction warnings -- verify manually",
    "heading_compliance_matrix": "Compliance Matrix",
    "heading_gap_analysis": "Gap Analysis",
    "heading_user_input_required": "User Input Required List",
    "heading_placeholders_in_document": "Placeholders found in the proposal document itself",

    # -- Non-heading scaffolding (Audit Round 2, Part 5) --
    # Exporter-written body text/placeholders that a Spanish-output pack
    # was still getting in English. Scoped to what the audit brief actually
    # flagged (specific file:line citations) -- a full sweep of every
    # remaining English string in this module (personnel-profile field
    # labels, business-boilerplate paragraphs, etc.) is a larger follow-up.
    # Round 3, Part 1b follow-up: reworded to open with the canonical
    # "[INSERT" prefix -- it previously matched no PLACEHOLDER_PREFIXES
    # entry in EITHER language (a pre-existing gap wider than Part 1b's own
    # citation list), so an English pack's own placeholder sweep silently
    # missed it too, not just a Spanish one.
    "export_footer_bidder_placeholder": "[INSERT BIDDER COMPANY NAME]",
    "export_footer_registered_address": "[REGISTERED ADDRESS]",
    "export_no_introduction": "[NO INTRODUCTION DRAFTED YET -- generate a draft or write one in the Draft Responses step]",
    "export_no_fees_entered_letter": "[NO FEES ENTERED -- price the discipline fee build-up, or generate the discipline fee split, in the Fees & Program step]",
    "export_fee_nothing_selected": "[SELECT WHICH FEE PRESENTATION TO INCLUDE -- Fee Estimate tab]",
    "export_no_assumptions": "[NO ASSUMPTIONS EXTRACTED -- add any that apply]",
    "export_no_terms_of_engagement": "[NO TERMS OF ENGAGEMENT ENTERED -- reference the applicable contract/commercial conditions]",
    "export_no_scope_items": "[NO SCOPE ITEMS EXTRACTED -- run Tender Analysis, or add scope items manually]",
    "export_no_tasks_for_item": "[NO TASKS EXTRACTED FOR {item}]",
    "export_no_methodology": "[NO METHODOLOGY DRAFTED YET -- generate first-pass drafts in the Draft Responses step]",
    "export_eyebrow_why_choose_us": "Why choose us",
    "export_no_team_members": "[NO TEAM MEMBERS ASSIGNED -- assign people (and tick 'Include in proposal') in the Team & Resourcing tab]",
    "export_no_program_entered": "[NO PROGRAM ENTERED -- set the delivery weeks in the Program step]",
    "export_letter_signoff_regards": "Regards",
    "export_letter_sender_placeholder": "[INSERT SENDER NAME]",
    "export_letter_checklist_placeholders": "Replace every red bracketed placeholder above with real, verified content.",
    "export_letter_checklist_fees": "Confirm every fee figure is a real, reviewed number -- not a seeded estimate.",
    "export_letter_checklist_team": "Confirm named team members' availability for the stated program.",
    "export_letter_checklist_program": "Confirm the program dates are realistic and reflect any award-date dependency.",
    "export_letter_checklist_terms": "Confirm the Terms of Engagement reference the correct/current contract.",
    "export_letter_checklist_footer": "Fill in the footer's ABN and registered address placeholders on every page.",
    "export_letter_checklist_proofread": "Proofread the document as a whole -- cover page, Executive Summary, and sign-off details.",
    "export_checklist_delete_boxes": "Delete every red 'DELETE BEFORE SUBMISSION' guidance box in this document.",
    "export_checklist_replace_placeholders": "Replace every red bracketed placeholder -- [INSERT ...], [CONFIRM ...] and [TO BE COMPLETED: ...] -- with verified, project-specific content.",
    "export_checklist_page_limits": "Confirm every page limit and formatting rule against the current brief and any addenda.",
    "export_checklist_schedules": "Complete and attach all returnable schedules / forms listed in the Compliance Matrix.",
    "export_checklist_personnel": "Confirm named personnel, CVs, certifications, and insurances are current and accurate.",
    "export_checklist_fee_cap": "Confirm the priced schedule against any stated fee cap.",
    "export_checklist_graphics": "Replace all graphic placeholders with final, approved graphics.",
    "export_checklist_toc": "Update the Table of Contents field before final export.",
    "export_checklist_compliance_check": "Run a final compliance check against every row in the Compliance Matrix.",
    "export_checklist_submission": "Confirm the submission method, format, and deadline one more time before lodging.",
    "export_cover_image_placeholder": "[COVER IMAGE PLACEHOLDER]",
    "export_cover_image_placeholder_detail": "[COVER IMAGE PLACEHOLDER: PROJECT / SITE PHOTO]",
    "export_cover_disclaimer": (
        "FIRST-PASS PREPARATION PACK -- NOT SUBMISSION READY. Generated {date}. Every red "
        "guidance box and bracketed placeholder must be reviewed, verified, and removed "
        "before this document is used for anything beyond internal drafting."
    ),
    "export_cover_fallback_title": "Tender Response Pack",
    "export_pull_quote_eyebrow_differentiator": "What sets us apart",
    "export_no_executive_summary": "[NO EXECUTIVE SUMMARY DRAFTED YET -- generate one in the Draft Responses step]",
    "export_block_untitled": "[UNTITLED]",
    "export_no_content_drafted": "[NO CONTENT DRAFTED]",
    "export_unweighted_note": (
        "[UNWEIGHTED -- carries no evaluation score, but sets the tone for everything that "
        "follows. Confirm every claim above before submission.]"
    ),
    "export_org_chart_firstpass_note": (
        "[FIRST-PASS CHART ABOVE, generated from the Team & Resourcing tab -- replace it with "
        "the finished chart. A companion PowerPoint org chart is exported alongside this "
        "document; finish it there, then paste it over the image above.]"
    ),
    "export_org_chart_insert_note": (
        "[INSERT ORGANISATION CHART HERE -- paste in the finished chart image. A companion "
        "PowerPoint org chart template is exported alongside this document; build the chart "
        "there, then paste it into this space.]"
    ),
    "export_photo_placeholder": "[INSERT PHOTO]",
    "export_photo_placeholder_instruction": "Click here, delete this text, then Insert ▸ Pictures",
    "export_cash_flow_insert": "[INSERT PROJECT CASH FLOW PROFILE, BASED ON THE FEE AND PROGRAM]",
    "export_local_benefits_intro_note": (
        "The brief calls for local-benefit / local-content commitments -- the headings below are "
        "a standard starting structure; every figure and claim must be confirmed for this bid "
        "before submission."
    ),
    "export_local_benefits_heading_resources": "Local resources and location",
    "export_local_benefits_heading_economy": "Contribution to the local economy",
    "export_local_benefits_heading_strategy": "Alignment with local strategy / vision",
    "export_local_benefits_heading_reinvestment": "Profit / community reinvestment",
    "export_local_benefits_confirm_local": "[CONFIRM % OF THE TEAM BASED LOCALLY AND WHICH OFFICE(S) WILL DELIVER THE WORK]",
    "export_local_benefits_describe_economy": (
        "[DESCRIBE HOW THIS BID SUPPORTS LOCAL EMPLOYMENT, LOCAL SUPPLIERS/SUBCONSULTANTS, AND "
        "REINVESTMENT IN {client}'S REGION]"
    ),
    "export_local_benefits_reference_strategy": "[REFERENCE ANY NAMED LOCAL/REGIONAL STRATEGY OR VISION DOCUMENT THE BRIEF CALLS OUT]",
    "export_local_benefits_confirm_reinvestment": "[CONFIRM A REAL, CURRENT FIRM COMMUNITY/REINVESTMENT PROGRAM TO REFERENCE HERE]",
    "export_local_benefits_from_profile": "[FROM YOUR FIRM PROFILE -- confirm it still reads correctly for this bid]",
    "export_user_input_intro": "Everything below still needs a human to supply real information.",
    "export_user_input_none": "(none identified -- verify manually)",

    # -- PPTX builders (org_chart_pptx.py / program_pptx.py / methodology_pptx.py) --
    "pptx_org_chart_title": "Project organisation",
    "pptx_org_band_client": "Client",
    "pptx_org_band_leadership": "Leadership",
    "pptx_org_band_delivery_team": "Delivery team",
    "pptx_org_band_assurance": "Assurance",
    "pptx_org_peer_review": "Peer review — {name}",
    "pptx_org_footnote_with_assurance": (
        "Solid reporting lines run top-down; the assurance band reviews independently of the "
        "delivery team."
    ),
    "pptx_org_footnote_plain": "Solid reporting lines run top-down.",
    "pptx_org_empty_note": (
        "[NO TEAM ASSIGNED -- add the management roles and discipline leads in the Team & "
        "Resourcing tab, then re-download this PowerPoint]"
    ),
    "pptx_program_title": "Delivery program",
    "pptx_insert_project_name": "[Insert project name]",
    "pptx_program_legend_scheduled": "Scheduled activity",
    "pptx_program_legend_milestone": "Milestone / hold point",
    # Round 3, Part 4b: milestone labels program_render.build_model() derives
    # itself (a client hold point from the methodology stages, a submission
    # milestone from the tender's deadline) -- shared by BOTH the PPTX export
    # and the PNG preview, so these were English regardless of
    # output_language until this round.
    "program_milestone_client_hold_point": "Client hold point",
    "program_milestone_submission": "Submission",
    "pptx_program_empty_note": (
        "[NO PROGRAM ENTERED -- build the delivery program in the Fee Estimate tab, then "
        "re-download this PowerPoint]"
    ),
    "pptx_methodology_title": "Our proposed methodology",
    "pptx_wvr_statement": "All design deliverables will be issued with completed Work Verification Records (WVRs)",
    "pptx_wvr_confirm_placeholder": "[CONFIRM WVR / QA STATEMENT FOR THIS FIRM]",

    # -- Round 3, Part 2: methodology_pptx.py's DEFAULT "matrix" style (and
    # the three non-default styles, which had the identical bug) had these
    # row labels/legend text hardcoded in English regardless of language. --
    "pptx_key_legend_heading": "KEY",
    "pptx_meth_client_placeholder": "[Insert client name]",
    "pptx_meth_hold_point_suffix": " hold point",
    "pptx_meth_collaborative_engagement": "Collaborative engagement",
    "pptx_row_key_tasks": "KEY TASKS",
    "pptx_row_key_engagement_activities": "KEY ENGAGEMENT\nACTIVITIES",
    "pptx_row_outcome": "OUTCOME",
    "pptx_row_deliverables": "DELIVERABLES",
    "pptx_row_engagement": "ENGAGEMENT",
    "pptx_row_what_we_do": "WHAT WE DO",
    "pptx_row_with_you": "WITH YOU",
    "pptx_row_you_receive": "YOU RECEIVE",
    "pptx_row_what_you_receive": "WHAT YOU RECEIVE",
    "pptx_hold_point_diamond": "HOLD\nPOINT",
    "pptx_confirm_date_range": "[Date range]",
    "pptx_deliverables_more_line": "+{dropped} more — see full methodology",

    # -- Round 3, Part 2: org_chart_pptx.py's DEFAULT "cards" style (and the
    # "columns"/"tree" styles, same bug) -- the "bands" style was localised
    # in Audit Round 2, but the panel/badge text it shares with these three
    # was not. --
    "pptx_peer_review_heading": "PEER REVIEW",
    "pptx_qa_review_badge": "QA / Review",
    "pptx_client_suffix_label": "{label} — Client",
    "pptx_independent_review_prefix": "★ Independent review: {text}",
    "pptx_confirm_title": "[CONFIRM TITLE]",
    "pptx_role_lead_label": "{role} Lead",
    "pptx_client_role_with_name": "Client · {name}",

    # -- Round 3, Part 4b: the live PNG previews (org_chart_render.py /
    # program_render.py / methodology_render.py's render_png(), shown in
    # the app's own Draft Responses / Team & Resourcing / Fees & Program
    # tabs) had ZERO language support -- a matplotlib-drawn parallel to the
    # PPTX builders' own scaffolding, with the identical bug. Most of the
    # PPTX keys above are reused verbatim since the English wording matches
    # exactly; the two below are preview-specific text that has no PPTX
    # twin (a live preview says "re-generate", a downloaded file says
    # "re-download"). --
    "org_chart_preview_empty_note": (
        "[NO TEAM ASSIGNED -- add the management roles and discipline leads in the "
        "Team & Resourcing tab, then re-generate this]"
    ),
    "program_preview_empty_note": (
        "[NO PROGRAM ENTERED -- build the delivery program in the Fees & Program tab, "
        "then re-generate this]"
    ),

    # -- Round 3, Part 2: program_pptx.py's swimlanes-style-specific legend
    # text and stage fallback (the shared _activity_legend() helper was
    # already localised; this swatch is built ad hoc only in that style). --
    "pptx_milestone_legend": "Milestone",
    "pptx_unassigned_stage_label": "Unassigned",
    "pptx_duration_weeks_short": "{weeks} wk",
    "pptx_week_number_short": "Wk {week}",
    "pptx_duration_weeks_long_singular": "{weeks} week",
    "pptx_duration_weeks_long_plural": "{weeks} weeks",

    # -- Round 3, Part 2 follow-up: methodology_render.py's "legacy"
    # boilerplate columns (build_columns()/_legacy_columns()) -- shown by
    # ALL FOUR methodology PPTX styles (and the matching PNG preview,
    # Part 4b's own territory for the render side) whenever a project hasn't
    # run the stage drafter yet, i.e. the exact case check_spanish_pptx's
    # own default arguments exercise. Not in Part 2's own file citations
    # (org_chart_pptx.py / methodology_pptx.py / program_pptx.py) but the
    # identical "hardcoded English regardless of output_language" bug, and
    # the one that made the loop-every-style-and-check-body-text acceptance
    # test actually fail -- so fixed here rather than left as a gap. --
    "pptx_legacy_stage1_name": "Project Initiation",
    "pptx_legacy_stage2_name": "15% design stage",
    "pptx_legacy_stage3_name": "15% developed to 50% design stage",
    "pptx_legacy_stage4_name": "50% developed to Final stage",
    "pptx_legacy_task_liaison": "Liaison with the client",
    "pptx_legacy_task_including": "Including:",
    "pptx_legacy_task_inception": "Inception (prestart) meeting",
    "pptx_legacy_task_site_inspection": "Site inspection",
    "pptx_legacy_task_confirm_program": "Confirmation of delivery program and team availability",
    "pptx_legacy_task_comm_protocols": "Establishing communication protocols",
    "pptx_legacy_task_progress_setup": "Initial progress reporting setup",
    "pptx_legacy_task_quality_plan": "Draft Quality Plan for discussion",
    "pptx_legacy_engagement_inception": "Inception meeting",
    "pptx_legacy_engagement_site_walkover": "Site inspection walkover",
    "pptx_legacy_outcome": "Project governance, scope, and collaboration framework established.",
    "pptx_legacy_deliverable_minutes": "Inception meeting minutes",
    "pptx_legacy_deliverable_comm_doc": "Communication protocols document",
    "pptx_no_scope_placeholder": (
        "[DESCRIBE APPROACH FOR THIS STAGE -- analyse the brief (Tender Analysis tab) to "
        "prefill this from the brief's real scope items]"
    ),
    "pptx_confirm_engagement_stage": "[CONFIRM ENGAGEMENT / WORKSHOP ACTIVITIES FOR THIS STAGE]",
    "pptx_confirm_outcome_stage": "[CONFIRM OUTCOME FOR THIS STAGE]",
    "pptx_confirm_deliverables_stage": "[CONFIRM DELIVERABLE(S) FOR THIS STAGE]",
    "pptx_confirm_tasks_stage": "[CONFIRM TASKS FOR THIS STAGE]",

    # -- Round 3, Part 1a: export_docx.py placeholders/labels that were still
    # written as raw English constants regardless of output_language. --
    "export_methodology_table_placeholder": (
        "[INSERT METHODOLOGY TABLE -- generate it in the app and paste the finished PowerPoint "
        "table here]"
    ),
    "export_no_draft_generated_section": "[NO DRAFT GENERATED YET -- run Draft Responses for this section]",
    "export_no_draft_body": "[NO DRAFT BODY -- generate a draft for this section]",
    "export_insert_key_personnel_name": "[INSERT KEY PERSONNEL NAME]",
    "export_insert_qualification": "[INSERT QUALIFICATION]",
    "export_confirm_registration_status": "[CONFIRM REGISTRATION STATUS AND NUMBER]",
    "export_insert_years_experience": "[INSERT YEARS OF EXPERIENCE FOR CV ATTACHMENT]",
    "export_insert_project_specific_detail": "[INSERT PROJECT-SPECIFIC DETAIL]",
    "export_enter_fee": "[ENTER FEE]",
    "export_not_assigned": "[NOT ASSIGNED]",
    "export_not_provided": "[NOT PROVIDED]",
    "export_no_description_drafted": "[NO DESCRIPTION DRAFTED -- draft/review this reference project in Upload Docs]",
    "export_insert_relevance_to_tender": "[INSERT RELEVANCE TO THIS TENDER]",
    "export_confirm_personnel_worked_on_project": "[CONFIRM WHICH KEY PERSONNEL WORKED ON THIS PROJECT]",
    "export_no_personnel_assigned_yet": "[NO PERSONNEL ASSIGNED YET -- assign names in the Team & Resourcing tab]",
    "export_no_personnel_ticked": (
        "[NO KEY PERSONNEL ARE TICKED FOR INCLUSION -- tick at least the project leadership "
        "(Project Director/Manager/Design Manager) in the Team & Resourcing tab]"
    ),
    "export_confirm_contractual_arrangements": (
        "[CONFIRM THE PANEL / CONTRACT AND RATES THIS FEE IS BASED ON, AND ANY SUBCONSULTANT "
        "ARRANGEMENTS (E.G. MEMORANDUM OF UNDERSTANDING / SUBCONSULTANCY AGREEMENTS)]"
    ),
    "export_evaluation_weighting_dashboard_placeholder": "[EVALUATION WEIGHTING DASHBOARD PLACEHOLDER]",
    "export_graphic_placeholder": "[{title} PLACEHOLDER]",
    "export_no_fee_buildup_entered": "[NO FEE BUILD-UP ENTERED -- price the discipline fee table in the Fees & Program tab]",
    "export_no_fee_buildup_entered_tab": "[NO FEE BUILD-UP ENTERED -- price the discipline fee table in the Fee Estimate tab]",

    # -- Round 3, Part 4a: table headers and inline labels around the same
    # sites, and a few personnel-block sites outside Part 1a's list. --
    "export_label_qualification": "Qualification",
    "export_label_experience": "Experience",
    "export_label_on_project_will": "On this project, {name} will",
    "export_label_relevant_experience": "Relevant project experience:",
    "export_label_local_experience": "Local district experience:",
    "export_label_rpeq_status": "RPEQ / registration status",
    "export_label_years_experience": "Years of experience",
    "export_label_relevance_to_project": "Relevance to project: ",
    "export_label_personnel_involved": "Personnel involved: ",
    "export_heading_graphics_for_section": "Graphics for this section",
    "export_table_header_discipline": "Discipline",
    "export_table_header_discipline_stage": "Discipline / stage",
    "export_table_header_fee_excl_gst": "Fee (excl. GST)",
    "export_table_header_total": "Total",
    "export_table_header_id": "ID",
    "export_table_header_description": "Description",
    "export_table_header_type": "Type",
    "export_table_header_mapped_section": "Mapped Section",
    "export_table_header_priority": "Priority",
    "export_table_header_status": "Status",
    "export_table_header_action_required": "Action Required",
    "export_table_header_risk": "Risk",
    "export_table_header_issue": "Issue",
    "export_table_header_impact": "Impact",
    "export_table_header_recommended_action": "Recommended Action",
    "export_compliance_matrix_intro": (
        "Every requirement identified in the brief, mapped to a proposal section and a status. "
        "'Missing' items need user input before this pack is usable."
    ),
    "export_gap_analysis_intro": "Risks and gaps this pack could identify automatically -- nothing here is invented.",
    "export_no_scope_item_fees_entered": "[NO SCOPE ITEM FEES ENTERED -- price the scope item table in the Fee Estimate tab]",
    "export_untitled_scope_item": "[UNTITLED SCOPE ITEM]",
    "export_table_header_scope_item": "Scope item",
    "export_table_header_notes": "Notes",
    "export_note_selected_past_projects": (
        "Selected past projects most relevant to this brief's scope, drawn from the firm's "
        "project reference library."
    ),
    "export_no_relevance_drafted": "[NO RELEVANCE DRAFTED -- draft/review this reference project in Upload Docs]",
    "export_table_header_scope_item_cap": "Scope Item",
    "export_table_header_commence": "Commence",
    "export_table_header_complete": "Complete",
    "export_table_header_duration": "Duration",
    # Round 3, Part 4b: the PNG preview's "Formal table" style has its own
    # inline timeline-bar column and legend, not present in the PPTX table
    # slide (which has no room for it) -- new keys, no PPTX equivalent to reuse.
    "program_table_header_timeline": "Timeline",
    "program_table_legend_scheduled_duration": "Scheduled duration",
    "export_program_anchored_note": (
        "Program anchored to an anticipated commencement of {start_date} -- dates shift with "
        "the actual award date."
    ),
    "export_table_header_risk_cap": "Risk",
    "export_table_header_impact_cap": "Impact",
    "export_table_header_mitigation": "Mitigation",
    "export_risk_register_firstpass_note": (
        "[FIRST-PASS REGISTER -- every mitigation is a commitment this firm will be held to. "
        "Confirm each one, and replace every red TBC, before submission.]"
    ),
    "export_no_reference_projects_entered": (
        "[NO REFERENCE PROJECTS ENTERED -- add project references in Upload Docs, then "
        "draft/review them there before export]"
    ),
    "export_client_name_placeholder": "[CLIENT NAME]",
    "export_relationship_intro": (
        "We focus on the moments that matter -- looking beyond the technical solution to foster "
        "a united, professional relationship with {client}. By maintaining live comment "
        "registers and prioritising timely review closure, we minimise rework and ensure "
        "stakeholder input is captured and actioned. Proactive engagement and clear "
        "communication are central to our relationship management approach and underpin our "
        "proven ability to deliver projects on time."
    ),
    "export_label_leadership_oversight": "Leadership oversight. ",
    "export_relationship_standard_text_note": (
        "[STANDARD TEXT -- confirm real local staff/offices, and tailor to this project's actual "
        "engagement plan, before submission]"
    ),
    "export_table_header_principles": "Principles",
    "export_table_header_our_approach": "Our approach",
    "export_length_note_under_over": (
        "[LENGTH: this draft is about {words} words against roughly {target} for its {pages}-page "
        "allocation -- {verdict_text} budget (more than {tolerance_pct}% out). {action_text}"
    ),
    "export_length_verdict_under": "well under",
    "export_length_verdict_over": "well over",
    "export_length_action_under": "Expand it with real detail, or re-check the allocation.",
    "export_length_action_over": "Cut it back, or re-check the allocation.",

    # -- Round 3, Part 4a: fee_estimation_engine.py's INDICATIVE_NOTE and the
    # fee-table headers around its two call sites in export_docx.py. --
    "export_indicative_fee_split_note": (
        "INDICATIVE FEE SPLIT -- INTERNAL PLANNING ONLY, NOT FOR SUBMISSION. This is a rough "
        "sanity check for the bid team, not a priced offer. It must be reviewed and re-priced "
        "by whoever owns commercial sign-off before any number here is used anywhere near an "
        "actual submission."
    ),
    "export_table_header_fee_pct": "Fee %",
    "export_table_header_confidence": "Confidence",
    "export_table_header_source": "Source",
    "export_table_header_indicative_amount": "Indicative $",
    "export_fee_cap_anchored_note": "Anchored to the brief's stated fee cap: {fee_cap}",
}

# Spanish overrides -- only keys that differ from English need an entry here;
# export_t() falls back to _EN for anything missing. Terminology deliberately
# matches modules/translations/es.py (e.g. "propuesta" for proposal,
# "honorarios" for fees, "licitación" for tender) so a project's exported
# pack reads consistently with the rest of the app's Spanish UI.
_ES: dict[str, str] = {
    "heading_toc": "Tabla de contenido",
    "heading_executive_summary": "Resumen ejecutivo",
    "heading_risks_noted_in_brief": "Riesgos identificados en el brief",
    "heading_fee_summary": "Resumen de honorarios",
    "heading_fee_by_scope_item": "Honorarios por partida de alcance",
    "heading_cash_flow": "Flujo de caja",
    "heading_contractual_arrangements": "Arreglos contractuales",
    "heading_local_benefits": "Beneficios locales",
    "heading_review_checklist": "Lista de verificación",

    "heading_page_allocation_plan": "Plan de asignación de páginas",
    "heading_fee_estimate_by_discipline": "Estimación indicativa de honorarios por disciplina",
    "heading_org_chart": "Organigrama del proyecto",
    "heading_key_personnel_profiles": "Perfiles de personal clave",
    "heading_methodology_summary": "Resumen de la metodología",
    "heading_relevant_experience_compact": "Experiencia relevante en proyectos",
    "heading_relevant_experience": "Nuestra experiencia relevante en proyectos",
    "heading_personnel_experience_matrix": "Personal clave x experiencia relevante",
    "heading_relationship_management": "Nuestro enfoque de gestión de relaciones",

    "heading_letter_intro": "1. Introducción",
    "heading_letter_scope_of_work": "2. Alcance del trabajo",
    "heading_letter_methodology": "3. Metodología y entregables",
    "heading_letter_team": "4. Equipo del proyecto",
    "heading_letter_fees": "5. Honorarios",
    "heading_letter_program": "6. Programa",
    "heading_letter_assumptions": "7. Supuestos y aclaraciones",
    "heading_letter_terms": "8. Términos de contratación",
    "heading_risks_mitigation": "Riesgos y mitigación",
    "heading_discipline_fee_buildup": "Desglose de honorarios por disciplina",
    "heading_fee_split_by_discipline": "Reparto indicativo de honorarios por disciplina",
    "heading_letter_review_checklist": "Lista de verificación (elimina esta página antes de enviar)",

    "heading_tender_summary": "Resumen de la licitación",
    "heading_client_objectives": "Objetivos del cliente",
    "heading_mandatory_requirements": "Requisitos obligatorios",
    "heading_deliverables": "Entregables",
    "heading_required_forms": "Formularios / anexos requeridos",
    "heading_assumptions": "Supuestos",
    "heading_evaluation_weighting_dashboard": "Panel de ponderación de evaluación",
    "heading_extraction_warnings": "Advertencias de extracción -- verificar manualmente",
    "heading_compliance_matrix": "Matriz de cumplimiento",
    "heading_gap_analysis": "Análisis de brechas",
    "heading_user_input_required": "Lista de información pendiente del usuario",
    "heading_placeholders_in_document": "Marcadores de posición encontrados en el propio documento de la propuesta",

    # -- Non-heading scaffolding (Audit Round 2, Part 5) --
    # Round 3, Part 1b follow-up: reworded to open with the canonical
    # "[INSERTAR" prefix -- it used to open "[NOMBRE...", which happened to
    # match EN's "[NO" prefix as a substring (accidental cross-language
    # match), and matched no ES prefix at all.
    "export_footer_bidder_placeholder": "[INSERTAR NOMBRE DE LA EMPRESA LICITANTE]",
    "export_footer_registered_address": "[DIRECCIÓN REGISTRADA]",
    # Round 3, Part 1b: every one of these used to open "[NO SE ...]", which
    # is NOT one of PLACEHOLDER_PREFIXES["es"] (that set has "[SIN", not
    # "[NO") -- they were only ever found by collect_placeholders() because
    # the ENGLISH "[NO" prefix happens to also match "[NO SE...]" as a
    # substring. Reworded to open with the canonical "[SIN ..." prefix so a
    # Spanish pack's placeholder sweep no longer silently depends on the
    # English prefix set being present too (see test 5a).
    "export_no_introduction": "[SIN INTRODUCCIÓN REDACTADA AÚN -- genere un borrador o escríbala en el paso Redactar Respuestas]",
    "export_no_fees_entered_letter": "[SIN HONORARIOS INGRESADOS -- calcule el desglose de honorarios por disciplina, o genere el reparto por disciplina, en el paso Honorarios y Programa]",
    "export_fee_nothing_selected": "[SELECCIONE QUÉ PRESENTACIÓN DE HONORARIOS INCLUIR -- pestaña Estimación de Honorarios]",
    "export_no_assumptions": "[SIN SUPUESTOS EXTRAÍDOS -- agregue los que correspondan]",
    "export_no_terms_of_engagement": "[SIN TÉRMINOS DE CONTRATACIÓN INGRESADOS -- haga referencia al contrato o condiciones comerciales aplicables]",
    "export_no_scope_items": "[SIN PARTIDAS DE ALCANCE EXTRAÍDAS -- ejecute el Análisis de la Licitación, o agregue partidas de alcance manualmente]",
    "export_no_tasks_for_item": "[SIN TAREAS EXTRAÍDAS PARA {item}]",
    "export_no_methodology": "[SIN METODOLOGÍA REDACTADA AÚN -- genere borradores iniciales en el paso Redactar Respuestas]",
    "export_eyebrow_why_choose_us": "Por qué elegirnos",
    "export_no_team_members": "[SIN INTEGRANTES DEL EQUIPO ASIGNADOS -- asigne personas (y marque 'Incluir en la propuesta') en la pestaña Equipo y Recursos]",
    "export_no_program_entered": "[SIN PROGRAMA INGRESADO -- defina las semanas de ejecución en el paso Programa]",
    "export_letter_signoff_regards": "Saludos cordiales",
    "export_letter_sender_placeholder": "[INSERTAR NOMBRE DEL REMITENTE]",
    "export_letter_checklist_placeholders": "Reemplace todo marcador de posición en rojo entre corchetes anterior por contenido real y verificado.",
    "export_letter_checklist_fees": "Confirme que cada cifra de honorarios sea un número real y revisado -- no una estimación de referencia.",
    "export_letter_checklist_team": "Confirme la disponibilidad de los integrantes del equipo nombrados para el programa indicado.",
    "export_letter_checklist_program": "Confirme que las fechas del programa sean realistas y reflejen cualquier dependencia de la fecha de adjudicación.",
    "export_letter_checklist_terms": "Confirme que los Términos de Contratación hagan referencia al contrato correcto y vigente.",
    "export_letter_checklist_footer": "Complete los marcadores de posición del ABN y la dirección registrada en el pie de página de cada página.",
    "export_letter_checklist_proofread": "Revise el documento en su totalidad -- portada, resumen ejecutivo y datos de la firma.",
    "export_checklist_delete_boxes": "Elimine todos los cuadros de orientación en rojo 'ELIMINAR ANTES DE PRESENTAR' de este documento.",
    "export_checklist_replace_placeholders": "Reemplace todo marcador de posición en rojo entre corchetes -- [INSERTAR ...], [CONFIRMAR ...] y [POR COMPLETAR: ...] -- por contenido verificado y específico del proyecto.",
    "export_checklist_page_limits": "Confirme cada límite de páginas y regla de formato contra el brief vigente y sus adendas.",
    "export_checklist_schedules": "Complete y adjunte todos los anexos/formularios retornables listados en la Matriz de Cumplimiento.",
    "export_checklist_personnel": "Confirme que el personal nombrado, los CV, las certificaciones y los seguros estén vigentes y sean exactos.",
    "export_checklist_fee_cap": "Confirme el cuadro de precios contra cualquier tope de honorarios establecido.",
    "export_checklist_graphics": "Reemplace todos los marcadores de posición gráficos por gráficos finales y aprobados.",
    "export_checklist_toc": "Actualice el campo de la Tabla de Contenido antes de la exportación final.",
    "export_checklist_compliance_check": "Realice una verificación final de cumplimiento contra cada fila de la Matriz de Cumplimiento.",
    "export_checklist_submission": "Confirme una vez más el método de presentación, el formato y el plazo antes de enviar.",
    "export_cover_image_placeholder": "[MARCADOR DE IMAGEN DE PORTADA]",
    "export_cover_image_placeholder_detail": "[MARCADOR DE IMAGEN DE PORTADA: FOTO DEL PROYECTO / SITIO]",
    "export_cover_disclaimer": (
        "PAQUETE DE PREPARACIÓN DE PRIMERA VERSIÓN -- NO LISTO PARA PRESENTAR. Generado el "
        "{date}. Cada cuadro de orientación en rojo y cada marcador de posición entre corchetes "
        "deben revisarse, verificarse y eliminarse antes de usar este documento para algo más "
        "que un borrador interno."
    ),
    "export_cover_fallback_title": "Paquete de Respuesta a la Licitación",
    "export_pull_quote_eyebrow_differentiator": "Qué nos diferencia",
    "export_no_executive_summary": "[SIN RESUMEN EJECUTIVO REDACTADO AÚN -- genere uno en el paso Redactar Respuestas]",
    "export_block_untitled": "[SIN TÍTULO]",
    "export_no_content_drafted": "[SIN CONTENIDO REDACTADO]",
    "export_unweighted_note": (
        "[SIN PONDERACIÓN -- no otorga puntaje de evaluación, pero marca el tono de todo lo que "
        "sigue. Confirme cada afirmación anterior antes de presentar.]"
    ),
    # Round 3, Part 1b: reworded to open with the canonical "[PRIMERA
    # VERSIÓN" prefix (PLACEHOLDER_PREFIXES["es"]["first_pass"]) -- it used
    # to open "[ORGANIGRAMA DE PRIMERA VERSIÓN...", which that prefix does
    # NOT match (only the English "[FIRST-PASS" twin did), so
    # collect_placeholders() silently missed it in an ES-only sweep.
    "export_org_chart_firstpass_note": (
        "[PRIMERA VERSIÓN DEL ORGANIGRAMA ARRIBA, generado desde la pestaña Equipo y Recursos -- "
        "reemplácelo por el organigrama definitivo. Un organigrama complementario en PowerPoint "
        "se exporta junto con este documento; termínelo allí y luego péguelo sobre la imagen de "
        "arriba.]"
    ),
    "export_org_chart_insert_note": (
        "[INSERTAR ORGANIGRAMA AQUÍ -- pegue la imagen del organigrama terminado. Se exporta una "
        "plantilla de organigrama complementaria en PowerPoint junto con este documento; "
        "constrúyalo allí y luego péguelo en este espacio.]"
    ),
    "export_photo_placeholder": "[INSERTAR FOTO]",
    "export_photo_placeholder_instruction": "Haga clic aquí, elimine este texto y luego Insertar ▸ Imágenes",
    "export_cash_flow_insert": "[INSERTAR PERFIL DE FLUJO DE CAJA DEL PROYECTO, BASADO EN LOS HONORARIOS Y EL PROGRAMA]",
    "export_local_benefits_intro_note": (
        "El brief exige compromisos de beneficio/contenido local -- los encabezados a "
        "continuación son una estructura inicial estándar; cada cifra y afirmación debe "
        "confirmarse para esta oferta antes de presentar."
    ),
    "export_local_benefits_heading_resources": "Recursos y ubicación locales",
    "export_local_benefits_heading_economy": "Contribución a la economía local",
    "export_local_benefits_heading_strategy": "Alineación con la estrategia / visión local",
    "export_local_benefits_heading_reinvestment": "Reinversión de utilidades / en la comunidad",
    "export_local_benefits_confirm_local": "[CONFIRMAR EL % DEL EQUIPO CON BASE LOCAL Y QUÉ OFICINA(S) EJECUTARÁN EL TRABAJO]",
    "export_local_benefits_describe_economy": (
        "[DESCRIBIR CÓMO ESTA OFERTA APOYA EL EMPLEO LOCAL, LOS PROVEEDORES/SUBCONSULTORES "
        "LOCALES Y LA REINVERSIÓN EN LA REGIÓN DE {client}]"
    ),
    "export_local_benefits_reference_strategy": "[REFERENCIAR CUALQUIER ESTRATEGIA O DOCUMENTO DE VISIÓN LOCAL/REGIONAL QUE EL BRIEF MENCIONE]",
    "export_local_benefits_confirm_reinvestment": "[CONFIRMAR UN PROGRAMA REAL Y VIGENTE DE LA EMPRESA DE REINVERSIÓN COMUNITARIA PARA REFERENCIAR AQUÍ]",
    "export_local_benefits_from_profile": "[DESDE SU PERFIL DE EMPRESA -- confirme que siga siendo correcto para esta oferta]",
    "export_user_input_intro": "Todo lo que aparece a continuación aún necesita que una persona proporcione información real.",
    "export_user_input_none": "(no se identificó ninguno -- verifique manualmente)",

    # -- PPTX builders --
    "pptx_org_chart_title": "Organización del proyecto",
    "pptx_org_band_client": "Cliente",
    "pptx_org_band_leadership": "Liderazgo",
    "pptx_org_band_delivery_team": "Equipo de ejecución",
    "pptx_org_band_assurance": "Aseguramiento",
    "pptx_org_peer_review": "Revisión por pares — {name}",
    "pptx_org_footnote_with_assurance": (
        "Las líneas continuas de reporte van de arriba hacia abajo; la banda de aseguramiento "
        "revisa de forma independiente del equipo de ejecución."
    ),
    "pptx_org_footnote_plain": "Las líneas continuas de reporte van de arriba hacia abajo.",
    "pptx_org_empty_note": (
        "[SIN EQUIPO ASIGNADO -- agregue los roles de gestión y los líderes de disciplina "
        "en la pestaña Equipo y Recursos, luego vuelva a descargar este PowerPoint]"
    ),
    "pptx_program_title": "Programa de ejecución",
    "pptx_insert_project_name": "[Insertar nombre del proyecto]",
    "pptx_program_legend_scheduled": "Actividad programada",
    "pptx_program_legend_milestone": "Hito / punto de espera",
    "program_milestone_client_hold_point": "Punto de espera del cliente",
    "program_milestone_submission": "Presentación",
    "pptx_program_empty_note": (
        "[SIN PROGRAMA INGRESADO -- construya el programa de ejecución en la pestaña "
        "Estimación de Honorarios, luego vuelva a descargar este PowerPoint]"
    ),
    "pptx_methodology_title": "Nuestra metodología propuesta",
    "pptx_wvr_statement": "Todos los entregables de diseño se emitirán con Registros de Verificación de Trabajo (WVR) completos",
    "pptx_wvr_confirm_placeholder": "[CONFIRMAR DECLARACIÓN DE WVR / CALIDAD PARA ESTA EMPRESA]",

    # -- Round 3, Part 2 -- see the matching English keys' comments above. --
    "pptx_key_legend_heading": "CLAVE",
    "pptx_meth_client_placeholder": "[Insertar nombre del cliente]",
    "pptx_meth_hold_point_suffix": " punto de espera",
    "pptx_meth_collaborative_engagement": "Participación colaborativa",
    "pptx_row_key_tasks": "TAREAS CLAVE",
    "pptx_row_key_engagement_activities": "ACTIVIDADES CLAVE\nDE PARTICIPACIÓN",
    "pptx_row_outcome": "RESULTADO",
    "pptx_row_deliverables": "ENTREGABLES",
    "pptx_row_engagement": "PARTICIPACIÓN",
    "pptx_row_what_we_do": "QUÉ HACEMOS",
    "pptx_row_with_you": "CON USTED",
    "pptx_row_you_receive": "USTED RECIBE",
    "pptx_row_what_you_receive": "LO QUE USTED RECIBE",
    "pptx_hold_point_diamond": "PUNTO DE\nESPERA",
    "pptx_confirm_date_range": "[Rango de fechas]",
    "pptx_deliverables_more_line": "+{dropped} más — ver metodología completa",

    "pptx_peer_review_heading": "REVISIÓN POR PARES",
    "pptx_qa_review_badge": "QA / Revisión",
    "pptx_client_suffix_label": "{label} — Cliente",
    "pptx_independent_review_prefix": "★ Revisión independiente: {text}",
    "pptx_confirm_title": "[CONFIRMAR CARGO]",
    "pptx_role_lead_label": "Líder de {role}",
    "pptx_client_role_with_name": "Cliente · {name}",

    "org_chart_preview_empty_note": (
        "[SIN EQUIPO ASIGNADO -- agregue los roles de gestión y los líderes de disciplina "
        "en la pestaña Equipo y Recursos, luego vuelva a generar esto]"
    ),
    "program_preview_empty_note": (
        "[SIN PROGRAMA INGRESADO -- construya el programa de ejecución en la pestaña "
        "Honorarios y Programa, luego vuelva a generar esto]"
    ),

    "pptx_milestone_legend": "Hito",
    "pptx_unassigned_stage_label": "Sin asignar",
    "pptx_duration_weeks_short": "{weeks} sem",
    "pptx_week_number_short": "Sem {week}",
    "pptx_duration_weeks_long_singular": "{weeks} semana",
    "pptx_duration_weeks_long_plural": "{weeks} semanas",

    "pptx_legacy_stage1_name": "Iniciación del proyecto",
    "pptx_legacy_stage2_name": "Etapa de diseño al 15%",
    "pptx_legacy_stage3_name": "Etapa de diseño del 15% al 50%",
    "pptx_legacy_stage4_name": "Etapa del 50% a la etapa final",
    "pptx_legacy_task_liaison": "Enlace con el cliente",
    "pptx_legacy_task_including": "Incluyendo:",
    "pptx_legacy_task_inception": "Reunión de inicio de obra",
    "pptx_legacy_task_site_inspection": "Inspección del sitio",
    "pptx_legacy_task_confirm_program": "Confirmación del programa de ejecución y disponibilidad del equipo",
    "pptx_legacy_task_comm_protocols": "Establecimiento de protocolos de comunicación",
    "pptx_legacy_task_progress_setup": "Configuración inicial de informes de avance",
    "pptx_legacy_task_quality_plan": "Borrador del Plan de Calidad para su discusión",
    "pptx_legacy_engagement_inception": "Reunión de inicio",
    "pptx_legacy_engagement_site_walkover": "Recorrido de inspección del sitio",
    "pptx_legacy_outcome": "Gobernanza del proyecto, alcance y marco de colaboración establecidos.",
    "pptx_legacy_deliverable_minutes": "Acta de la reunión de inicio",
    "pptx_legacy_deliverable_comm_doc": "Documento de protocolos de comunicación",
    "pptx_no_scope_placeholder": (
        "[DESCRIBIR EL ENFOQUE PARA ESTA ETAPA -- analice el brief (pestaña Análisis de la "
        "Licitación) para prellenar esto con las partidas de alcance reales del brief]"
    ),
    "pptx_confirm_engagement_stage": "[CONFIRMAR ACTIVIDADES DE PARTICIPACIÓN / TALLER PARA ESTA ETAPA]",
    "pptx_confirm_outcome_stage": "[CONFIRMAR RESULTADO PARA ESTA ETAPA]",
    "pptx_confirm_deliverables_stage": "[CONFIRMAR ENTREGABLE(S) PARA ESTA ETAPA]",
    "pptx_confirm_tasks_stage": "[CONFIRMAR TAREAS PARA ESTA ETAPA]",

    # -- Round 3, Part 1a/4a -- see the matching English keys' comments above. --
    "export_methodology_table_placeholder": (
        "[INSERTAR TABLA DE METODOLOGÍA -- genérela en la aplicación y pegue aquí la tabla de "
        "PowerPoint terminada]"
    ),
    "export_no_draft_generated_section": "[SIN BORRADOR GENERADO AÚN -- ejecute Redactar Respuestas para esta sección]",
    "export_no_draft_body": "[SIN CUERPO DE BORRADOR -- genere un borrador para esta sección]",
    "export_insert_key_personnel_name": "[INSERTAR NOMBRE DEL PERSONAL CLAVE]",
    "export_insert_qualification": "[INSERTAR CUALIFICACIÓN]",
    "export_confirm_registration_status": "[CONFIRMAR EL ESTADO Y NÚMERO DE REGISTRO]",
    "export_insert_years_experience": "[INSERTAR LOS AÑOS DE EXPERIENCIA PARA EL CV ADJUNTO]",
    "export_insert_project_specific_detail": "[INSERTAR DETALLE ESPECÍFICO DEL PROYECTO]",
    "export_enter_fee": "[INGRESAR HONORARIO]",
    "export_not_assigned": "[SIN ASIGNAR]",
    "export_not_provided": "[SIN PROPORCIONAR]",
    "export_no_description_drafted": "[SIN DESCRIPCIÓN REDACTADA -- redacte o revise este proyecto de referencia en Cargar Documentos]",
    "export_insert_relevance_to_tender": "[INSERTAR RELEVANCIA PARA ESTA LICITACIÓN]",
    "export_confirm_personnel_worked_on_project": "[CONFIRMAR QUÉ PERSONAL CLAVE TRABAJÓ EN ESTE PROYECTO]",
    "export_no_personnel_assigned_yet": "[SIN PERSONAL ASIGNADO AÚN -- asigne nombres en la pestaña Equipo y Recursos]",
    "export_no_personnel_ticked": (
        "[SIN PERSONAL CLAVE MARCADO PARA INCLUSIÓN -- marque al menos el liderazgo del proyecto "
        "(Director/Gerente de Proyecto/Gerente de Diseño) en la pestaña Equipo y Recursos]"
    ),
    "export_confirm_contractual_arrangements": (
        "[CONFIRMAR EL PANEL / CONTRATO Y LAS TARIFAS EN QUE SE BASA ESTE HONORARIO, Y CUALQUIER "
        "ACUERDO DE SUBCONSULTOR (P. EJ., MEMORANDO DE ENTENDIMIENTO / ACUERDOS DE SUBCONSULTORÍA)]"
    ),
    "export_evaluation_weighting_dashboard_placeholder": "[MARCADOR DEL PANEL DE PONDERACIÓN DE EVALUACIÓN]",
    "export_graphic_placeholder": "[MARCADOR DE {title}]",
    "export_no_fee_buildup_entered": (
        "[SIN DESGLOSE DE HONORARIOS INGRESADO -- calcule la tabla de honorarios por disciplina en "
        "la pestaña Honorarios y Programa]"
    ),
    "export_no_fee_buildup_entered_tab": (
        "[SIN DESGLOSE DE HONORARIOS INGRESADO -- calcule la tabla de honorarios por disciplina en "
        "la pestaña Estimación de Honorarios]"
    ),
    "export_label_qualification": "Cualificación",
    "export_label_experience": "Experiencia",
    "export_label_on_project_will": "En este proyecto, {name} se encargará de",
    "export_label_relevant_experience": "Experiencia relevante en proyectos:",
    "export_label_local_experience": "Experiencia en el distrito local:",
    "export_label_rpeq_status": "RPEQ / estado de registro",
    "export_label_years_experience": "Años de experiencia",
    "export_label_relevance_to_project": "Relevancia para el proyecto: ",
    "export_label_personnel_involved": "Personal involucrado: ",
    "export_heading_graphics_for_section": "Gráficos de esta sección",
    "export_table_header_discipline": "Disciplina",
    "export_table_header_discipline_stage": "Disciplina / etapa",
    "export_table_header_fee_excl_gst": "Honorario (sin IVA)",
    "export_table_header_total": "Total",
    "export_table_header_id": "ID",
    "export_table_header_description": "Descripción",
    "export_table_header_type": "Tipo",
    "export_table_header_mapped_section": "Sección asignada",
    "export_table_header_priority": "Prioridad",
    "export_table_header_status": "Estado",
    "export_table_header_action_required": "Acción requerida",
    "export_table_header_risk": "Riesgo",
    "export_table_header_issue": "Problema",
    "export_table_header_impact": "Impacto",
    "export_table_header_recommended_action": "Acción recomendada",
    "export_compliance_matrix_intro": (
        "Cada requisito identificado en el brief, asignado a una sección de la propuesta y un "
        "estado. Los elementos 'Faltante' necesitan la intervención del usuario antes de que este "
        "paquete sea utilizable."
    ),
    "export_gap_analysis_intro": (
        "Riesgos y brechas que este paquete puede identificar automáticamente -- nada aquí está "
        "inventado."
    ),
    "export_no_scope_item_fees_entered": (
        "[SIN HONORARIOS DE PARTIDAS DE ALCANCE INGRESADOS -- calcule la tabla de partidas de "
        "alcance en la pestaña Estimación de Honorarios]"
    ),
    "export_untitled_scope_item": "[PARTIDA DE ALCANCE SIN TÍTULO]",
    "export_table_header_scope_item": "Partida de alcance",
    "export_table_header_notes": "Notas",
    "export_note_selected_past_projects": (
        "Proyectos anteriores seleccionados más relevantes para el alcance de este brief, "
        "extraídos de la biblioteca de proyectos de referencia de la empresa."
    ),
    "export_no_relevance_drafted": "[SIN RELEVANCIA REDACTADA -- redacte o revise este proyecto de referencia en Cargar Documentos]",
    "export_table_header_scope_item_cap": "Partida de alcance",
    "export_table_header_commence": "Inicio",
    "export_table_header_complete": "Finalización",
    "export_table_header_duration": "Duración",
    "program_table_header_timeline": "Cronograma",
    "program_table_legend_scheduled_duration": "Duración programada",
    "export_program_anchored_note": (
        "El programa está anclado a un inicio previsto el {start_date} -- las fechas cambian "
        "según la fecha real de adjudicación."
    ),
    "export_table_header_risk_cap": "Riesgo",
    "export_table_header_impact_cap": "Impacto",
    "export_table_header_mitigation": "Mitigación",
    "export_risk_register_firstpass_note": (
        "[PRIMERA VERSIÓN DEL REGISTRO -- cada mitigación es un compromiso que asumirá esta "
        "empresa. Confirme cada una y reemplace cada TBC en rojo antes de presentar.]"
    ),
    "export_no_reference_projects_entered": (
        "[SIN PROYECTOS DE REFERENCIA INGRESADOS -- agregue proyectos de referencia en Cargar "
        "Documentos, luego redáctelos o revíselos allí antes de exportar]"
    ),
    "export_client_name_placeholder": "[NOMBRE DEL CLIENTE]",
    "export_relationship_intro": (
        "Nos enfocamos en los momentos que importan -- yendo más allá de la solución técnica "
        "para fomentar una relación unida y profesional con {client}. Mediante el mantenimiento "
        "de registros de comentarios en vivo y la priorización del cierre oportuno de las "
        "revisiones, minimizamos el retrabajo y garantizamos que los aportes de las partes "
        "interesadas se capturen y se atiendan. La participación proactiva y la comunicación "
        "clara son fundamentales para nuestro enfoque de gestión de relaciones y sustentan "
        "nuestra probada capacidad de entregar proyectos a tiempo."
    ),
    "export_label_leadership_oversight": "Supervisión del liderazgo. ",
    "export_relationship_standard_text_note": (
        "[TEXTO ESTÁNDAR -- confirme el personal y las oficinas locales reales, y adapte al "
        "plan de participación real de este proyecto, antes de presentar]"
    ),
    "export_table_header_principles": "Principios",
    "export_table_header_our_approach": "Nuestro enfoque",
    "export_length_note_under_over": (
        "[LONGITUD: este borrador tiene aproximadamente {words} palabras frente a las {target} "
        "previstas para su asignación de {pages} páginas -- {verdict_text} el presupuesto (más "
        "del {tolerance_pct}% de diferencia). {action_text}"
    ),
    "export_length_verdict_under": "muy por debajo de",
    "export_length_verdict_over": "muy por encima de",
    "export_length_action_under": "Amplíelo con detalle real, o vuelva a revisar la asignación.",
    "export_length_action_over": "Redúzcalo, o vuelva a revisar la asignación.",

    "export_indicative_fee_split_note": (
        "REPARTO DE HONORARIOS INDICATIVO -- SOLO PLANIFICACIÓN INTERNA, NO PARA PRESENTAR. Esta "
        "es una verificación aproximada para el equipo de licitación, no una oferta con precio. "
        "Debe ser revisada y reevaluada por quien tenga la aprobación comercial antes de que "
        "cualquier cifra aquí se use cerca de una presentación real."
    ),
    "export_table_header_fee_pct": "Honorario %",
    "export_table_header_confidence": "Confianza",
    "export_table_header_source": "Fuente",
    "export_table_header_indicative_amount": "$ indicativo",
    "export_fee_cap_anchored_note": "Anclado al tope de honorarios indicado en el brief: {fee_cap}",
}

_CATALOGS: dict[str, dict[str, str]] = {
    "en": _EN,
    "es": _ES,
}


# ---------------------------------------------------------------------------
# Canonical placeholder markers (Audit Round 2, Part 4).
#
# Every red bracketed placeholder written by a DETERMINISTIC code path
# (returnable_schedules.py's make_placeholder(), the DOCX/PPTX exporters,
# draft_generator's own prompt instructions) must use exactly one of these
# prefixes -- never a free translation coined on the spot -- so that
# export_docx.collect_placeholders()'s sweep (which matches on these literal
# prefixes, see ALL_PLACEHOLDER_PREFIXES below) never silently misses what a
# Spanish pack actually contains. The Spanish UI already promises
# "[POR COMPLETAR: ...]" (modules/translations/es.py) -- this is what
# actually makes that promise true.
#
# Keyed by a short logical "kind" so callers ask for what they mean
# ("tbc" == to-be-completed, the common case) rather than repeating literal
# bracket text everywhere.
PLACEHOLDER_PREFIXES: dict[str, dict[str, str]] = {
    "en": {
        "tbc": "[TO BE COMPLETED",
        "insert": "[INSERT",
        "confirm": "[CONFIRM",
        "no": "[NO",
        "describe": "[DESCRIBE",
        "enter": "[ENTER",
        "reference": "[REFERENCE",
        "first_pass": "[FIRST-PASS",
        "standard_text": "[STANDARD TEXT",
        "length": "[LENGTH:",
    },
    "es": {
        "tbc": "[POR COMPLETAR",
        "insert": "[INSERTAR",
        "confirm": "[CONFIRMAR",
        "no": "[SIN",
        "describe": "[DESCRIBIR",
        "enter": "[INGRESAR",
        "reference": "[REFERENCIA",
        "first_pass": "[PRIMERA VERSIÓN",
        "standard_text": "[TEXTO ESTÁNDAR",
        "length": "[LONGITUD:",
    },
}

# Flattened across every language -- what collect_placeholders() sweeps a
# generated document for, so a pack that mixes languages (e.g. after a
# mid-project output-language switch) still gets every placeholder listed,
# not just the ones matching whatever language the project is in right now.
ALL_PLACEHOLDER_PREFIXES: tuple[str, ...] = tuple(
    prefix for lang_map in PLACEHOLDER_PREFIXES.values() for prefix in lang_map.values()
)

# Round 3, Part 4b: program_render.build_model() derives the delivery
# program's month bands with datetime.strftime("%B"), which always returns
# the ENGLISH month name regardless of output_language (it follows the
# server's C locale, not the project's language) -- a Spanish "Modern
# timeline" style program silently showed "JANUARY"/"FEBRUARY" bands no
# matter what. A fixed lookup table sidesteps strftime's locale dependence
# entirely rather than trying to get a Spanish locale installed/selected
# server-side for one string.
MONTH_NAMES: dict[str, list[str]] = {
    "en": ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"],
    "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
}

# Same strftime-locale problem as MONTH_NAMES above, for the abbreviated
# form program_render.py's start_date_text uses (e.g. "15 Aug 2026") -- that
# string is then spliced, unmodified, into export_program_anchored_note's
# ES sentence by both program_pptx.py and export_docx.py, so an unfixed
# English abbreviation here leaks into an otherwise-Spanish sentence even
# though the surrounding template is correctly translated.
MONTH_NAMES_ABBR: dict[str, list[str]] = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "es": ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
          "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
}


def export_month_name(month_number: int, language: str | None, abbreviated: bool = False) -> str:
    """The localized name of `month_number` (1-12). `language=None` (the
    opt-in default used throughout this module's callers) resolves to
    English, matching the un-migrated behaviour every other function here
    falls back to. An out-of-range month number returns ""."""
    lang = (language or "en").strip().lower()[:2]
    table = MONTH_NAMES_ABBR if abbreviated else MONTH_NAMES
    names = table.get(lang, table["en"])
    if 1 <= month_number <= 12:
        return names[month_number - 1]
    return ""


def placeholder_marker(detail: str, language: str | None = None, kind: str = "tbc") -> str:
    """Builds one canonical red placeholder in the project's output language,
    e.g. placeholder_marker("ABN", "es") -> "[POR COMPLETAR: ABN]". `kind`
    selects which prefix family (default "tbc", the to-be-completed marker
    make_placeholder() uses); falls back to English for an unrecognised
    language or kind, same fallback behaviour as export_t()."""
    lang = (language or "").strip().lower()[:2]
    prefixes = PLACEHOLDER_PREFIXES.get(lang, PLACEHOLDER_PREFIXES["en"])
    prefix = prefixes.get(kind) or PLACEHOLDER_PREFIXES["en"].get(kind, "[TO BE COMPLETED")
    detail = (detail or "").strip()
    return f"{prefix}: {detail}]" if detail else f"{prefix}]"


def canonical_marker_instruction(language: str | None) -> str:
    """Round 3, Part 1c: the shared "use only the canonical Spanish
    placeholder prefixes" instruction fragment, appended to an AI drafting
    prompt whenever output_language is Spanish. Originally written once,
    inline, in draft_generator.py (Audit Round 2, Part 4) -- factored out
    here so every other AI-drafting module that can produce Spanish-output
    free text (executive_summary.py, team_intro.py, experience_intro.py,
    methodology_stages.py, team_bios.py, pitch_review.py) gets the
    IDENTICAL instruction instead of each carrying its own copy that could
    drift out of sync with PLACEHOLDER_PREFIXES. Without this, a model left
    to its own judgement coins its own marker (e.g. "[EL USUARIO DEBE
    INSERTAR...]"), which export_docx.collect_placeholders()'s fixed-prefix
    sweep never matches -- a Spanish pack silently under-reports what still
    needs a human.

    Returns "" for anything other than "es" -- callers should simply
    concatenate the result onto their existing prompt/instruction string,
    so an English-output call is a harmless no-op.

    risk_register.py deliberately does NOT call this: its two AI-written
    fields (impact/mitigation) already use a single literal marker, "TBC",
    kept unchanged in every language by its own prompt instruction -- a
    structural placeholder the export sweep matches via a dedicated regex
    (export_docx._TBC_RE), not the bracket-prefix family this instruction
    governs. Adding this instruction there would just be a second,
    conflicting placeholder convention for fields that already can't leak
    English into a Spanish document."""
    lang = (language or "").strip().lower()[:2]
    if lang != "es":
        return ""
    _es = PLACEHOLDER_PREFIXES["es"]
    return (
        " Any bracketed placeholder you write for missing information MUST use exactly one of "
        f"these Spanish markers -- never a free translation of your own: {_es['insert']} ...] for "
        f"something to insert, {_es['confirm']} ...] for something to confirm, {_es['tbc']}: ...] "
        f"for something to be completed, {_es['no']} ...] for something not supplied. For example, "
        f"write {_es['insert']}: DETALLE ESPECÍFICO DEL PROYECTO] -- not a paraphrase of it -- so a "
        "reviewer scanning the Spanish draft, and the app's own automated sweep for placeholders, "
        "both reliably find every gap."
    )


# Round 3, Part 4c: methodology_render.stage_carries_hold_point() and
# program_render.build_model()'s milestone derivation both detect a "hold
# point" by scanning a stage's own AI-drafted engagement-activities/outcome
# text for the English phrase "hold point" -- which never matches once that
# text is legitimately in Spanish, silently dropping the hold-point gate
# diamond and the delivery-program milestone for every Spanish project. Both
# scan the SAME free-text field this canonical phrase governs, so one fixed
# Spanish phrase (paired with the prompt instruction below telling the
# drafter to use it verbatim, the same convention canonical_marker_instruction()
# already established for placeholders) fixes both detectors at once.
HOLD_POINT_PHRASES: dict[str, str] = {
    "en": "hold point",
    "es": "punto de espera",
}


def mentions_hold_point(text) -> bool:
    """True if `text` names a hold point in EITHER language this catalog
    covers -- deliberately not gated on the project's own output_language,
    since a mixed-language document (a language switched mid-project, or a
    stage edited by hand) should still have its hold points detected."""
    haystack = str(text or "").lower()
    return any(phrase in haystack for phrase in HOLD_POINT_PHRASES.values())


def hold_point_phrasing_instruction(language: str | None) -> str:
    """Round 3, Part 4c: tells the stage-drafting AI call to use the single
    canonical Spanish phrase for a hold point, the same way
    canonical_marker_instruction() pins down the bracketed-placeholder
    vocabulary -- without this, a model left to its own judgement might
    write "punto de retención" or "hito de aprobación del cliente" instead,
    which mentions_hold_point() would never recognise as one.

    Returns "" for anything other than "es" -- concatenate onto an existing
    prompt, same calling convention as canonical_marker_instruction()."""
    lang = (language or "").strip().lower()[:2]
    if lang != "es":
        return ""
    phrase = HOLD_POINT_PHRASES["es"]
    return (
        f" Whenever a task, engagement activity, or outcome genuinely is a hold point (a point "
        f"where work pauses for the client's review/approval before continuing), name it using "
        f"the exact phrase \"{phrase}\" somewhere in that text -- never a paraphrase of your own "
        f"(not \"punto de retención\", not \"hito de aprobación\") -- so the app's own automated "
        f"detection of hold points, which matches on that exact phrase, reliably finds every one "
        f"you write. Only label something a hold point if the inputs actually describe one; do "
        f"not invent one that wasn't there."
    )


def export_t(key: str, language: str | None, **fmt) -> str:
    """Looks up `key` in `language`'s export catalog, falling back to English,
    then to a visibly-broken `[[key]]` marker if the key exists in neither --
    mirrors modules/i18n.t()'s fallback behaviour so a missing translation
    fails loud instead of silently, but is otherwise an entirely independent
    system (see module docstring above -- this is a per-PROJECT output
    language, not the per-session UI language modules/i18n.py drives).
    `**fmt` is applied with str.format_map against the resolved string when
    given, e.g. export_t("heading_letter_intro", "es", n=1)."""
    lang = (language or "").strip().lower()[:2]
    catalog = _CATALOGS.get(lang, _EN)
    text = catalog.get(key) or _EN.get(key)
    if text is None:
        return f"[[{key}]]"
    if fmt:
        try:
            return text.format(**fmt)
        except Exception:
            return text
    return text

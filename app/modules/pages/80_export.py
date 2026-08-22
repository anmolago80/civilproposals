# modules/pages/80_export.py -- one segment of the CivilProposals app script.
# Tab 10 Export Pack (DOCX/PPTX generation, proposal library, returnable schedules) and the end-of-run autosave.
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
# Tab 10: Export Pack
# ---------------------------------------------------------------------------

with tabs[9]:
    st.subheader(i18n.t("export_subheader"))

    # Audit fix Part 2c: _mark_free_artifact_downloaded() (10_state_helpers.py)
    # now distinguishes a genuine database failure from the expected
    # duplicate-key "already downloaded" case -- a genuine failure sets this
    # flag instead of silently granting an unmetered extra download. Shown
    # once, then cleared, same "read it once" pattern as a st.toast.
    if st.session_state.pop("_free_artifact_mark_error", None):
        st.warning(i18n.t("export_download_mark_failed_warning"))

    # Part B2: passes-remaining indicator for a paid project -- the brief's
    # own "sidebar/readiness pass counter" requirement, placed here (right
    # above the readiness checklist) rather than the sidebar itself, since
    # passes are a PER-PROJECT figure and the sidebar's plan/status block is
    # already a per-ACCOUNT one (see modules/pages/20_chrome.py) -- mixing
    # the two there would misleadingly imply passes are account-wide.
    # Nothing shown at all for a trial-funded project (trial_remaining in
    # the sidebar already covers that), for UNLIMITED_ACCOUNTS, or outside
    # SaaS mode.
    _export_passes = _project_passes_status()
    if _export_passes["has_passes"]:
        if _export_passes["remaining"] > 0:
            st.caption("🎫 " + i18n.t(
                "passes_remaining_caption",
                remaining=_export_passes["remaining"], total=_export_passes["purchased"],
            ))
        else:
            st.warning(i18n.t("passes_exhausted"))
            # Audit fix Part 8: was a two-step button-then-link_button flow
            # -- the exact vanishing-link bug 00_init.py's own comment
            # documents and _render_upgrade_buttons() was rewritten to
            # avoid (see that function's docstring). A single link_button,
            # backed by the same cached-URL helper, removes the round trip.
            try:
                _topup_url = _get_or_create_checkout_url(current_user, "bid", topup_project_key=_current_project_key())
                st.link_button(i18n.t("passes_topup_button"), _topup_url, key="_export_passes_topup_btn", type="primary")
            except Exception as exc:
                _show_error("Couldn't start checkout", exc)
    elif _project_is_free_tier():
        # Audit fix Part 1a: a trial-funded project whose one free pass is
        # already spent gets the SAME "buy a bid, unlock this project"
        # path as the paid-and-exhausted case above -- previously nothing
        # here offered a project-specific purchase at all, only the
        # generic "start a new project" buttons elsewhere in the app,
        # which never actually unlocked the project someone's stuck on.
        st.warning(i18n.t("free_tier_generate_used"))
        try:
            _unlock_url = _get_or_create_checkout_url(current_user, "bid", topup_project_key=_current_project_key())
            st.link_button(
                "Buy 1 bid -- $50, to unlock this project →", _unlock_url,
                key="_export_free_tier_unlock_btn", type="primary",
            )
        except Exception as exc:
            _show_error("Couldn't start checkout", exc)

    # Readiness checklist. Most of the red in an exported pack is not missing
    # information -- it is a step that hasn't been run. Listing those here,
    # each with where to go, turns a silently red document into a short list
    # of actions before anyone opens the file and starts wondering.
    _readiness = _export_readiness()
    if _readiness:
        with st.expander(i18n.t("export_readiness_expander", n=len(_readiness)),
                         expanded=True):
            for _item in _readiness:
                st.markdown(
                    i18n.t("export_readiness_item", label=_item['label'], where=_item['where'])
                    + (f". {_item['detail']}" if _item["detail"] else "")
                )
            st.caption(i18n.t("export_readiness_caption"))
    else:
        st.success(i18n.t("export_readiness_all_done_success"))

    if _is_letter():
        st.caption(i18n.t("export_letter_intro_caption"))
        ready = st.session_state.sections is not None
        if not ready:
            st.info(i18n.t("export_generate_structure_first_info"))

        if _structure_format_stale():
            st.warning(i18n.t("export_letter_structure_stale_warning"))

        if st.button(i18n.t("export_generate_letter_docx_button"), type="primary", disabled=not ready):
            with st.spinner(i18n.t("export_assembling_spinner")):
                cover_image = _cover_photo_bytes()
                sender = {
                    "name": st.session_state.letter_sender_name,
                    "title": st.session_state.letter_sender_title,
                    "phone": st.session_state.letter_sender_phone,
                    "email": st.session_state.letter_sender_email,
                }
                understanding_draft = (st.session_state.drafts or {}).get("Project Understanding")
                understanding_text = understanding_draft.draft_text if understanding_draft else ""
                methodology_draft = (st.session_state.drafts or {}).get("Methodology and Deliverables")
                methodology_text = methodology_draft.draft_text if methodology_draft else ""
                buffer = export_docx.build_letter_docx(
                    project_info=_project_info(),
                    firm=_firm_export_context(),
                    risk_register=st.session_state.risk_register,
                    fee_sections_included=st.session_state.fee_sections_included,
                    scope_item_fees=st.session_state.scope_item_fees,
                    sender=sender,
                    analysis=st.session_state.analysis,
                    understanding_text=understanding_text,
                    methodology_text=methodology_text,
                    resource_plan=st.session_state.resource_plan,
                    personnel_photos=st.session_state.personnel_photos,
                    program_schedule=st.session_state.program_schedule,
                    program_week_labels=st.session_state.program_week_labels,
                    terms_of_engagement_text=st.session_state.terms_of_engagement_text,
                    executive_summary=st.session_state.executive_summary,
                    cover_image_bytes=cover_image,
                    cover_theme_image_bytes=st.session_state.cover_hero_png,
                    fee_estimates=st.session_state.fee_estimates,
                    discipline_fee_lines=st.session_state.discipline_fee_lines,
                    differentiator_text=st.session_state.project_differentiator,
                    sales_pitch_text=st.session_state.project_sales_pitch,
                    ocr_note=_ocr_export_note(),
                    program_style=st.session_state.program_style,
                    methodology_stages=st.session_state.methodology_stages,
                    program_start_date=st.session_state.program_start_date,
                    output_language=st.session_state.get("output_language", "en"),
                )
                st.session_state.docx_buffer = buffer
                _mark_export_generated()

                # Same companion internal document the Large Scope pack generates
                # alongside its own DOCX (see export_docx.build_tender_summary_docx) --
                # a guide to the brief's main requirements (scope/objectives/mandatory
                # requirements/deliverables/risks), plus whatever compliance matrix and
                # gap analysis the user chose to run in Proposal Structure (tab 4), kept
                # OUT of the proposal itself. Small Scope packs don't generate an
                # evaluation weighting chart, so that section is simply omitted.
                # Read the just-built proposal back and list every placeholder
                # actually in it -- the compliance/draft lists between them
                # miss most of what really ends up red on the page.
                _doc_placeholders = _placeholders_in_generated_pack(buffer)
                st.session_state.tender_summary_buffer = export_docx.build_tender_summary_docx(
                    project_info=_project_info(),
                    analysis=st.session_state.analysis,
                    weighting_chart_png=st.session_state.weighting_chart_png,
                    compliance_items=st.session_state.compliance_items or [],
                    gap_items=st.session_state.gap_items or [],
                    sections=st.session_state.sections,
                    drafts=st.session_state.drafts or {},
                    body_font=st.session_state.body_font,
                    ocr_note=_ocr_export_note(),
                    document_placeholders=_doc_placeholders,
                    output_language=st.session_state.get("output_language", "en"),
                )
            st.success(i18n.t("export_document_generated_success"))
    else:
        st.caption(i18n.t("export_formal_intro_caption"))

        ready = st.session_state.sections is not None and st.session_state.guidance_notes is not None
        if not ready:
            st.info(i18n.t("export_formal_generate_structure_first_info"))

        if _structure_format_stale():
            st.warning(i18n.t("export_formal_structure_stale_warning"))

        if st.button(i18n.t("export_generate_docx_button"), type="primary", disabled=not ready):
            with st.spinner(i18n.t("export_assembling_spinner")):
                cover_image = _cover_photo_bytes()

                # Same override the Fee Estimate tab's "Indicative fee split by discipline"
                # section applies to its own on-screen table/Excel/chart: a manually-entered
                # total project fee takes priority, else the discipline fee build-up's own $
                # total, else nothing -- without this, the proposal's fee table could show "-"
                # for every discipline even though the app's own Fee Estimate tab was showing
                # real dollar figures for the same split.
                _manual_fee_total = st.session_state.get("fee_estimate_manual_total") or 0
                _buildup_fee_total = sum(l.fee_amount for l in (st.session_state.discipline_fee_lines or []))
                _fee_indicative_amounts = {
                    e.discipline: (
                        _manual_fee_total * e.fee_percentage / 100 if _manual_fee_total > 0
                        else (_buildup_fee_total * e.fee_percentage / 100 if _buildup_fee_total else None)
                    )
                    for e in (st.session_state.fee_estimates or [])
                }

                buffer = export_docx.build_docx(
                    project_info=_project_info(),
                    analysis=st.session_state.analysis,
                    weighted_criteria=st.session_state.weighted_criteria or [],
                    allocations=st.session_state.allocations or [],
                    sections=st.session_state.sections,
                    guidance_notes=st.session_state.guidance_notes,
                    drafts=st.session_state.drafts or {},
                    compliance_items=st.session_state.compliance_items or [],
                    gap_items=st.session_state.gap_items or [],
                    graphics=st.session_state.graphics or [],
                    fee_estimates=st.session_state.fee_estimates,
                    weighting_chart_png=st.session_state.weighting_chart_png,
                    cover_image_bytes=cover_image,
                    cover_theme_image_bytes=st.session_state.cover_hero_png,
                    divider_images=st.session_state.divider_images,
                    resource_plan=st.session_state.resource_plan,
                    org_chart_png=st.session_state.org_chart_png,
                    body_font=st.session_state.body_font,
                    personnel_photos=st.session_state.personnel_photos,
                    reference_projects=st.session_state.reference_projects,
                    reference_project_photos=st.session_state.reference_project_photos,
                    discipline_fee_lines=st.session_state.discipline_fee_lines,
                    executive_summary=st.session_state.executive_summary,
                    fee_estimate_indicative_amounts=_fee_indicative_amounts,
                    team_intro=st.session_state.team_intro,
                    experience_intro=st.session_state.experience_intro,
                    differentiator_text=st.session_state.project_differentiator,
                    sales_pitch_text=st.session_state.project_sales_pitch,
                    ocr_note=_ocr_export_note(),
                    # Feeds the Commercial section's derived cash-flow profile
                    # (export_docx.cash_flow_rows) -- the priced fee build-up
                    # spread over the weeks this program actually has work in.
                    program_schedule=st.session_state.program_schedule,
                    program_week_labels=st.session_state.program_week_labels,
                    firm=_firm_export_context(),
                    # Which fee presentations reach the proposal is the
                    # user's choice (Fee Estimate tab), not the pack format's.
                    fee_sections_included=st.session_state.fee_sections_included,
                    scope_item_fees=st.session_state.scope_item_fees,
                    # The methodology body content is now just the red
                    # "paste the finished table here" placeholder note --
                    # build_docx no longer takes a stages image to embed.
                    output_language=st.session_state.get("output_language", "en"),
                )
                st.session_state.docx_buffer = buffer
                _mark_export_generated()

                # Companion internal document -- everything that's about how the
                # brief was read and how this pack was assembled (tender summary,
                # compliance matrix, gap analysis, review checklist, user-input
                # list), kept OUT of the proposal itself so that document is only
                # the proposal. Generated alongside it, same click.
                # Read the just-built proposal back and list every placeholder
                # actually in it -- the compliance/draft lists between them
                # miss most of what really ends up red on the page.
                _doc_placeholders = _placeholders_in_generated_pack(buffer)
                st.session_state.tender_summary_buffer = export_docx.build_tender_summary_docx(
                    project_info=_project_info(),
                    analysis=st.session_state.analysis,
                    weighting_chart_png=st.session_state.weighting_chart_png,
                    compliance_items=st.session_state.compliance_items or [],
                    gap_items=st.session_state.gap_items or [],
                    sections=st.session_state.sections,
                    drafts=st.session_state.drafts or {},
                    body_font=st.session_state.body_font,
                    ocr_note=_ocr_export_note(),
                    document_placeholders=_doc_placeholders,
                    output_language=st.session_state.get("output_language", "en"),
                )
            st.success(i18n.t("export_document_generated_success"))

    if st.session_state.docx_buffer:
        if _export_is_stale():
            st.warning(i18n.t("export_stale_files_warning"))
        filename = (st.session_state.tender_name or "tender_response_pack").replace(" ", "_")
        suffix = "small_scope_pack" if _is_letter() else "large_scope_pack"
        # Small Scope: DOCX + Tender Summary. Large Scope: DOCX + Org Chart + Methodology
        # Table + Program, all PPTX, + Tender Summary.
        dcols = st.columns(2 if _is_letter() else 5)
        with dcols[0]:
            # Part B: the Proposal DOCX is one of the three free-tier
            # artifacts (see FREE_TIER_ARTIFACTS in 10_state_helpers.py) --
            # a trial-funded project gets exactly one download of it; a
            # paid/unlimited project always gets it. _mark_free_artifact_downloaded
            # is a no-op for anything other than a free-tier project's
            # first download, so it's always safe to call right after a
            # successful click.
            if _free_artifact_download_blocked("proposal_docx"):
                st.button(i18n.t("export_download_docx_button"), disabled=True, type="primary", key="_dl_docx_blocked")
                st.caption(i18n.t("free_tier_artifact_used"))
            else:
                # Audit fix Part 2a: marked via on_click=, not by checking
                # st.download_button()'s return value on the FOLLOWING
                # rerun. The old pattern re-evaluated the gate BEFORE the
                # mark ran (this same `if _free_artifact_download_blocked`
                # check, at the top of the next script run, still saw "not
                # yet used"), so the button rendered enabled for one more
                # rerun and a fast second click served the file again.
                # on_click fires as part of handling this click itself, so
                # the mark commits before any later render can decide
                # whether to show this button enabled again.
                st.download_button(
                    i18n.t("export_download_docx_button"), data=st.session_state.docx_buffer,
                    file_name=f"{filename}_{suffix}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                    on_click=_mark_free_artifact_downloaded, args=("proposal_docx",),
                )
        # All three PowerPoint companions below used to be rebuilt from
        # scratch on EVERY rerun of the script -- so every keystroke, every
        # checkbox, every tab change re-ran three full presentation builds
        # whose inputs hadn't changed. _cached_pptx keeps the last result per
        # artefact, keyed by a signature of the data that actually goes into
        # it, and rebuilds only when that signature moves.
        def _methodology_stage_signature():
            """Value signature of the reviewed stage grid, for the PPTX cache
            and the DOCX image -- an edit to any cell has to invalidate both."""
            return tuple(
                (s.name, s.week_start, s.week_end, tuple(s.key_tasks),
                 tuple(s.engagement_activities), s.outcome, tuple(s.deliverables))
                for s in (st.session_state.methodology_stages or [])
            )

        def _cached_pptx(name: str, signature, build):
            cache = st.session_state.setdefault("_pptx_cache", {})
            entry = cache.get(name)
            if entry is not None and entry[0] == signature:
                return entry[1]
            blob = build()
            cache[name] = (signature, blob)
            return blob

        # The formal pack's Key Personnel section leaves an explicit placeholder for the
        # org chart (see export_docx._build_personnel_block) rather than embedding the
        # auto-generated preview -- the finished chart is built in PowerPoint and pasted
        # in by hand. Build that PowerPoint fresh from this project's actual resourcing
        # plan (see org_chart_pptx.populate_org_chart) right next to the DOCX download,
        # so it's never a separate hunt. Every discipline in resource_plan gets its own
        # column, showing that discipline's Lead name (or a red "TBC" if nobody's
        # assigned yet) PLUS any support members added under that lead. The client's own
        # PM counterpart and subconsultant firms have no equivalent in the app's data and
        # simply aren't shown, same no-invention rule as everywhere else in this tool. The Small Scope pack doesn't have a Key
        # Personnel/org chart section, so skip it there.
        if not _is_letter():
            with dcols[1]:
                # Part B: the third free-tier artifact -- same one-download
                # gate as the DOCX above, checked BEFORE the (non-trivial)
                # PPTX build, so a project that's already used its free
                # download doesn't pay the render cost for a file it can't
                # have.
                if _free_artifact_download_blocked("org_chart_pptx"):
                    st.button(i18n.t("export_download_orgchart_button"), disabled=True, type="primary", key="_dl_orgchart_blocked")
                    st.caption(i18n.t("free_tier_artifact_used"))
                else:
                    try:
                        chart_bytes = _cached_pptx(
                            "org_chart",
                            _org_signature(st.session_state.org_chart_style),
                            lambda: org_chart_pptx.populate_org_chart(
                                st.session_state.resource_plan or [],
                                client_name=st.session_state.client_name,
                                project_name=st.session_state.project_name,
                                tender_name=st.session_state.tender_name,
                                theme_name=st.session_state.proposal_theme,
                                style=st.session_state.org_chart_style,
                            ),
                        )
                        # Audit fix Part 2a -- see the proposal DOCX button above.
                        st.download_button(
                            i18n.t("export_download_orgchart_button"),
                            data=chart_bytes,
                            file_name="Org_Chart.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            type="primary",
                            on_click=_mark_free_artifact_downloaded, args=("org_chart_pptx",),
                        )
                        st.caption(i18n.t("export_orgchart_caption"))
                    except Exception:
                        # Never let a chart-generation bug block the DOCX download that
                        # actually matters -- just skip the org chart download this time.
                        st.caption(i18n.t("export_orgchart_build_failed_caption"))

        # Same placeholder-in-DOCX / finish-in-PowerPoint pattern as the org chart
        # above (see export_docx._build_methodology_table). Four generic stage
        # columns (Project Initiation, then three progressively-developed design
        # stages), themed to match this proposal's chosen colours (see
        # methodology_pptx.populate_methodology). Column 1 is standard
        # boilerplate; column 2's Key tasks are built straight from this
        # project's real scope items (title + tasks), never invented. Columns
        # 3-4 cover stages the brief doesn't describe, so they stay explicit red
        # "[CONFIRM ...]" placeholders, same no-invention rule as everywhere
        # else in this tool. The legend's client-name hold-point label is
        # populated from Project Setup, showing a red placeholder if not yet
        # entered.
        if not _is_letter():
            with dcols[2]:
                # Part B: NOT one of the three free-tier artifacts -- always
                # paid-only, for every free-tier project, regardless of
                # whether its one free download has been used yet.
                if _free_artifact_download_blocked("methodology_pptx"):
                    st.button(i18n.t("export_download_methodology_button"), disabled=True, type="primary", key="_dl_methodology_blocked")
                    st.caption(i18n.t("free_tier_paid_only_caption"))
                else:
                    try:
                        methodology_bytes = _cached_pptx(
                            "methodology",
                            (
                                st.session_state.methodology_style,
                                _methodology_stage_signature(),
                                tuple((i.title, tuple(i.tasks))
                                      for i in (getattr(st.session_state.analysis, "scope_items", None) or [])),
                                tuple(st.session_state.program_week_labels or []),
                                st.session_state.client_name, st.session_state.project_name,
                                st.session_state.proposal_theme,
                                bool(st.session_state.methodology_wvr_confirmed),
                            ),
                            lambda: methodology_pptx.populate_methodology(
                                st.session_state.analysis,
                                client_name=st.session_state.client_name,
                                project_name=st.session_state.project_name,
                                theme_name=st.session_state.proposal_theme,
                                stages=st.session_state.methodology_stages,
                                week_labels=st.session_state.program_week_labels,
                                wvr_confirmed=bool(st.session_state.methodology_wvr_confirmed),
                                style=st.session_state.methodology_style,
                            ),
                        )
                        st.download_button(
                            i18n.t("export_download_methodology_button"),
                            data=methodology_bytes,
                            file_name="Methodology_Table.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                         type="primary")
                        st.caption(
                            i18n.t("export_methodology_caption_has_stages")
                            if st.session_state.methodology_stages else
                            i18n.t("export_methodology_caption_no_stages")
                        )
                    except Exception:
                        # Never let a chart-generation bug block the DOCX download that
                        # actually matters -- just skip the methodology table download this time.
                        st.caption(i18n.t("export_methodology_build_failed_caption"))

        # Same PPTX-companion pattern as the org chart / methodology table above -- the
        # Large Scope pack's DOCX has no Program section of its own (unlike the Small
        # Scope pack, which embeds one inline), so the delivery program built in the Fee
        # Estimate tab is exported here instead, as an editable Gantt-style table (see
        # program_pptx.populate_program) to paste into a program/methodology slide.
        if not _is_letter():
            with dcols[3]:
                # Part B: also not on the free list -- always paid-only.
                if _free_artifact_download_blocked("program_pptx"):
                    st.button(i18n.t("export_download_program_button"), disabled=True, type="primary", key="_dl_program_blocked")
                    st.caption(i18n.t("free_tier_paid_only_caption"))
                else:
                    try:
                        program_bytes = _cached_pptx(
                            "program",
                            _program_signature(st.session_state.program_style),
                            lambda: program_pptx.populate_program(
                                st.session_state.program_schedule or {},
                                st.session_state.program_week_labels or [],
                                client_name=st.session_state.client_name,
                                project_name=st.session_state.project_name,
                                theme_name=st.session_state.proposal_theme,
                                style=st.session_state.program_style,
                                methodology_stages=st.session_state.methodology_stages,
                                start_date=st.session_state.program_start_date,
                                analysis=st.session_state.analysis,
                            ),
                        )
                        st.download_button(
                            i18n.t("export_download_program_button"),
                            data=program_bytes,
                            file_name="Delivery_Program.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                         type="primary")
                        st.caption(i18n.t("export_program_caption"))
                    except Exception:
                        # Never let a chart-generation bug block the DOCX download that
                        # actually matters -- just skip the program download this time.
                        st.caption(i18n.t("export_program_build_failed_caption"))

        # The Tender Summary is a separate document (see export_docx.build_tender_summary_docx),
        # generated in the same click as the Proposal DOCX above -- everything about how the
        # brief was read and how this pack was assembled (a guide to the brief's main
        # requirements, plus the compliance matrix, gap analysis, review checklist, and
        # user-input list, where generated) lives here instead of inside the proposal itself.
        # Available for both pack sizes -- the Small Scope pack just won't have an evaluation
        # weighting chart or (unless run manually in tab 4) a compliance matrix/gap analysis.
        with dcols[1 if _is_letter() else 4]:
            if st.session_state.tender_summary_buffer:
                # Part B: the second free-tier artifact.
                if _free_artifact_download_blocked("tender_summary_docx"):
                    st.button(i18n.t("export_download_tendersummary_button"), disabled=True, type="primary", key="_dl_tendersummary_blocked")
                    st.caption(i18n.t("free_tier_artifact_used"))
                else:
                    # Audit fix Part 2a -- see the proposal DOCX button above.
                    st.download_button(
                        i18n.t("export_download_tendersummary_button"),
                        data=st.session_state.tender_summary_buffer,
                        file_name=f"{filename}_tender_summary.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        on_click=_mark_free_artifact_downloaded, args=("tender_summary_docx",),
                    )
                    st.caption(i18n.t("export_tendersummary_caption"))
            else:
                st.caption(i18n.t("export_tendersummary_pending_caption"))

        st.divider()
        st.markdown(i18n.t("export_library_heading"))
        st.caption(i18n.t(
            "export_library_caption",
            project_type=st.session_state.project_type or i18n.t("export_library_project_type_placeholder"),
        ))
        if st.button(i18n.t("export_archive_button"), key="archive_to_library_btn", type="primary"):
            try:
                _archived = proposal_library.archive_proposal(
                    _lib_user_id(),
                    st.session_state.docx_buffer.getvalue(),
                    project_type=st.session_state.project_type,
                    pack_type="small_scope" if _is_letter() else "large_scope",
                    project_name=st.session_state.project_name,
                    client_name=st.session_state.client_name,
                    tender_name=st.session_state.tender_name,
                )
                # Archiving is the strongest signal that this pricing is real
                # and finished, so the fee snapshot is refreshed here too. The
                # upsert in fee_history keeps it from counting as a second bid.
                _record_fee_snapshot()
                st.success(i18n.t("export_archive_success", project_type=_archived['project_type'], filename=_archived['filename']))
            except Exception as exc:
                _show_error(i18n.t("export_archive_failed_error"), exc)

    # -----------------------------------------------------------------------
    # Returnable schedules -- fill the client's own response forms (DOCX
    # tables/forms, XLSX schedules) from this project's data, preserving
    # their original formatting (see modules/returnable_schedules.py).
    # Available whether or not the proposal DOCX has been generated: the
    # schedules only need project data, not the pack.
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown(i18n.t("export_schedules_heading"))
    if _project_is_free_tier():
        st.caption(i18n.t("free_tier_paid_only_caption"))
    # The prefix shown here must match what make_placeholder() will actually
    # write for THIS project's output_language (Audit Round 2, Part 4) --
    # not always the English default.
    _sched_lang = (st.session_state.get("output_language") or "en")
    _sched_prefix = export_i18n.PLACEHOLDER_PREFIXES.get(_sched_lang, export_i18n.PLACEHOLDER_PREFIXES["en"])["tbc"]
    st.caption(i18n.t("export_schedules_caption", placeholder_prefix=_sched_prefix))
    _extra_scheds = st.file_uploader(
        i18n.t("export_add_schedules_label"), type=["docx", "xlsx", "xlsm"],
        accept_multiple_files=True, key="_returnable_sched_uploader",
    )
    if _extra_scheds:
        for _f in _extra_scheds:
            _name = _f.name
            if _name not in (st.session_state.returnable_schedule_files or {}):
                if _name.lower().endswith(".docx") and not returnable_schedules.looks_like_response_form(_name, _f.getvalue()):
                    st.info(i18n.t("export_schedule_not_form_info", name=_name))
                st.session_state.returnable_schedule_files = {
                    **(st.session_state.returnable_schedule_files or {}),
                    _name: _f.getvalue(),
                }

    _sched_files = st.session_state.returnable_schedule_files or {}
    if not _sched_files:
        st.caption(i18n.t("export_no_schedules_caption"))
    else:
        _sched_names = sorted(_sched_files)
        st.write(i18n.t("export_schedules_ready_prefix", n=len(_sched_names)) + ", ".join(f"`{n}`" for n in _sched_names))
        _rm_col1, _rm_col2 = st.columns([3, 1])
        with _rm_col2:
            _keep_all_option = i18n.t("export_keep_all_option")
            _to_remove = st.selectbox(i18n.t("export_remove_file_label"), [_keep_all_option] + _sched_names, key="_sched_remove_pick",
                                      label_visibility="collapsed")
            if _to_remove != _keep_all_option and st.button(i18n.t("export_remove_button"), key="_sched_remove_btn"):
                _new = dict(_sched_files)
                _new.pop(_to_remove, None)
                st.session_state.returnable_schedule_files = _new
                st.rerun()
        with _rm_col1:
            if st.button(i18n.t("export_fill_schedules_button"), type="primary", key="_fill_scheds_btn"):
                # Firm-level answers (ABN, insurances, certifications,
                # registered address) come from the firm profile -- these
                # labels were permanently placeholdered before it existed.
                _fill_data = returnable_schedules.build_fill_data(
                    st.session_state, firm_profile.schedule_fill_data(_firm_profile()),
                )
                _results = []
                with st.spinner(i18n.t("export_filling_spinner", n=len(_sched_names))):
                    for _name in _sched_names:
                        _results.append(returnable_schedules.fill_schedule(_name, _sched_files[_name], _fill_data))
                st.session_state._sched_fill_results = _results

        for _res in st.session_state.get("_sched_fill_results") or []:
            st.markdown(f"**{_res.filename}**")
            if _res.error:
                st.warning(_res.error)
                continue
            _fcol1, _fcol2 = st.columns([1, 3])
            with _fcol1:
                # Part B: filled returnable schedules aren't on the free
                # list either -- always paid-only for a free-tier project.
                if _free_artifact_download_blocked("returnable_schedule"):
                    st.button(i18n.t("export_download_filled_button"), disabled=True, type="primary", key=f"_sched_dl_blocked_{_res.filename}")
                else:
                    st.download_button(
                        i18n.t("export_download_filled_button"),
                        data=_res.file_bytes,
                        file_name=returnable_schedules.filled_filename(_res.filename),
                        mime=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                              if _res.kind == "docx" else
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                        key=f"_sched_dl_{_res.filename}",
                        type="primary",
                    )
            with _fcol2:
                st.caption(i18n.t(
                    "export_schedule_fill_summary_caption",
                    filled=len(_res.filled), placeholdered=len(_res.placeholdered),
                ))
            if _res.filled or _res.placeholdered:
                with st.expander(i18n.t("export_schedule_detail_expander", filename=_res.filename)):
                    if _res.filled:
                        st.markdown(i18n.t("export_filled_heading"))
                        st.dataframe(
                            [{i18n.t("export_col_where"): f["where"], i18n.t("export_col_field"): f["label"], i18n.t("export_col_value"): f["value"]} for f in _res.filled],
                            use_container_width=True, hide_index=True,
                        )
                    if _res.placeholdered:
                        st.markdown(i18n.t("export_placeholdered_heading"))
                        st.dataframe(
                            [{i18n.t("export_col_where"): f["where"], i18n.t("export_col_field"): f["label"]} for f in _res.placeholdered],
                            use_container_width=True, hide_index=True,
                        )


# ---------------------------------------------------------------------------
# Auto-save -- runs once per script execution, after every tab above has had
# a chance to mutate session_state, so it captures this run's latest state.
# ---------------------------------------------------------------------------

_maybe_autosave()

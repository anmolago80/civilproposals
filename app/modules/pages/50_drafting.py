# modules/pages/50_drafting.py -- one segment of the CivilProposals app script.
# Tab 6 Draft Responses (drafting, differentiator/sales pitch, red-team review).
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
# Tab 6: Draft Responses
# ---------------------------------------------------------------------------

with tabs[5]:
    st.subheader(i18n.t("drafting_subheader"))
    if _is_letter():
        st.caption(i18n.t("drafting_letter_caption"))
    else:
        st.caption(i18n.t("drafting_standard_caption"))

    ready = (
        st.session_state.sections is not None
        and bool(st.session_state.ai_config.get("api_key"))
        and _current_project_already_paid()
    )
    if not ready:
        if st.session_state.sections is not None and not _current_project_already_paid():
            st.info(_ai_block_reason())
        else:
            # TODO A2 i18n: _AI_HINT_CLAUSE is defined (English-only) in
            # 00_init.py, out of scope for this pass -- only the surrounding
            # sentence is translated here.
            st.info(i18n.t("drafting_generate_structure_and_hint", hint=_AI_HINT_CLAUSE))

    if _structure_format_stale():
        st.warning(i18n.t("drafting_format_stale_warning"))

    # Audit fix Part 3a: a full "Generate/Regenerate All Drafts" run is a
    # full generation cycle under Part B2's definition -- tell the user
    # up front whether clicking it will spend one of a paid project's
    # passes (only when this project's drafting inputs have genuinely
    # changed since the last metered run; free on the very first run and
    # on any re-run with unchanged inputs -- see _draft_would_consume_pass()).
    if ready:
        _draft_metered, _ = _draft_project_is_metered()
        if _draft_metered:
            if _draft_would_consume_pass():
                st.caption(i18n.t("drafting_regen_will_use_pass_caption"))
            else:
                st.caption(i18n.t("drafting_regen_no_pass_caption"))

    if st.button(i18n.t("drafting_generate_button"), type="primary", disabled=not ready):
        targets = _draftable_sections(st.session_state.sections)
        if not targets:
            st.error(i18n.t("drafting_nothing_to_draft_error"))
            st.stop()

        # Spend the pass (if this run needs one) BEFORE the AI work starts --
        # same atomic-guarded-update, pre-run pattern as Tender Analysis's
        # repeat-run metering (Part 1c).
        _draft_metered, _draft_key = _draft_project_is_metered()
        _draft_pass_ok = True
        if _draft_metered and _draft_would_consume_pass():
            _draft_pass_ok = auth.consume_project_pass(current_user, _draft_key)
            if not _draft_pass_ok:
                st.warning(i18n.t("passes_exhausted"))

        if _draft_pass_ok:
            progress = st.progress(0.0, text=i18n.t("drafting_progress_text"))

            def _progress_cb(done, total, title):
                # generate_all_drafts() now runs sections concurrently and calls
                # this AFTER each one finishes (done is already a 1-indexed
                # completed-count, not "about to start section done+1" like the
                # old sequential version) -- sections may complete out of their
                # original order, so `title` here is whichever one just finished,
                # not necessarily done'th in the list.
                progress.progress(done / max(total, 1), text=i18n.t("drafting_progress_detail", title=title, done=done, total=total))

            try:
                _record_ai_click()
                # Keep excluded personnel (unticked via "Include in proposal" on the
                # Team & Resourcing tab -- e.g. because their CV wasn't provided)
                # out of the material fed to the AI, not just the nominated-team
                # list: their own CV text would otherwise still let the drafting
                # model surface their name in section prose.
                _excluded_names = resourcing.excluded_personnel_names(st.session_state.resource_plan)
                _material_for_draft = dict(st.session_state.company_material_text)
                if _excluded_names:
                    _cv_files = st.session_state.company_material_files.get("cv_library", {})
                    _excluded_cv_files = team_bios.cv_filenames_for_names(_excluded_names, _cv_files)
                    if _excluded_cv_files:
                        _kept_cv_files = {
                            fn: text for fn, text in _cv_files.items() if fn not in _excluded_cv_files
                        }
                        _material_for_draft["cv_library"] = "\n\n".join(_kept_cv_files.values())

                # Same background-job pattern as Tender Analysis (see that call
                # site's comment and _run_job_or_inline) -- this is the other
                # genuinely slow, heavy operation in the app (up to
                # MAX_CONCURRENT_DRAFTS AI calls in flight at once for a big
                # pack), so it gets the same treatment, including the redacted
                # ai_config on the queued path (see job_queue.py's docstring).
                _redacted_ai_config = {**st.session_state.ai_config, "api_key": ""}

                # Context the drafter never used to receive. All of it already
                # existed in state: the client's own name, the brief's scope items
                # and deliverables, its objectives, the risks it raises, the
                # mandatory requirements, the compliance rows that map to each
                # section, and the bid team's own win themes. A "Methodology and
                # Deliverables" section literally could not list the real
                # deliverables before this.
                _draft_win_themes = "\n\n".join(
                    part for part in (
                        (st.session_state.project_differentiator or "").strip(),
                        (st.session_state.project_sales_pitch or "").strip(),
                    ) if part
                )
                # Structured, user-edited content replaces the raw upload blob for
                # the sections that have it -- otherwise the draft argues from
                # truncated raw text while the cards beside it in the same
                # document show the corrected version.
                _structured_material = _structured_material_by_section(targets)

                _draft_kwargs = {
                    "team_context": draft_generator.format_team_context(st.session_state.resource_plan),
                    "project_info": _project_info(),
                    "compliance_items": st.session_state.compliance_items or [],
                    "win_themes": _draft_win_themes,
                    "structured_material": _structured_material,
                    "output_language": st.session_state.get("output_language", "en"),
                }
                new_drafts = _run_job_or_inline(
                    "draft_generation", draft_generator.generate_all_drafts,
                    args=(targets, st.session_state.analysis, _material_for_draft, st.session_state.ai_config),
                    kwargs=_draft_kwargs,
                    progress=progress,
                    queued_text=i18n.t("drafting_queued_text"), running_text=i18n.t("drafting_progress_text"),
                    inline_extra_kwargs={"progress_callback": _progress_cb},
                    queue_func=job_queue.run_draft_generation_job,
                    queue_args=(targets, st.session_state.analysis, _material_for_draft, _redacted_ai_config),
                )
                st.session_state.drafts = {**(st.session_state.drafts or {}), **new_drafts}
                progress.progress(1.0, text=i18n.t("drafting_done_text"))
                # "Complete" has to mean complete. An empty or one-sentence draft
                # used to render as a blank expander under a green success
                # message, and nobody opens twelve expanders to check.
                _thin = _thin_drafts(new_drafts)
                if _thin:
                    st.warning(i18n.t("drafting_thin_warning", sections=", ".join(_thin)))
                if len(_thin) < len(new_drafts):
                    st.success(i18n.t("drafting_generation_complete_success", n=len(new_drafts) - len(_thin)))
                if _draft_metered:
                    # Record this run's signature as the new baseline --
                    # whether or not THIS run actually spent a pass (a free
                    # first/unchanged run still needs a baseline recorded so
                    # the NEXT comparison has something real to compare
                    # against).
                    st.session_state["_last_draft_metered_signature"] = _draft_generation_input_signature()
            except Exception as exc:
                _show_error(i18n.t("drafting_generation_failed_error"), exc)

    # -----------------------------------------------------------------
    # Risk register
    # -----------------------------------------------------------------
    st.markdown("---")
    st.markdown(i18n.t("drafting_risk_register_heading"))
    st.caption(i18n.t("drafting_risk_register_caption"))
    _risk_ready = (
        st.session_state.analysis is not None
        and bool(st.session_state.ai_config.get("api_key"))
        and _current_project_already_paid()
    )
    rcol1, rcol2 = st.columns([1, 2])
    with rcol1:
        _draft_risk_clicked = st.button(
            i18n.t("drafting_risk_register_button"), type="primary", disabled=not _risk_ready, key="draft_risk_btn",
        )
    with rcol2:
        if not st.session_state.ai_config.get("api_key"):
            st.caption(_AI_HINT_SENTENCE)
        elif not _current_project_already_paid():
            st.caption(_ai_block_reason())
        elif st.session_state.analysis is None:
            st.caption(i18n.t("drafting_risk_run_analysis_caption"))

    if _draft_risk_clicked:
        if st.session_state.risk_register and not st.session_state.get("_confirm_rerisk"):
            st.session_state._confirm_rerisk = True
        else:
            st.session_state._confirm_rerisk = False
            with st.spinner(i18n.t("drafting_spinner_risk_register")):
                try:
                    _record_ai_click()
                    st.session_state.risk_register = risk_register.draft_risk_register(
                        st.session_state.analysis,
                        st.session_state.gap_items or [],
                        st.session_state.ai_config,
                        output_language=st.session_state.get("output_language", "en"),
                    )
                    if not (st.session_state.risk_register.entries if st.session_state.risk_register else []):
                        st.warning(i18n.t("drafting_risk_none_warning"))
                    else:
                        st.success(i18n.t("drafting_risk_structured_success", n=len(st.session_state.risk_register.entries)))
                except Exception as exc:
                    _show_error(i18n.t("drafting_risk_register_failed_error"), exc)

    if st.session_state.get("_confirm_rerisk"):
        st.warning(i18n.t("drafting_risk_confirm_rerisk_warning"))
        if st.button(i18n.t("drafting_cancel_button"), key="cancel_rerisk"):
            st.session_state._confirm_rerisk = False
            st.rerun()

    if st.session_state.risk_register and st.session_state.risk_register.entries:
        _risk_rows = [
            {"Risk": e.risk, "Impact": e.impact, "Mitigation": e.mitigation, "Source": e.source}
            for e in st.session_state.risk_register.entries
        ]
        _edited_risks = st.data_editor(
            _risk_rows, key="risk_register_editor", num_rows="dynamic", use_container_width=True,
            hide_index=True,
            column_config={
                "Risk": st.column_config.TextColumn(i18n.t("drafting_risk_col_risk"), width="medium"),
                "Impact": st.column_config.TextColumn(i18n.t("drafting_risk_col_impact"), width="medium"),
                "Mitigation": st.column_config.TextColumn(i18n.t("drafting_risk_col_mitigation"), width="medium"),
                "Source": st.column_config.TextColumn(i18n.t("drafting_risk_col_source"), disabled=True, width="small"),
            },
        )
        st.session_state.risk_register = risk_register.RiskRegister(entries=[
            risk_register.RiskEntry(
                risk=(row.get("Risk") or "").strip(),
                impact=(row.get("Impact") or "").strip() or risk_register.TBC,
                mitigation=(row.get("Mitigation") or "").strip() or risk_register.TBC,
                source=(row.get("Source") or "").strip(),
            )
            for row in _edited_risks if (row.get("Risk") or "").strip()
        ])
        st.caption(i18n.t("drafting_risk_tbc_caption"))

    # -----------------------------------------------------------------
    # Design stages -- the grid that fills the methodology table
    # -----------------------------------------------------------------
    st.markdown("---")
    st.markdown(i18n.t("drafting_design_stages_heading"))
    st.caption(i18n.t("drafting_design_stages_caption"))

    _stages_ready = (
        st.session_state.analysis is not None
        and bool(st.session_state.ai_config.get("api_key"))
        and _current_project_already_paid()
    )
    _existing_stages = st.session_state.methodology_stages
    _stages_edited = bool(_existing_stages) and any(
        st.session_state.get(f"_stage_dirty_{i}") for i in range(len(_existing_stages))
    )

    scol1, scol2 = st.columns([1, 2])
    with scol1:
        _draft_stages_clicked = st.button(
            i18n.t("drafting_stages_button"), type="primary", disabled=not _stages_ready,
            key="draft_stages_btn",
        )
    with scol2:
        if not st.session_state.ai_config.get("api_key"):
            st.caption(_AI_HINT_SENTENCE)
        elif not _current_project_already_paid():
            st.caption(_ai_block_reason())
        elif st.session_state.analysis is None:
            st.caption(i18n.t("drafting_stages_run_analysis_caption"))

    # Regenerating over edited content needs an explicit second click. AI
    # output must never silently overwrite something a person has changed.
    if _draft_stages_clicked:
        if _existing_stages and not st.session_state.get("_confirm_restage"):
            st.session_state._confirm_restage = True
        else:
            st.session_state._confirm_restage = False
            with st.spinner(i18n.t("drafting_spinner_stages")):
                try:
                    _record_ai_click()
                    _methodology_draft = (st.session_state.drafts or {}).get("Methodology and Deliverables")
                    st.session_state.methodology_stages = methodology_stages.draft_methodology_stages(
                        st.session_state.analysis,
                        methodology_draft_text=_methodology_draft.draft_text if _methodology_draft else "",
                        program_schedule=st.session_state.program_schedule,
                        program_week_labels=st.session_state.program_week_labels,
                        project_info=_project_info(),
                        config=st.session_state.ai_config,
                        output_language=st.session_state.get("output_language", "en"),
                    )
                    if not st.session_state.methodology_stages:
                        st.warning(i18n.t("drafting_stages_none_warning"))
                    else:
                        st.success(i18n.t("drafting_stages_drafted_success", n=len(st.session_state.methodology_stages)))
                except Exception as exc:
                    _show_error(i18n.t("drafting_stages_failed_error"), exc)

    if st.session_state.get("_confirm_restage"):
        st.warning(i18n.t("drafting_stages_confirm_restage_warning"))
        if st.button(i18n.t("drafting_cancel_button"), key="cancel_restage"):
            st.session_state._confirm_restage = False
            st.rerun()

    if not st.session_state.methodology_stages:
        if st.button(i18n.t("drafting_blank_grid_button"), key="blank_stages_btn"):
            st.session_state.methodology_stages = methodology_stages.blank_stages()
            st.rerun()
        st.caption(i18n.t("drafting_no_stages_caption"))
    else:
        _week_labels = st.session_state.program_week_labels or []
        _week_options = [0] + list(range(1, len(_week_labels) + 1))

        def _week_label(index: int) -> str:
            if not index:
                return "-"
            return _week_labels[index - 1] if index <= len(_week_labels) else f"Wk {index}"

        _remove_index = None
        for _i, _stage in enumerate(st.session_state.methodology_stages):
            _stage_title = i18n.t(
                "drafting_stage_title", n=_i + 1,
                name=_stage.name or i18n.t("drafting_stage_untitled"),
            )
            with st.expander(_stage_title, expanded=(_i == 0)):
                _stage.name = st.text_input(i18n.t("drafting_stage_name_label"), value=_stage.name, key=f"_stage_name_{_i}")
                wcol1, wcol2, wcol3 = st.columns([1, 1, 2])
                with wcol1:
                    _ws = st.selectbox(
                        i18n.t("drafting_stage_first_week_label"), _week_options, key=f"_stage_ws_{_i}",
                        index=_week_options.index(_stage.week_start) if _stage.week_start in _week_options else 0,
                        format_func=_week_label,
                    )
                with wcol2:
                    _we = st.selectbox(
                        i18n.t("drafting_stage_last_week_label"), _week_options, key=f"_stage_we_{_i}",
                        index=_week_options.index(_stage.week_end) if _stage.week_end in _week_options else 0,
                        format_func=_week_label,
                    )
                with wcol3:
                    st.write("")
                    st.caption(i18n.t("drafting_week_numbers_caption"))
                _stage.week_start = _ws or None
                _stage.week_end = _we or None

                _stage.key_tasks = [
                    line.strip() for line in st.text_area(
                        i18n.t("drafting_key_tasks_label"), value="\n".join(_stage.key_tasks),
                        key=f"_stage_tasks_{_i}", height=110,
                    ).split("\n") if line.strip()
                ]
                _stage.engagement_activities = [
                    line.strip() for line in st.text_area(
                        i18n.t("drafting_engagement_activities_label"),
                        value="\n".join(_stage.engagement_activities),
                        key=f"_stage_eng_{_i}", height=80,
                    ).split("\n") if line.strip()
                ]
                _stage.outcome = st.text_input(i18n.t("drafting_outcome_label"), value=_stage.outcome, key=f"_stage_out_{_i}")
                _stage.deliverables = [
                    line.strip() for line in st.text_area(
                        i18n.t("drafting_deliverables_label"), value="\n".join(_stage.deliverables),
                        key=f"_stage_deliv_{_i}", height=90,
                    ).split("\n") if line.strip()
                ]
                st.caption(i18n.t("drafting_cell_tbc_caption"))
                if st.button(i18n.t("drafting_remove_stage_button"), key=f"_stage_rm_{_i}"):
                    _remove_index = _i

        if _remove_index is not None:
            st.session_state.methodology_stages.pop(_remove_index)
            st.rerun()

        acol1, acol2 = st.columns([1, 3])
        with acol1:
            if st.button(i18n.t("drafting_add_stage_button"), key="add_stage_btn"):
                st.session_state.methodology_stages.append(
                    methodology_stages.MethodologyStage(
                        name="", key_tasks=[methodology_stages.TBC],
                        engagement_activities=[methodology_stages.TBC],
                        outcome=methodology_stages.TBC,
                        deliverables=[methodology_stages.TBC],
                    )
                )
                st.rerun()

        st.checkbox(
            i18n.t("drafting_wvr_checkbox_label"),
            key="methodology_wvr_confirmed",
            help=i18n.t("drafting_wvr_checkbox_help"),
        )

        st.markdown("")
        _methodology_style_control()

    st.markdown("---")
    st.caption(i18n.t("drafting_diff_pitch_caption"))
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.text_area(
            i18n.t("drafting_differentiator_label"), key="project_differentiator", height=140,
            placeholder=i18n.t("drafting_differentiator_placeholder"),
        )
    with dcol2:
        st.text_area(
            i18n.t("drafting_sales_pitch_label"), key="project_sales_pitch", height=140,
            placeholder=i18n.t("drafting_sales_pitch_placeholder"),
        )
    _pitch_ready = bool(st.session_state.ai_config.get("api_key")) and (
        st.session_state.project_differentiator.strip() or st.session_state.project_sales_pitch.strip()
    ) and _current_project_already_paid()
    if st.button(i18n.t("drafting_review_ai_button"), disabled=not _pitch_ready, key="review_pitch_btn", type="primary"):
        with st.spinner(i18n.t("drafting_spinner_pitch_review")):
            try:
                _record_ai_click()
                st.session_state.pitch_review = pitch_review_module.review_pitch(
                    st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                    st.session_state.analysis, _project_info(), st.session_state.ai_config,
                    output_language=st.session_state.get("output_language", "en"),
                )
                st.success(i18n.t("drafting_review_complete_success"))
            except Exception as exc:
                _show_error(i18n.t("drafting_pitch_review_failed_error"), exc)
    if not st.session_state.ai_config.get("api_key"):
        st.caption(_AI_HINT_SENTENCE)
    elif not _current_project_already_paid():
        st.caption(_ai_block_reason())

    st.markdown(i18n.t("drafting_sharpen_heading"))
    st.caption(i18n.t("drafting_sharpen_caption"))
    if st.button(i18n.t("drafting_get_questions_button"), disabled=not _pitch_ready, key="get_pitch_questions_btn"):
        with st.spinner(i18n.t("drafting_spinner_questions")):
            try:
                _record_ai_click()
                for i in range(4):
                    st.session_state.pop(f"diff_qa_{i}", None)
                    st.session_state.pop(f"pitch_qa_{i}", None)
                st.session_state.pitch_questions = pitch_review_module.generate_pitch_questions(
                    st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                    st.session_state.analysis, _project_info(), st.session_state.ai_config,
                    output_language=st.session_state.get("output_language", "en"),
                )
            except Exception as exc:
                _show_error(i18n.t("drafting_generate_questions_failed_error"), exc)

    if st.session_state.pitch_questions:
        pq = st.session_state.pitch_questions
        if not pq.differentiator_questions and not pq.sales_pitch_questions:
            st.caption(i18n.t("drafting_both_specific_caption"))
        else:
            qcol1, qcol2 = st.columns(2)
            with qcol1:
                if pq.differentiator_questions:
                    st.markdown(f"*{i18n.t('drafting_differentiator_label')}*")
                    for i, q in enumerate(pq.differentiator_questions):
                        st.text_input(q, key=f"diff_qa_{i}")
            with qcol2:
                if pq.sales_pitch_questions:
                    st.markdown(f"*{i18n.t('drafting_sales_pitch_label')}*")
                    for i, q in enumerate(pq.sales_pitch_questions):
                        st.text_input(q, key=f"pitch_qa_{i}")

            if st.button(i18n.t("drafting_sharpen_with_answers_button"), key="sharpen_with_answers_btn", type="primary",
                         disabled=not _current_project_already_paid()):
                with st.spinner(i18n.t("drafting_spinner_sharpening")):
                    try:
                        _record_ai_click()
                        _diff_qa = [
                            (q, st.session_state.get(f"diff_qa_{i}", ""))
                            for i, q in enumerate(pq.differentiator_questions)
                        ]
                        _pitch_qa = [
                            (q, st.session_state.get(f"pitch_qa_{i}", ""))
                            for i, q in enumerate(pq.sales_pitch_questions)
                        ]
                        st.session_state.pitch_review = pitch_review_module.review_pitch(
                            st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                            st.session_state.analysis, _project_info(), st.session_state.ai_config,
                            differentiator_qa=_diff_qa, sales_pitch_qa=_pitch_qa,
                            output_language=st.session_state.get("output_language", "en"),
                        )
                        st.success(i18n.t("drafting_sharpened_success"))
                    except Exception as exc:
                        _show_error(i18n.t("drafting_sharpening_failed_error"), exc)

    if st.session_state.pitch_review:
        pr = st.session_state.pitch_review

        def _apply_differentiator_rewrite():
            # Widget-bound session_state keys can only be reassigned from a
            # callback (which runs BEFORE the next script run instantiates the
            # text_area again) -- reassigning inline after the widget has
            # already rendered in the current run raises a StreamlitAPIException.
            st.session_state.project_differentiator = st.session_state.pitch_review.differentiator_refined

        def _apply_sales_pitch_rewrite():
            st.session_state.project_sales_pitch = st.session_state.pitch_review.sales_pitch_refined

        rcol1, rcol2 = st.columns(2)
        with rcol1:
            if pr.differentiator_comment or pr.differentiator_refined:
                st.markdown(i18n.t("drafting_diff_ai_comment_heading"))
                st.write(pr.differentiator_comment)
                st.markdown(i18n.t("drafting_suggested_rewrite_heading"))
                st.write(pr.differentiator_refined)
                if pr.differentiator_refined:
                    st.button(
                        i18n.t("drafting_use_rewrite_button"), key="use_diff_rewrite", on_click=_apply_differentiator_rewrite,
                     type="primary")
        with rcol2:
            if pr.sales_pitch_comment or pr.sales_pitch_refined:
                st.markdown(i18n.t("drafting_pitch_ai_comment_heading"))
                st.write(pr.sales_pitch_comment)
                st.markdown(i18n.t("drafting_suggested_rewrite_heading"))
                st.write(pr.sales_pitch_refined)
                if pr.sales_pitch_refined:
                    st.button(
                        i18n.t("drafting_use_rewrite_button"), key="use_pitch_rewrite", on_click=_apply_sales_pitch_rewrite,
                     type="primary")

    st.markdown("---")
    st.caption(i18n.t("drafting_exec_summary_caption"))
    if not st.session_state.drafts:
        st.caption(i18n.t("drafting_exec_summary_draft_first_caption"))
    if st.button(i18n.t("drafting_generate_exec_summary_button"), disabled=not ready, type="primary"):
        with st.spinner(i18n.t("drafting_spinner_exec_summary")):
            try:
                _record_ai_click()
                _excluded_names = resourcing.excluded_personnel_names(st.session_state.resource_plan)
                _team_context = draft_generator.format_team_context(st.session_state.resource_plan)
                st.session_state.executive_summary = executive_summary_module.draft_executive_summary(
                    st.session_state.analysis, _project_info(), _team_context, st.session_state.ai_config,
                    # The summary introduces the document, so it is told what
                    # the document actually contains -- without this it could
                    # promise an evaluator a subject the methodology never
                    # mentions.
                    drafted_section_titles=sorted((st.session_state.drafts or {}).keys()),
                    win_themes="\n\n".join(part for part in (
                        (st.session_state.project_differentiator or "").strip(),
                        (st.session_state.project_sales_pitch or "").strip(),
                    ) if part),
                    program_weeks=_program_week_count() or None,
                    output_language=st.session_state.get("output_language", "en"),
                )
                _es = st.session_state.executive_summary
                if not _es or not ((_es.intro or "").strip() or _es.blocks):
                    st.warning(i18n.t("drafting_exec_summary_empty_warning"))
                else:
                    st.success(i18n.t("drafting_exec_summary_drafted_success"))
            except Exception as exc:
                _show_error(i18n.t("drafting_exec_summary_failed_error"), exc)

    if st.session_state.executive_summary:
        with st.expander(i18n.t("drafting_exec_summary_expander"), expanded=False):
            es = st.session_state.executive_summary
            if es.intro:
                st.write(es.intro)
            for block in es.blocks:
                st.markdown(f"**{block.title}**")
                st.write(block.body)

    if not _is_letter():
        st.markdown("---")
        st.caption(i18n.t("drafting_team_intro_caption"))
        _team_ready = ready and bool(st.session_state.resource_plan)
        if st.button(i18n.t("drafting_generate_team_intro_button"), disabled=not _team_ready, type="primary"):
            with st.spinner(i18n.t("drafting_spinner_team_intro")):
                try:
                    _record_ai_click()
                    _included_people = [
                        e for e in resourcing.personnel_profiles_deduped(st.session_state.resource_plan)
                        if (e.get("name") or "").strip()
                        and getattr(e["assignment"], "include_in_proposal", True)
                    ]
                    st.session_state.team_intro = team_intro_module.draft_team_intro(
                        _included_people, st.session_state.analysis, _project_info(), st.session_state.ai_config,
                        output_language=st.session_state.get("output_language", "en"),
                    )
                    _ti = st.session_state.team_intro
                    if not _ti or not ((_ti.heading or "").strip() or _ti.paragraphs):
                        st.warning(i18n.t("drafting_team_intro_empty_warning"))
                    else:
                        st.success(i18n.t("drafting_team_intro_drafted_success"))
                except Exception as exc:
                    _show_error(i18n.t("drafting_team_intro_failed_error"), exc)
        if not st.session_state.resource_plan:
            st.caption(i18n.t("drafting_assign_person_caption"))

        if st.session_state.team_intro:
            with st.expander(i18n.t("drafting_team_intro_expander"), expanded=False):
                ti = st.session_state.team_intro
                if ti.heading:
                    st.markdown(f"**{ti.heading}**")
                for para in ti.paragraphs:
                    st.write(para)
                if ti.pullquote:
                    st.markdown(f"*{ti.pullquote}*")

        st.markdown("---")
        st.caption(i18n.t("drafting_experience_intro_caption"))
        _experience_ready = ready and bool(st.session_state.reference_projects)
        if st.button(i18n.t("drafting_generate_experience_intro_button"), disabled=not _experience_ready,
                     help=None if _experience_ready else i18n.t("drafting_experience_intro_help"), type="primary"):
            with st.spinner(i18n.t("drafting_spinner_experience_intro")):
                try:
                    _record_ai_click()
                    st.session_state.experience_intro = experience_intro_module.draft_experience_intro(
                        st.session_state.reference_projects, st.session_state.analysis,
                        _project_info(), st.session_state.ai_config,
                        output_language=st.session_state.get("output_language", "en"),
                    )
                    _ei = st.session_state.experience_intro
                    if not _ei or not (getattr(_ei, "paragraph", "") or "").strip():
                        st.warning(i18n.t("drafting_experience_intro_empty_warning"))
                    else:
                        st.success(i18n.t("drafting_experience_intro_drafted_success"))
                except Exception as exc:
                    _show_error(i18n.t("drafting_experience_intro_failed_error"), exc)
        if not st.session_state.reference_projects:
            # Uploading reference material (Upload Docs) only extracts its text --
            # it still needs "Draft reference projects from uploaded material"
            # clicked there before any entries exist for this button to use. A
            # bare "add a reference project" caption reads as if uploading alone
            # should have been enough, which is exactly the confusing part.
            st.caption(i18n.t("drafting_no_reference_projects_caption"))

        if st.session_state.experience_intro:
            with st.expander(i18n.t("drafting_experience_intro_expander"), expanded=False):
                st.write(st.session_state.experience_intro.paragraph)

    if st.session_state.drafts:
        for section in _draftable_sections(st.session_state.sections or []):
            draft = st.session_state.drafts.get(section.title)
            note = st.session_state.guidance_notes.get(section.title) if st.session_state.guidance_notes else None
            # TODO A2 i18n: expander title "{number}. {title}" carries no
            # translatable words of its own (section.title is generated data),
            # left as an f-string.
            with st.expander(f"{section.section_number}. {section.title}", expanded=False):
                if note and not _is_letter():
                    st.markdown(f":red[**[{note.marker}]**]")
                    st.markdown(f":red[{i18n.t('drafting_page_limit_prefix', text=note.page_limit_text)}]")
                    st.markdown(f":red[{i18n.t('drafting_evaluation_weighting_prefix', text=note.weighting_text)}]")
                    st.markdown(f":red[{i18n.t('drafting_formatting_prefix', text=note.format_requirements_text)}]")
                if draft:
                    st.markdown(f"**{draft.draft_heading}**")
                    st.write(draft.draft_text)
                    if draft.required_user_inputs:
                        st.markdown(i18n.t("drafting_still_needs_heading"))
                        for r in draft.required_user_inputs:
                            st.markdown(f"- {r}")

    if _is_letter():
        st.divider()
        st.markdown(i18n.t("drafting_terms_heading"))
        st.caption(i18n.t("drafting_terms_caption"))
        st.text_area(
            i18n.t("drafting_terms_label"), key="terms_of_engagement_text", height=150,
            placeholder=i18n.t("drafting_terms_placeholder"),
            label_visibility="collapsed",
        )



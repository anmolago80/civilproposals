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
    st.subheader("Draft Responses")
    if _is_letter():
        st.caption(
            "The Small Scope pack has two sections that are genuinely free text -- Introduction "
            "and Methodology and Deliverables, both drafted below. Scope of Work comes straight "
            "from the brief, Project Team/Fees/Program have their own dedicated steps "
            "(Team & Resourcing / Fee Estimate), and Terms of Engagement further down is "
            "always your own wording, never AI-drafted."
        )
    else:
        st.caption("First-pass draft content per section, with red guidance notes and a list of what still needs real user input.")

    ready = (
        st.session_state.sections is not None
        and bool(st.session_state.ai_config.get("api_key"))
        and _current_project_already_paid()
    )
    if not ready:
        if st.session_state.sections is not None and not _current_project_already_paid():
            st.info(_PROJECT_NOT_PAID_HINT)
        else:
            st.info(f"Generate the Proposal Structure and {_AI_HINT_CLAUSE}.")

    if _structure_format_stale():
        st.warning(
            "The Proposal format (Project Setup) was changed after the current sections were generated. "
            "Go to Structure and click **Generate Proposal Structure** again before drafting, or "
            "this will silently draft nothing for the sections that only exist in this format."
        )

    if st.button("Generate First-Pass Drafts", type="primary", disabled=not ready):
        targets = _draftable_sections(st.session_state.sections)
        if not targets:
            st.error(
                "Nothing to draft -- the current sections don't match any of this format's "
                "AI-drafted section titles. This usually means the Proposal format (Project Setup) was "
                "changed after Proposal Structure was generated. Go to Structure and click "
                "**Generate Proposal Structure** again, then retry this."
            )
            st.stop()
        progress = st.progress(0.0, text="Drafting...")

        def _progress_cb(done, total, title):
            # generate_all_drafts() now runs sections concurrently and calls
            # this AFTER each one finishes (done is already a 1-indexed
            # completed-count, not "about to start section done+1" like the
            # old sequential version) -- sections may complete out of their
            # original order, so `title` here is whichever one just finished,
            # not necessarily done'th in the list.
            progress.progress(done / max(total, 1), text=f"Drafted '{title}' ({done}/{total})...")

        try:
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
            }
            new_drafts = _run_job_or_inline(
                "draft_generation", draft_generator.generate_all_drafts,
                args=(targets, st.session_state.analysis, _material_for_draft, st.session_state.ai_config),
                kwargs=_draft_kwargs,
                progress=progress,
                queued_text="Queued for drafting...", running_text="Drafting...",
                inline_extra_kwargs={"progress_callback": _progress_cb},
                queue_func=job_queue.run_draft_generation_job,
                queue_args=(targets, st.session_state.analysis, _material_for_draft, _redacted_ai_config),
            )
            st.session_state.drafts = {**(st.session_state.drafts or {}), **new_drafts}
            progress.progress(1.0, text="Done.")
            # "Complete" has to mean complete. An empty or one-sentence draft
            # used to render as a blank expander under a green success
            # message, and nobody opens twelve expanders to check.
            _thin = _thin_drafts(new_drafts)
            if _thin:
                st.warning(
                    "**Drafting finished, but some sections came back empty or very short:** "
                    + ", ".join(_thin)
                    + ". Re-run drafting for those, or write them yourself -- they will export "
                    "as red placeholders until you do."
                )
            if len(_thin) < len(new_drafts):
                st.success(f"Draft generation complete for {len(new_drafts) - len(_thin)} section(s).")
        except Exception as exc:
            _show_error("Draft generation failed", exc)

    # -----------------------------------------------------------------
    # Risk register
    # -----------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### Risk register")
    st.caption(
        "A first-pass risk / impact / mitigation table, structured from the risks the brief "
        "itself raises and the gaps the analysis found. **A mitigation is a commitment your "
        "firm will be held to**, so the AI only ever states one the brief already describes -- "
        "everything else comes back as **TBC** for you to decide. Edit anything below."
    )
    _risk_ready = (
        st.session_state.analysis is not None
        and bool(st.session_state.ai_config.get("api_key"))
        and _current_project_already_paid()
    )
    rcol1, rcol2 = st.columns([1, 2])
    with rcol1:
        _draft_risk_clicked = st.button(
            "Draft risk register", type="primary", disabled=not _risk_ready, key="draft_risk_btn",
        )
    with rcol2:
        if not st.session_state.ai_config.get("api_key"):
            st.caption(_AI_HINT_SENTENCE)
        elif not _current_project_already_paid():
            st.caption(_PROJECT_NOT_PAID_HINT)
        elif st.session_state.analysis is None:
            st.caption("Run Tender Analysis first -- the register is built from the brief's own risks.")

    if _draft_risk_clicked:
        if st.session_state.risk_register and not st.session_state.get("_confirm_rerisk"):
            st.session_state._confirm_rerisk = True
        else:
            st.session_state._confirm_rerisk = False
            with st.spinner("Structuring the risk register..."):
                try:
                    st.session_state.risk_register = risk_register.draft_risk_register(
                        st.session_state.analysis,
                        st.session_state.gap_items or [],
                        st.session_state.ai_config,
                    )
                    if not (st.session_state.risk_register.entries if st.session_state.risk_register else []):
                        st.warning(
                            "No risks came back -- the brief may not raise any. Nothing has been "
                            "changed; add rows by hand below if you want a register anyway."
                        )
                    else:
                        st.success(f"Structured {len(st.session_state.risk_register.entries)} risk(s) -- review below.")
                except Exception as exc:
                    _show_error("Drafting the risk register failed", exc)

    if st.session_state.get("_confirm_rerisk"):
        st.warning(
            "You already have a risk register, and some of it may be your own edits. Drafting "
            "again replaces every row. Click **Draft risk register** once more to go ahead."
        )
        if st.button("Cancel", key="cancel_rerisk"):
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
                "Risk": st.column_config.TextColumn("Risk", width="medium"),
                "Impact": st.column_config.TextColumn("Impact", width="medium"),
                "Mitigation": st.column_config.TextColumn("Mitigation", width="medium"),
                "Source": st.column_config.TextColumn("Source", disabled=True, width="small"),
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
        st.caption(
            "Rows left as **TBC** export in red, so nobody submits an unfilled mitigation by "
            "accident."
        )

    # -----------------------------------------------------------------
    # Design stages -- the grid that fills the methodology table
    # -----------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### Design stages")
    st.caption(
        "The delivery stages behind the exported methodology table. The AI assigns your "
        "brief's own scope items and deliverables to stages and rephrases them -- it never "
        "adds a task, activity, deliverable or date that isn't in the brief, and writes "
        "**TBC** wherever the brief doesn't support a cell. Edit anything below; what's here "
        "when you export is exactly what goes into the table."
    )

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
            "Draft methodology stages", type="primary", disabled=not _stages_ready,
            key="draft_stages_btn",
        )
    with scol2:
        if not st.session_state.ai_config.get("api_key"):
            st.caption(_AI_HINT_SENTENCE)
        elif not _current_project_already_paid():
            st.caption(_PROJECT_NOT_PAID_HINT)
        elif st.session_state.analysis is None:
            st.caption("Run Tender Analysis first -- the stages are built from the brief's own scope and deliverables.")

    # Regenerating over edited content needs an explicit second click. AI
    # output must never silently overwrite something a person has changed.
    if _draft_stages_clicked:
        if _existing_stages and not st.session_state.get("_confirm_restage"):
            st.session_state._confirm_restage = True
        else:
            st.session_state._confirm_restage = False
            with st.spinner("Drafting methodology stages..."):
                try:
                    _methodology_draft = (st.session_state.drafts or {}).get("Methodology and Deliverables")
                    st.session_state.methodology_stages = methodology_stages.draft_methodology_stages(
                        st.session_state.analysis,
                        methodology_draft_text=_methodology_draft.draft_text if _methodology_draft else "",
                        program_schedule=st.session_state.program_schedule,
                        program_week_labels=st.session_state.program_week_labels,
                        project_info=_project_info(),
                        config=st.session_state.ai_config,
                    )
                    if not st.session_state.methodology_stages:
                        st.warning(
                            "The AI returned no stages -- nothing has been changed. You can fill "
                            "the grid in by hand with **Start a blank grid** below."
                        )
                    else:
                        st.success(f"Drafted {len(st.session_state.methodology_stages)} stage(s) -- review and edit below.")
                except Exception as exc:
                    _show_error("Drafting the methodology stages failed", exc)

    if st.session_state.get("_confirm_restage"):
        st.warning(
            "You already have a stage grid below, and some of it may be your own edits. "
            "Drafting again replaces every stage. Click **Draft methodology stages** once "
            "more to go ahead, or edit the grid directly instead."
        )
        if st.button("Cancel", key="cancel_restage"):
            st.session_state._confirm_restage = False
            st.rerun()

    if not st.session_state.methodology_stages:
        if st.button("Start a blank grid", key="blank_stages_btn"):
            st.session_state.methodology_stages = methodology_stages.blank_stages()
            st.rerun()
        st.caption(
            "No stages yet. Without them the exported methodology table falls back to its "
            "generic four-stage layout with placeholder columns."
        )
    else:
        _week_labels = st.session_state.program_week_labels or []
        _week_options = [0] + list(range(1, len(_week_labels) + 1))

        def _week_label(index: int) -> str:
            if not index:
                return "-"
            return _week_labels[index - 1] if index <= len(_week_labels) else f"Wk {index}"

        _remove_index = None
        for _i, _stage in enumerate(st.session_state.methodology_stages):
            with st.expander(f"Stage {_i + 1}: {_stage.name or 'Untitled'}", expanded=(_i == 0)):
                _stage.name = st.text_input("Stage name", value=_stage.name, key=f"_stage_name_{_i}")
                wcol1, wcol2, wcol3 = st.columns([1, 1, 2])
                with wcol1:
                    _ws = st.selectbox(
                        "First week", _week_options, key=f"_stage_ws_{_i}",
                        index=_week_options.index(_stage.week_start) if _stage.week_start in _week_options else 0,
                        format_func=_week_label,
                    )
                with wcol2:
                    _we = st.selectbox(
                        "Last week", _week_options, key=f"_stage_we_{_i}",
                        index=_week_options.index(_stage.week_end) if _stage.week_end in _week_options else 0,
                        format_func=_week_label,
                    )
                with wcol3:
                    st.write("")
                    st.caption(
                        "Week numbers come from the delivery program on the Fees & Program step. "
                        "Set an anticipated start date there and these become real dates in the "
                        "exported table."
                    )
                _stage.week_start = _ws or None
                _stage.week_end = _we or None

                _stage.key_tasks = [
                    line.strip() for line in st.text_area(
                        "Key tasks (one per line)", value="\n".join(_stage.key_tasks),
                        key=f"_stage_tasks_{_i}", height=110,
                    ).split("\n") if line.strip()
                ]
                _stage.engagement_activities = [
                    line.strip() for line in st.text_area(
                        "Engagement activities (one per line)",
                        value="\n".join(_stage.engagement_activities),
                        key=f"_stage_eng_{_i}", height=80,
                    ).split("\n") if line.strip()
                ]
                _stage.outcome = st.text_input("Outcome", value=_stage.outcome, key=f"_stage_out_{_i}")
                _stage.deliverables = [
                    line.strip() for line in st.text_area(
                        "Deliverables (one per line)", value="\n".join(_stage.deliverables),
                        key=f"_stage_deliv_{_i}", height=90,
                    ).split("\n") if line.strip()
                ]
                st.caption(
                    "Leave a cell as **TBC** where the brief genuinely doesn't say -- it exports "
                    "in red so nobody submits it by accident."
                )
                if st.button("Remove this stage", key=f"_stage_rm_{_i}"):
                    _remove_index = _i

        if _remove_index is not None:
            st.session_state.methodology_stages.pop(_remove_index)
            st.rerun()

        acol1, acol2 = st.columns([1, 3])
        with acol1:
            if st.button("Add a stage", key="add_stage_btn"):
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
            "Confirm this firm issues Work Verification Records (WVRs) with design deliverables",
            key="methodology_wvr_confirmed",
            help="The methodology table used to state this as fact in every export without "
                 "anyone having been asked. Leave it unticked and it exports as a red "
                 "[CONFIRM WVR / QA STATEMENT] instead.",
        )

        st.markdown("")
        _methodology_style_control()

    st.markdown("---")
    st.caption(
        "**Differentiator & sales pitch** -- write these in your own words: what sets this "
        "firm apart for this bid, and the pitch for why it should win. AI review is optional "
        "-- it comments on the text as written and offers a tightened, re-angled rewrite tied "
        "to this brief's real scope, but only ever works with what you've written here, never "
        "invents new claims."
    )
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.text_area(
            "Differentiator", key="project_differentiator", height=140,
            placeholder="What sets this firm apart for this bid?",
        )
    with dcol2:
        st.text_area(
            "Sales pitch", key="project_sales_pitch", height=140,
            placeholder="The pitch for why this firm should win.",
        )
    _pitch_ready = bool(st.session_state.ai_config.get("api_key")) and (
        st.session_state.project_differentiator.strip() or st.session_state.project_sales_pitch.strip()
    ) and _current_project_already_paid()
    if st.button("Review with AI", disabled=not _pitch_ready, key="review_pitch_btn", type="primary"):
        with st.spinner("Reviewing differentiator & sales pitch..."):
            try:
                st.session_state.pitch_review = pitch_review_module.review_pitch(
                    st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                    st.session_state.analysis, _project_info(), st.session_state.ai_config,
                )
                st.success("Review complete.")
            except Exception as exc:
                _show_error("Pitch review failed", exc)
    if not st.session_state.ai_config.get("api_key"):
        st.caption(_AI_HINT_SENTENCE)
    elif not _current_project_already_paid():
        st.caption(_PROJECT_NOT_PAID_HINT)

    st.markdown("**Sharpen further with follow-up questions**")
    st.caption(
        "Generates a few targeted questions about whatever's still vague or unsupported in what "
        "you've written above (up to 4 per field), then folds your answers straight into a sharper "
        "rewrite -- same rule as everywhere else on this page, nothing added beyond what you type. "
        "Only runs when you click the button, never automatically."
    )
    if st.button("Get sharpening questions", disabled=not _pitch_ready, key="get_pitch_questions_btn"):
        with st.spinner("Coming up with follow-up questions..."):
            try:
                for i in range(4):
                    st.session_state.pop(f"diff_qa_{i}", None)
                    st.session_state.pop(f"pitch_qa_{i}", None)
                st.session_state.pitch_questions = pitch_review_module.generate_pitch_questions(
                    st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                    st.session_state.analysis, _project_info(), st.session_state.ai_config,
                )
            except Exception as exc:
                _show_error("Couldn't generate questions", exc)

    if st.session_state.pitch_questions:
        pq = st.session_state.pitch_questions
        if not pq.differentiator_questions and not pq.sales_pitch_questions:
            st.caption("Both already read specific and concrete -- no follow-up questions needed.")
        else:
            qcol1, qcol2 = st.columns(2)
            with qcol1:
                if pq.differentiator_questions:
                    st.markdown("*Differentiator*")
                    for i, q in enumerate(pq.differentiator_questions):
                        st.text_input(q, key=f"diff_qa_{i}")
            with qcol2:
                if pq.sales_pitch_questions:
                    st.markdown("*Sales pitch*")
                    for i, q in enumerate(pq.sales_pitch_questions):
                        st.text_input(q, key=f"pitch_qa_{i}")

            if st.button("Sharpen with my answers", key="sharpen_with_answers_btn", type="primary",
                         disabled=not _current_project_already_paid()):
                with st.spinner("Sharpening with your answers..."):
                    try:
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
                        )
                        st.success("Sharpened using your answers -- see the rewrite below.")
                    except Exception as exc:
                        _show_error("Sharpening failed", exc)

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
                st.markdown("**Differentiator -- AI comment**")
                st.write(pr.differentiator_comment)
                st.markdown("**Suggested rewrite**")
                st.write(pr.differentiator_refined)
                if pr.differentiator_refined:
                    st.button(
                        "Use this rewrite", key="use_diff_rewrite", on_click=_apply_differentiator_rewrite,
                     type="primary")
        with rcol2:
            if pr.sales_pitch_comment or pr.sales_pitch_refined:
                st.markdown("**Sales pitch -- AI comment**")
                st.write(pr.sales_pitch_comment)
                st.markdown("**Suggested rewrite**")
                st.write(pr.sales_pitch_refined)
                if pr.sales_pitch_refined:
                    st.button(
                        "Use this rewrite", key="use_pitch_rewrite", on_click=_apply_sales_pitch_rewrite,
                     type="primary")

    st.markdown("---")
    st.caption(
        "**Executive summary** -- an unweighted page that goes straight after the cover, "
        "before the scored sections (Large Scope pack) or straight after the cover (Small "
        "Scope pack). No score of its own, but it's the evaluators' first impression, so it's "
        "drafted warm and sales-forward rather than dry -- catchy titles, short readable "
        "blocks, grounded in the real brief and the real (included) nominated team."
    )
    if not st.session_state.drafts:
        st.caption(
            "Draft the sections first -- the summary is written from what the proposal "
            "actually says, so that it can't promise a subject the document doesn't cover."
        )
    if st.button("Generate Executive Summary (AI)", disabled=not ready, type="primary"):
        with st.spinner("Drafting executive summary..."):
            try:
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
                )
                _es = st.session_state.executive_summary
                if not _es or not ((_es.intro or "").strip() or _es.blocks):
                    st.warning(
                        "The executive summary came back empty -- nothing has been saved over "
                        "what you had. Try again, or write it yourself; the pack's first page "
                        "exports as a red placeholder until it exists."
                    )
                else:
                    st.success("Executive summary drafted.")
            except Exception as exc:
                _show_error("Executive summary generation failed", exc)

    if st.session_state.executive_summary:
        with st.expander("Executive summary", expanded=False):
            es = st.session_state.executive_summary
            if es.intro:
                st.write(es.intro)
            for block in es.blocks:
                st.markdown(f"**{block.title}**")
                st.write(block.body)

    if not _is_letter():
        st.markdown("---")
        st.caption(
            "**Team introduction** -- a short sales-forward pitch at the very start of Key "
            "Personnel, before the org chart and pen pics: a catchy headline and a couple of "
            "paragraphs connecting the nominated (included) team's real past projects to this "
            "brief's real challenges, closing with a pull-quote line. Grounded entirely in "
            "each person's own value-to-project write-up and relevant projects, entered on the "
            "Team & Resourcing tab -- never invented."
        )
        _team_ready = ready and bool(st.session_state.resource_plan)
        if st.button("Generate Team Introduction (AI)", disabled=not _team_ready, type="primary"):
            with st.spinner("Drafting team introduction..."):
                try:
                    _included_people = [
                        e for e in resourcing.personnel_profiles_deduped(st.session_state.resource_plan)
                        if (e.get("name") or "").strip()
                        and getattr(e["assignment"], "include_in_proposal", True)
                    ]
                    st.session_state.team_intro = team_intro_module.draft_team_intro(
                        _included_people, st.session_state.analysis, _project_info(), st.session_state.ai_config,
                    )
                    _ti = st.session_state.team_intro
                    if not _ti or not ((_ti.heading or "").strip() or _ti.paragraphs):
                        st.warning(
                            "The team introduction came back empty. This usually means the "
                            "nominated people have no write-ups yet -- fill in their "
                            "\"on this project they will...\" text on Team & Resourcing and "
                            "try again."
                        )
                    else:
                        st.success("Team introduction drafted.")
                except Exception as exc:
                    _show_error("Team introduction generation failed", exc)
        if not st.session_state.resource_plan:
            st.caption("Assign at least one person on the Team & Resourcing tab first.")

        if st.session_state.team_intro:
            with st.expander("Team introduction", expanded=False):
                ti = st.session_state.team_intro
                if ti.heading:
                    st.markdown(f"**{ti.heading}**")
                for para in ti.paragraphs:
                    st.write(para)
                if ti.pullquote:
                    st.markdown(f"*{ti.pullquote}*")

        st.markdown("---")
        st.caption(
            "**Project experience introduction** -- a short sales-forward paragraph at the "
            "start of Relevant Project Experience, before the individual project cards: "
            "names the strongest 2-4 comparable reference projects and states plainly why "
            "they prove this firm can deliver the brief, replacing the generic 'selected "
            "past projects' note. Grounded entirely in the real reference projects entered "
            "and drafted in Upload Docs -- never invented."
        )
        _experience_ready = ready and bool(st.session_state.reference_projects)
        if st.button("Generate Project Experience Introduction (AI)", disabled=not _experience_ready,
                     help=None if _experience_ready else "Needs at least one drafted reference project -- see below.", type="primary"):
            with st.spinner("Drafting project experience introduction..."):
                try:
                    st.session_state.experience_intro = experience_intro_module.draft_experience_intro(
                        st.session_state.reference_projects, st.session_state.analysis,
                        _project_info(), st.session_state.ai_config,
                    )
                    _ei = st.session_state.experience_intro
                    if not _ei or not (getattr(_ei, "paragraph", "") or "").strip():
                        st.warning(
                            "The project experience introduction came back empty -- the "
                            "reference projects may have no description or relevance text yet. "
                            "The section falls back to its default note until this exists."
                        )
                    else:
                        st.success("Project experience introduction drafted.")
                except Exception as exc:
                    _show_error("Project experience introduction generation failed", exc)
        if not st.session_state.reference_projects:
            # Uploading reference material (Upload Docs) only extracts its text --
            # it still needs "Draft reference projects from uploaded material"
            # clicked there before any entries exist for this button to use. A
            # bare "add a reference project" caption reads as if uploading alone
            # should have been enough, which is exactly the confusing part.
            st.caption(
                "No drafted reference projects yet. Go to Upload Docs, upload 'Project references' "
                "material if you haven't, then click **Draft reference projects from uploaded "
                "material** there -- or add one manually on that same step."
            )

        if st.session_state.experience_intro:
            with st.expander("Project experience introduction", expanded=False):
                st.write(st.session_state.experience_intro.paragraph)

    if st.session_state.drafts:
        for section in _draftable_sections(st.session_state.sections or []):
            draft = st.session_state.drafts.get(section.title)
            note = st.session_state.guidance_notes.get(section.title) if st.session_state.guidance_notes else None
            with st.expander(f"{section.section_number}. {section.title}", expanded=False):
                if note and not _is_letter():
                    st.markdown(f":red[**[{note.marker}]**]")
                    st.markdown(f":red[Page limit: {note.page_limit_text}]")
                    st.markdown(f":red[Evaluation weighting: {note.weighting_text}]")
                    st.markdown(f":red[Formatting: {note.format_requirements_text}]")
                if draft:
                    st.markdown(f"**{draft.draft_heading}**")
                    st.write(draft.draft_text)
                    if draft.required_user_inputs:
                        st.markdown("**Still needs from you:**")
                        for r in draft.required_user_inputs:
                            st.markdown(f"- {r}")

    if _is_letter():
        st.divider()
        st.markdown("#### Terms of Engagement")
        st.caption(
            "Always your own text -- this tool never invents or guesses which contract/commercial "
            "conditions apply, since getting that wrong is a real legal risk."
        )
        st.text_area(
            "Terms of Engagement", key="terms_of_engagement_text", height=150,
            placeholder="e.g. This offer is made under our current Master Services Agreement with Townsville City Council, reference ...",
            label_visibility="collapsed",
        )



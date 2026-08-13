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
            new_drafts = _run_job_or_inline(
                "draft_generation", draft_generator.generate_all_drafts,
                args=(targets, st.session_state.analysis, _material_for_draft, st.session_state.ai_config),
                kwargs={"team_context": draft_generator.format_team_context(st.session_state.resource_plan)},
                progress=progress,
                queued_text="Queued for drafting...", running_text="Drafting...",
                inline_extra_kwargs={"progress_callback": _progress_cb},
                queue_func=job_queue.run_draft_generation_job,
                queue_args=(targets, st.session_state.analysis, _material_for_draft, _redacted_ai_config),
            )
            st.session_state.drafts = {**(st.session_state.drafts or {}), **new_drafts}
            progress.progress(1.0, text="Done.")
            st.success("Draft generation complete.")
        except Exception as exc:
            _show_error("Draft generation failed", exc)

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
    if st.button("Generate Executive Summary (AI)", disabled=not ready, type="primary"):
        with st.spinner("Drafting executive summary..."):
            try:
                _excluded_names = resourcing.excluded_personnel_names(st.session_state.resource_plan)
                _team_context = draft_generator.format_team_context(st.session_state.resource_plan)
                st.session_state.executive_summary = executive_summary_module.draft_executive_summary(
                    st.session_state.analysis, _project_info(), _team_context, st.session_state.ai_config,
                )
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



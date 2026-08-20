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
    st.subheader("Export Pack")

    # Readiness checklist. Most of the red in an exported pack is not missing
    # information -- it is a step that hasn't been run. Listing those here,
    # each with where to go, turns a silently red document into a short list
    # of actions before anyone opens the file and starts wondering.
    _readiness = _export_readiness()
    if _readiness:
        with st.expander(f"⚠️ {len(_readiness)} thing(s) still outstanding before this pack is ready",
                         expanded=True):
            for _item in _readiness:
                st.markdown(
                    f"- **{_item['label']}** -- go to *{_item['where']}*"
                    + (f". {_item['detail']}" if _item["detail"] else "")
                )
            st.caption(
                "You can export anyway -- everything outstanding shows as a red placeholder in "
                "the document, so nothing is silently missing."
            )
    else:
        st.success("Everything this pack needs has been filled in.")

    if _is_letter():
        st.caption("Generates the first-pass Small Scope Proposal Response Pack. Review the checklist page inside before this goes anywhere near a real submission.")
        ready = st.session_state.sections is not None
        if not ready:
            st.info("Generate the Proposal Structure first.")

        if _structure_format_stale():
            st.warning(
                "The Proposal format (Project Setup) was changed after these sections were generated -- "
                "go to Structure and click **Generate Proposal Structure** again first, or the "
                "exported pack will be missing the Introduction/Methodology drafts even if you "
                "already ran drafting."
            )

        if st.button("Generate Small Scope Pack DOCX", type="primary", disabled=not ready):
            with st.spinner("Assembling document..."):
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
                )
            st.success("Document generated.")
    else:
        st.caption("Generates the first-pass DOCX response pack. Review the checklist inside the document before this goes anywhere near a real submission.")

        ready = st.session_state.sections is not None and st.session_state.guidance_notes is not None
        if not ready:
            st.info("Generate the Proposal Structure first. Drafts, graphics, and fee estimate are optional but recommended before exporting.")

        if _structure_format_stale():
            st.warning(
                "The Proposal format (Project Setup) was changed after these sections were generated -- "
                "go to Structure and click **Generate Proposal Structure** again first, or the "
                "exported pack may not match what you drafted."
            )

        if st.button("Generate DOCX", type="primary", disabled=not ready):
            with st.spinner("Assembling document..."):
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
                    # First-pass image of the reviewed design stages, placed
                    # above the "paste the finished table here" note -- same
                    # pattern as the org chart. None when no grid exists, in
                    # which case the note renders alone, as before.
                    firm=_firm_export_context(),
                    methodology_stages_png=methodology_stages.render_stages_png(
                        st.session_state.methodology_stages,
                        st.session_state.program_week_labels,
                        st.session_state.proposal_theme,
                        bool(st.session_state.methodology_wvr_confirmed),
                    ),
                )
                st.session_state.docx_buffer = buffer
                _mark_export_generated()

                # Companion internal document -- everything that's about how the
                # brief was read and how this pack was assembled (tender summary,
                # compliance matrix, gap analysis, review checklist, user-input
                # list), kept OUT of the proposal itself so that document is only
                # the proposal. Generated alongside it, same click.
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
                )
            st.success("Document generated.")

    if st.session_state.docx_buffer:
        if _export_is_stale():
            st.warning(
                "**These files were generated before your latest edits.** Downloading now gives "
                "you the older pack. Generate again to pick up the changes."
            )
        filename = (st.session_state.tender_name or "tender_response_pack").replace(" ", "_")
        suffix = "small_scope_pack" if _is_letter() else "large_scope_pack"
        # Small Scope: DOCX + Tender Summary. Large Scope: DOCX + Org Chart + Methodology
        # Table + Program, all PPTX, + Tender Summary.
        dcols = st.columns(2 if _is_letter() else 5)
        with dcols[0]:
            st.download_button(
                "Download DOCX", data=st.session_state.docx_buffer,
                file_name=f"{filename}_{suffix}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
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
                try:
                    chart_bytes = _cached_pptx(
                        "org_chart",
                        (
                            tuple((a.slot, a.person_name, a.is_lead, a.custom_title)
                                  for a in (st.session_state.resource_plan or [])),
                            st.session_state.client_name, st.session_state.project_name,
                            st.session_state.tender_name, st.session_state.proposal_theme,
                        ),
                        lambda: org_chart_pptx.populate_org_chart(
                            st.session_state.resource_plan or [],
                            client_name=st.session_state.client_name,
                            project_name=st.session_state.project_name,
                            tender_name=st.session_state.tender_name,
                            theme_name=st.session_state.proposal_theme,
                        ),
                    )
                    st.download_button(
                        "Download Org Chart (PPTX)",
                        data=chart_bytes,
                        file_name="Org_Chart.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     type="primary")
                    st.caption(
                        "Built from this project's resourcing plan -- each discipline's lead plus "
                        "anyone added under them, with red \"TBC\" for unassigned roles and "
                        "[CONFIRM TITLE] where a support member has no title yet. The client's own "
                        "PM and subconsultant firms aren't shown -- the app holds no data for them. "
                        "Fill in the gaps, then paste the finished chart over the first-pass image "
                        "in the DOCX."
                    )
                except Exception:
                    # Never let a chart-generation bug block the DOCX download that
                    # actually matters -- just skip the org chart download this time.
                    st.caption("Couldn't build the org chart this time -- the DOCX download above is unaffected.")

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
                try:
                    methodology_bytes = _cached_pptx(
                        "methodology",
                        (
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
                        ),
                    )
                    st.download_button(
                        "Download Methodology Table (PPTX)",
                        data=methodology_bytes,
                        file_name="Methodology_Table.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     type="primary")
                    st.caption(
                        "Built from the design stages you reviewed on the Draft Responses step -- "
                        "every column is real content, with red TBC where the brief didn't support a "
                        "cell. Without a reviewed grid it falls back to the generic four-stage layout. "
                        "Fill in any TBCs, then paste the finished table over the first-pass image in "
                        "the DOCX."
                        if st.session_state.methodology_stages else
                        "No design stages reviewed yet, so this is the generic four-stage fallback: "
                        "column 2 from your real scope items, the rest red placeholders. Run **Draft "
                        "methodology stages** on the Draft Responses step to fill all four columns."
                    )
                except Exception:
                    # Never let a chart-generation bug block the DOCX download that
                    # actually matters -- just skip the methodology table download this time.
                    st.caption("Couldn't build the methodology table this time -- the DOCX download above is unaffected.")

        # Same PPTX-companion pattern as the org chart / methodology table above -- the
        # Large Scope pack's DOCX has no Program section of its own (unlike the Small
        # Scope pack, which embeds one inline), so the delivery program built in the Fee
        # Estimate tab is exported here instead, as an editable Gantt-style table (see
        # program_pptx.populate_program) to paste into a program/methodology slide.
        if not _is_letter():
            with dcols[3]:
                try:
                    program_bytes = _cached_pptx(
                        "program",
                        (
                            tuple((title, tuple(bool(w) for w in weeks))
                                  for title, weeks in (st.session_state.program_schedule or {}).items()),
                            tuple(st.session_state.program_week_labels or []),
                            st.session_state.client_name, st.session_state.project_name,
                            st.session_state.proposal_theme,
                        ),
                        lambda: program_pptx.populate_program(
                            st.session_state.program_schedule or {},
                            st.session_state.program_week_labels or [],
                            client_name=st.session_state.client_name,
                            project_name=st.session_state.project_name,
                            theme_name=st.session_state.proposal_theme,
                        ),
                    )
                    st.download_button(
                        "Download Program (PPTX)",
                        data=program_bytes,
                        file_name="Delivery_Program.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     type="primary")
                    st.caption(
                        "Built from the delivery program entered in the Fee Estimate tab -- shows a red "
                        "placeholder if no program has been generated there yet."
                    )
                except Exception:
                    # Never let a chart-generation bug block the DOCX download that
                    # actually matters -- just skip the program download this time.
                    st.caption("Couldn't build the program this time -- the DOCX download above is unaffected.")

        # The Tender Summary is a separate document (see export_docx.build_tender_summary_docx),
        # generated in the same click as the Proposal DOCX above -- everything about how the
        # brief was read and how this pack was assembled (a guide to the brief's main
        # requirements, plus the compliance matrix, gap analysis, review checklist, and
        # user-input list, where generated) lives here instead of inside the proposal itself.
        # Available for both pack sizes -- the Small Scope pack just won't have an evaluation
        # weighting chart or (unless run manually in tab 4) a compliance matrix/gap analysis.
        with dcols[1 if _is_letter() else 4]:
            if st.session_state.tender_summary_buffer:
                st.download_button(
                    "Download Tender Summary (DOCX)",
                    data=st.session_state.tender_summary_buffer,
                    file_name=f"{filename}_tender_summary.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 type="primary")
                st.caption(
                    "Companion internal document -- guidance on the brief's main requirements, plus "
                    "the compliance matrix, gap analysis, review checklist, and user input list where "
                    "generated. Not part of the proposal itself."
                )
            else:
                st.caption("Tender Summary document will be generated alongside the DOCX above.")

        st.divider()
        st.markdown("#### Proposal Library")
        st.caption(
            "Archive this generated proposal into the Proposal Library "
            f"(library/{st.session_state.project_type or '<project type>'}/) for reuse later -- "
            "as a 'Previous proposals' reference in Upload Docs, or to browse and "
            "download from the 'Proposal Library' button in the top banner. Nothing is archived automatically; click below "
            "whenever you're happy with this version. Only the proposal DOCX itself is archived, "
            "not the Tender Summary or the PowerPoint companions above."
        )
        if st.button("Archive to Library", key="archive_to_library_btn", type="primary"):
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
                st.success(f"Archived to the library under '{_archived['project_type']}' as {_archived['filename']}.")
            except Exception as exc:
                _show_error("Couldn't archive to the library", exc)

    # -----------------------------------------------------------------------
    # Returnable schedules -- fill the client's own response forms (DOCX
    # tables/forms, XLSX schedules) from this project's data, preserving
    # their original formatting (see modules/returnable_schedules.py).
    # Available whether or not the proposal DOCX has been generated: the
    # schedules only need project data, not the pack.
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("#### Returnable schedules")
    st.caption(
        "Fill the client's own response forms from this project's data -- company and contact "
        "details, key personnel, reference projects, fee build-up -- inside their original "
        "document, formatting intact. Anything the project doesn't actually know is left as a "
        f"clearly-marked **{returnable_schedules.PLACEHOLDER_PREFIX}: ...]** placeholder, never "
        "a guess. Schedules found in an uploaded tender-package ZIP appear here automatically; "
        "you can also upload more below."
    )
    _extra_scheds = st.file_uploader(
        "Add schedules to fill (DOCX or XLSX)", type=["docx", "xlsx", "xlsm"],
        accept_multiple_files=True, key="_returnable_sched_uploader",
    )
    if _extra_scheds:
        for _f in _extra_scheds:
            _name = _f.name
            if _name not in (st.session_state.returnable_schedule_files or {}):
                if _name.lower().endswith(".docx") and not returnable_schedules.looks_like_response_form(_name, _f.getvalue()):
                    st.info(
                        f"'{_name}' doesn't look like a response form (its tables are already "
                        f"full, or it has none) -- it'll still be attempted, but check the "
                        f"result carefully."
                    )
                st.session_state.returnable_schedule_files = {
                    **(st.session_state.returnable_schedule_files or {}),
                    _name: _f.getvalue(),
                }

    _sched_files = st.session_state.returnable_schedule_files or {}
    if not _sched_files:
        st.caption("No schedules yet -- upload a tender-package ZIP in Upload Docs, or add files above.")
    else:
        _sched_names = sorted(_sched_files)
        st.write(f"**{len(_sched_names)} schedule(s) ready:** " + ", ".join(f"`{n}`" for n in _sched_names))
        _rm_col1, _rm_col2 = st.columns([3, 1])
        with _rm_col2:
            _to_remove = st.selectbox("Remove a file", ["(keep all)"] + _sched_names, key="_sched_remove_pick",
                                      label_visibility="collapsed")
            if _to_remove != "(keep all)" and st.button("Remove", key="_sched_remove_btn"):
                _new = dict(_sched_files)
                _new.pop(_to_remove, None)
                st.session_state.returnable_schedule_files = _new
                st.rerun()
        with _rm_col1:
            if st.button("Fill schedules from this project's data", type="primary", key="_fill_scheds_btn"):
                # Firm-level answers (ABN, insurances, certifications,
                # registered address) come from the firm profile -- these
                # labels were permanently placeholdered before it existed.
                _fill_data = returnable_schedules.build_fill_data(
                    st.session_state, firm_profile.schedule_fill_data(_firm_profile()),
                )
                _results = []
                with st.spinner(f"Filling {len(_sched_names)} schedule(s)..."):
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
                st.download_button(
                    "Download filled copy",
                    data=_res.file_bytes,
                    file_name=returnable_schedules.filled_filename(_res.filename),
                    mime=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                          if _res.kind == "docx" else
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    key=f"_sched_dl_{_res.filename}",
                    type="primary",
                )
            with _fcol2:
                st.caption(
                    f"{len(_res.filled)} field(s) filled from project data, "
                    f"{len(_res.placeholdered)} left as clearly-marked placeholders to complete. "
                    f"Review everything before submitting -- this is a first pass, and the "
                    f"placeholders are deliberate: the project doesn't know those answers."
                )
            if _res.filled or _res.placeholdered:
                with st.expander(f"What was filled / placeholdered in {_res.filename}"):
                    if _res.filled:
                        st.markdown("**Filled from project data:**")
                        st.dataframe(
                            [{"Where": f["where"], "Field": f["label"], "Value": f["value"]} for f in _res.filled],
                            use_container_width=True, hide_index=True,
                        )
                    if _res.placeholdered:
                        st.markdown("**Left as placeholders (complete before submission):**")
                        st.dataframe(
                            [{"Where": f["where"], "Field": f["label"]} for f in _res.placeholdered],
                            use_container_width=True, hide_index=True,
                        )


# ---------------------------------------------------------------------------
# Auto-save -- runs once per script execution, after every tab above has had
# a chance to mutate session_state, so it captures this run's latest state.
# ---------------------------------------------------------------------------

_maybe_autosave()

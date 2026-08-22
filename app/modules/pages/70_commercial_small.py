# modules/pages/70_commercial_small.py -- one segment of the CivilProposals app script.
# Tab 9 Fees & Program -- SMALL SCOPE (letter) packs. The Large Scope branch lives in 71_commercial_large.py.
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
# Tab 9: Fee Estimate
# ---------------------------------------------------------------------------


# SPLIT NOTE (Batch 7): the pre-split file rendered this tab as one
# `with tabs[8]: ... if _is_letter(): <small> else: <large>` block -- too
# big for one file. It is now two exclusive `if` blocks in two files, each
# re-entering `with tabs[8]:` (Streamlit appends to the same tab, and only
# one branch ever renders anything, so the result is identical).
with tabs[8]:
    st.subheader(i18n.t("fee_small_tab_title_fees_program") if _is_letter() else i18n.t("fee_small_tab_title_fee_estimate"))

    if _is_letter():
        st.caption(i18n.t("fee_small_letter_caption"))
        _fee_inclusion_summary()
        analysis = st.session_state.analysis
        scope_items = analysis.scope_items if analysis else []
        if analysis is None:
            st.info(i18n.t("fee_small_run_analysis_first"))
        elif not scope_items:
            st.info(i18n.t("fee_small_run_tender_scope_items"))
        else:
            @st.fragment
            def _render_letter_scope_fee_table():
                # Same fragment-wrap rationale as the discipline table below -- see
                # _render_large_discipline_fee_table(). scope_items/analysis are
                # cheap to recompute here rather than relying on the outer
                # script's locals, since this fragment can rerun independently.
                analysis = st.session_state.analysis
                scope_items = analysis.scope_items if analysis else []
                st.markdown(i18n.t("fee_small_scope_items_heading"))
                _fee_include_checkbox("scope_buildup", "_inc_letter_scope")
                # TODO A2 i18n: shared constant from fee_estimation_engine.py, not owned by this file.
                st.caption(fee_estimation_engine.SCOPE_FEE_SEED_NOTE)
                st.caption(i18n.t("fee_small_scope_seed_explanation"))
                seed_col1, seed_col2 = st.columns([2, 1])
                with seed_col1:
                    st.number_input(i18n.t("fee_small_ballpark_total_label"), min_value=0.0, step=500.0, key="fee_seed_total")
                with seed_col2:
                    st.write("")
                    if st.button(i18n.t("fee_small_seed_button"), type="primary"):
                        st.session_state.scope_item_fees = fee_estimation_engine.seed_scope_item_fees(
                            scope_items, st.session_state.fee_seed_total,
                        )

                if not st.session_state.scope_item_fees:
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                        fee_estimation_engine.seed_scope_item_fees(scope_items, None)
                    )
                    st.session_state._scope_fee_editor_version += 1
                else:
                    # Add any newly-extracted scope items (e.g. after a Tender Analysis
                    # re-run) without wiping rows the user has already priced, added, or
                    # renamed -- same "merge in new, never clobber edits" pattern as the
                    # discipline fee table below.
                    existing_titles = {f.item_title.strip().lower() for f in st.session_state.scope_item_fees}
                    for item in scope_items:
                        if item.title.strip().lower() not in existing_titles:
                            st.session_state.scope_item_fees.append(
                                fee_estimation_engine.ScopeItemFee(item_title=item.title, fee_amount=0.0,
                                                                   notes=i18n.t("fee_small_scope_note_default"))
                            )
                            # Force the data_editor below to actually pick up this new row --
                            # it ignores its `data` argument once its widget state already
                            # exists under a given key, so a merge alone would silently never
                            # show up until the key itself changes. See the state-defaults
                            # comment for _scope_fee_editor_version.
                            st.session_state._scope_fee_editor_version += 1
                    # Project Management is a fixed line item, additional to whatever
                    # deliverables Tender Analysis extracts -- re-add it if a fresh
                    # Tender Analysis run reset the list without it (first-time seed
                    # above already guarantees it; this covers older projects/state).
                    if not any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                               for f in st.session_state.scope_item_fees):
                        st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                            st.session_state.scope_item_fees
                        )
                        st.session_state._scope_fee_editor_version += 1

                # Built from st.session_state.scope_item_fees itself (not re-derived from
                # scope_items every rerun) so rows the user adds, renames, or deletes via
                # the editor below actually persist -- deliverables/activities aren't
                # locked to exactly what Tender Analysis extracted.
                fee_rows = [
                    {"item_title": f.item_title, "fee_amount": f.fee_amount, "notes": f.notes}
                    for f in st.session_state.scope_item_fees
                ]
                edited_fees = st.data_editor(
                    fee_rows, key=f"scope_fee_editor_v{st.session_state._scope_fee_editor_version}",
                    use_container_width=True, hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        "item_title": st.column_config.TextColumn(i18n.t("fee_small_col_scope_item_deliverable"), required=True),
                        "fee_amount": st.column_config.NumberColumn(i18n.t("fee_small_col_fee_amount"), min_value=0.0, step=50.0, format="$%.0f"),
                        "notes": st.column_config.TextColumn(i18n.t("fee_small_col_notes")),
                    },
                )
                st.caption(i18n.t("fee_small_delete_row_hint"))
                # Deferred apply -- same pattern as the discipline fee build-up
                # table's checkbox (see the comment there for the full
                # rationale). Rebuilding the model and re-adding Project
                # Management only happens once the user ticks the box, so
                # reruns while typing stay cheap.
                _scope_raw_sig = tuple(
                    (str(r.get("item_title") or ""), r.get("fee_amount"), str(r.get("notes") or ""))
                    for r in edited_fees
                )
                _scope_first_load = st.session_state.get("_scope_fee_last_applied_editor_sig") is None
                _scope_pending = _scope_raw_sig != st.session_state.get("_scope_fee_last_applied_editor_sig")
                # A button, not a checkbox-as-button -- see _fee_apply_control.
                # The two tick_seen bookkeeping keys this used to need are gone
                # with it: a button is only True on the run it is clicked, which
                # is the semantic the checkbox was being made to fake.
                scope_apply_now = _fee_apply_control("_scope_fee_", _scope_pending, i18n.t("fee_indent_note_total"))

                if _scope_first_load or (scope_apply_now and _scope_pending):
                    rebuilt_scope_fees = [
                        fee_estimation_engine.ScopeItemFee(
                            item_title=str(r.get("item_title") or "").strip(),
                            fee_amount=float(r.get("fee_amount") or 0), notes=str(r.get("notes") or ""),
                        )
                        for r in edited_fees
                        if str(r.get("item_title") or "").strip()
                    ]
                    # Project Management is a fixed line item -- if the user deleted it via
                    # the editor's own row-delete control, silently re-add it (mirrors the
                    # discipline fee table's "always re-add Project Management" behaviour).
                    _had_pm = any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                                  for f in rebuilt_scope_fees)
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(rebuilt_scope_fees)
                    if not _had_pm:
                        st.session_state._scope_fee_editor_version += 1
                        st.info(i18n.t("fee_small_scope_pm_readded_info"))
                    st.session_state._scope_fee_last_applied_editor_sig = _scope_raw_sig
                else:
                    st.caption(
                        i18n.t("fee_small_scope_ticked_stale")
                        if _scope_pending else
                        i18n.t("fee_small_scope_ticked_current")
                    )

                total = sum(f.fee_amount for f in st.session_state.scope_item_fees)
                st.markdown(i18n.t("fee_small_scope_total", total=f"{total:,.0f}"))
                if any(f.fee_amount <= 0 for f in st.session_state.scope_item_fees):
                    st.warning(i18n.t("fee_small_scope_unpriced_warning"))

            # Deliberately rendered LAST and collapsed. This table is not
            # exported; the two below it are. It used to sit first and open,
            # so the biggest, most prominent fee table on the tab was the one
            # that never reaches the client -- inverted emphasis, and a real
            # source of "I priced it and it didn't come out" confusion.
            _render_deferred_scope_table = True

            st.divider()
            @st.fragment
            def _render_letter_discipline_fee_table():
                # Same fragment-wrap rationale as the Large Scope discipline
                # table -- see _render_large_discipline_fee_table().
                st.markdown(i18n.t("fee_small_discipline_heading"))
                _fee_include_checkbox("discipline_buildup", "_inc_letter_disc")
                st.caption(i18n.t("fee_small_discipline_caption"))
                letter_brief_disc = st.session_state.analysis.disciplines_involved if st.session_state.analysis else []
                if st.session_state.get("dismissed_fee_disciplines") is None:
                    st.session_state.dismissed_fee_disciplines = []
                letter_dismissed_fee = {d.lower() for d in st.session_state.dismissed_fee_disciplines}

                if not st.session_state.discipline_fee_lines:
                    st.session_state.discipline_fee_lines = resourcing.seed_discipline_fee_lines(letter_brief_disc)
                    st.session_state._discipline_fee_editor_version += 1
                else:
                    existing_fee_discs = {resourcing.canonical_discipline(l.discipline) for l in st.session_state.discipline_fee_lines}
                    for disc in resourcing.required_disciplines(letter_brief_disc):
                        if disc not in existing_fee_discs and disc.lower() not in letter_dismissed_fee:
                            st.session_state.discipline_fee_lines.append(resourcing.DisciplineFeeLine(discipline=disc))
                            # Force the data_editor below to re-seed from the underlying
                            # data model -- it otherwise ignores its `data` argument once
                            # its widget state already exists under a given key. See the
                            # state-defaults comment for _discipline_fee_editor_version.
                            st.session_state._discipline_fee_editor_version += 1

                # Rates the firm has already told us, filled into rows that
                # are still at zero -- see the same block on the Large Scope
                # tab. Hours stay the user's.
                _letter_prefilled_rates = _prefill_rates_from_firm_profile()
                if _letter_prefilled_rates:
                    st.caption(i18n.t("fee_small_rate_prefilled", n=_letter_prefilled_rates))
                _target_fee_prefill("letter")

                letter_disc_fee_rows = [
                    {
                        "discipline": l.discipline,
                        "total_hours": l.total_hours,
                        "rate_per_hour": l.rate_per_hour,
                        "total": l.fee_amount,
                        "note": l.note,
                    }
                    for l in st.session_state.discipline_fee_lines
                ]
                letter_before_discs = {r["discipline"].strip() for r in letter_disc_fee_rows if r["discipline"].strip()}

                letter_edited_disc_fees = st.data_editor(
                    letter_disc_fee_rows,
                    key=f"letter_discipline_fee_editor_v{st.session_state._discipline_fee_editor_version}",
                    use_container_width=True,
                    hide_index=True, num_rows="dynamic",
                    column_config={
                        "discipline": st.column_config.TextColumn(i18n.t("fee_small_col_discipline"), required=True),
                        "total_hours": st.column_config.NumberColumn(i18n.t("fee_small_col_total_hours"), min_value=0.0, step=1.0, format="%.1f"),
                        "rate_per_hour": st.column_config.NumberColumn(i18n.t("fee_small_col_rate_per_hour"), min_value=0.0, step=5.0, format="$%.0f"),
                        "total": st.column_config.NumberColumn(i18n.t("fee_small_col_total_amount"), format="$%.0f", disabled=True,
                                                                help=i18n.t("fee_small_col_total_amount_help")),
                        "note": st.column_config.TextColumn(i18n.t("fee_small_col_note")),
                    },
                )
                st.caption(i18n.t("fee_small_delete_row_hint"))
                # Deferred apply -- same rationale as the Large Scope discipline
                # table's checkbox (see the comment there): the rebuild and the
                # Excel/chart cache below only run once the user explicitly
                # ticks "done", instead of on every keystroke-commit, so most
                # reruns while typing stay cheap and the value-loss race has a
                # much smaller window to land in.
                letter_raw_sig = tuple(
                    (str(r.get("discipline") or ""), r.get("total_hours"), r.get("rate_per_hour"), str(r.get("note") or ""))
                    for r in letter_edited_disc_fees
                )
                letter_first_load = st.session_state.get("_letter_disc_fee_last_applied_editor_sig") is None
                letter_pending = letter_raw_sig != st.session_state.get("_letter_disc_fee_last_applied_editor_sig")
                # See the _disc_tick_seen comment on the Large Scope discipline
                # table for why this edge-detection flag is needed.
                # A button, not a checkbox-as-button -- see _fee_apply_control.
                # The two tick_seen bookkeeping keys this used to need are gone
                # with it: a button is only True on the run it is clicked, which
                # is the semantic the checkbox was being made to fake.
                letter_apply_now = _fee_apply_control("_letter_disc_fee_", letter_pending, i18n.t("fee_indent_note_totals_chart"))

                if letter_first_load or (letter_apply_now and letter_pending):
                    letter_rebuilt = [
                        resourcing.DisciplineFeeLine(
                            discipline=str(r.get("discipline") or "").strip(),
                            total_hours=float(r.get("total_hours") or 0),
                            rate_per_hour=float(r.get("rate_per_hour") or 0),
                            note=str(r.get("note") or ""),
                        )
                        for r in letter_edited_disc_fees
                        if str(r.get("discipline") or "").strip()
                    ]

                    letter_after_discs = {l.discipline for l in letter_rebuilt}
                    letter_removed_now = letter_before_discs - letter_after_discs
                    if letter_removed_now:
                        letter_newly_dismissed = {resourcing.canonical_discipline(d) for d in letter_removed_now if resourcing.canonical_discipline(d)}
                        st.session_state.dismissed_fee_disciplines = list(dict.fromkeys(
                            list(st.session_state.dismissed_fee_disciplines) + list(letter_newly_dismissed)
                        ))

                    letter_present = [l.discipline for l in letter_rebuilt]
                    letter_missing_always = set(resourcing.ensure_project_management_present(letter_present)) - set(letter_present)
                    for missing in letter_missing_always:
                        letter_rebuilt.append(resourcing.DisciplineFeeLine(discipline=missing,
                                                                            note=i18n.t("fee_small_note_always_included")))
                    if letter_missing_always:
                        # The user deleted Project Management via the editor's row-delete
                        # control -- it's being silently re-added to the data model, but the
                        # editor widget itself won't show it again until its key changes.
                        st.session_state._discipline_fee_editor_version += 1
                    st.session_state.discipline_fee_lines = letter_rebuilt
                    st.session_state._letter_disc_fee_last_applied_editor_sig = letter_raw_sig
                else:
                    st.caption(
                        i18n.t("fee_small_ticked_stale")
                        if letter_pending else
                        i18n.t("fee_small_ticked_current")
                    )

                # Always display from the applied model (session_state) -- see
                # the same note on the Large Scope discipline table.
                letter_rebuilt = st.session_state.discipline_fee_lines

                letter_disc_total = sum(l.fee_amount for l in letter_rebuilt)
                letter_total_hours_all = sum(l.total_hours for l in letter_rebuilt)
                letter_avg_rate = (letter_disc_total / letter_total_hours_all) if letter_total_hours_all else None
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    st.markdown(i18n.t("fee_small_disc_total_label", value=f"{letter_disc_total:,.0f}"))
                with bcol2:
                    _letter_avg_rate_value = f"${letter_avg_rate:,.0f}/hr" if letter_avg_rate else i18n.t("fee_small_avg_rate_unset")
                    st.markdown(i18n.t("fee_small_avg_rate_label", value=_letter_avg_rate_value))
                if not any(resourcing.canonical_discipline(l.discipline) == resourcing.ALWAYS_INCLUDED_DISCIPLINE
                           or l.discipline.strip().lower() == resourcing.ALWAYS_INCLUDED_DISCIPLINE.lower()
                           for l in letter_rebuilt):
                    st.info(i18n.t("fee_small_pm_readded_info"))

                # Cached the same way as the Large Scope discipline table --
                # see the comment on _disc_fee_cache_sig there for why (skips
                # redoing the Excel/chart work when the figures haven't
                # actually changed, which also shrinks the edit-commit race
                # window between this fragment rerun and the next one).
                _letter_disc_signature = tuple((l.discipline, l.total_hours, l.rate_per_hour, l.note) for l in letter_rebuilt)
                if st.session_state.get("_letter_disc_fee_cache_sig") != _letter_disc_signature:
                    st.session_state._letter_disc_fee_cache_sig = _letter_disc_signature
                    st.session_state._letter_disc_fee_cache_xlsx = resourcing.discipline_fee_lines_to_excel(
                        letter_rebuilt, theme_name=st.session_state.proposal_theme,
                        project_info=_project_info())
                    st.session_state._letter_disc_fee_cache_pie = graphics_engine.generate_fee_distribution_pie(
                        [(l.discipline, l.fee_amount) for l in letter_rebuilt],
                        i18n.t("fee_small_pie_title_discipline_buildup"),
                    )
                letter_hours_xlsx = st.session_state._letter_disc_fee_cache_xlsx
                letter_hours_pie_png = st.session_state._letter_disc_fee_cache_pie
                if letter_hours_xlsx:
                    st.download_button(
                        i18n.t("fee_small_export_excel_button"), data=letter_hours_xlsx, key="letter_download_hours_fee_xlsx",
                        file_name="discipline_fee_build_up.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help=i18n.t("fee_small_export_hours_help"),
                     type="primary")
                else:
                    st.caption(i18n.t("fee_small_export_unavailable_caption"))

                if letter_hours_pie_png:
                    st.image(letter_hours_pie_png, use_container_width=True)

            _render_letter_discipline_fee_table()

            if _render_deferred_scope_table:
                st.divider()
                with st.expander(i18n.t("fee_small_scope_expander_title")):
                    _render_letter_scope_fee_table()

            st.divider()
            st.markdown(i18n.t("fee_small_delivery_program_heading"))
            pcol1, pcol2, pcol3 = st.columns([2, 2, 1])
            with pcol1:
                st.number_input(i18n.t("fee_small_num_weeks_label"), min_value=1, max_value=52, step=1, key="program_num_weeks")
            with pcol2:
                st.date_input(
                    i18n.t("fee_small_start_date_label"), value=None, key="program_start_date",
                    format="DD/MM/YYYY",
                    help=i18n.t("fee_small_start_date_help"),
                )
            with pcol3:
                st.write("")
                if st.button(i18n.t("fee_small_generate_program_button"), type="primary"):
                    st.session_state.program_schedule = program_schedule.build_default_program(
                        scope_items, st.session_state.program_num_weeks,
                    )
                    st.session_state.program_week_labels = program_schedule.week_labels(
                        st.session_state.program_num_weeks, st.session_state.program_start_date,
                    )

            if st.session_state.program_schedule:
                # Relabel every rerun, not only at generation: the start date is
                # usually entered AFTER the grid exists, and a program whose
                # headers ignored it would be a silently wrong document. Width
                # comes from the schedule itself so the labels can never
                # disagree with the number of columns actually in the grid.
                st.session_state.program_week_labels = program_schedule.week_labels(
                    _program_week_count(), st.session_state.program_start_date,
                )
                labels = st.session_state.program_week_labels
                program_rows = [
                    {"Scope item": title, **{lbl: bool(v) for lbl, v in zip(labels, active)}}
                    for title, active in st.session_state.program_schedule.items()
                ]
                column_config = {"Scope item": st.column_config.TextColumn(i18n.t("fee_small_col_scope_item"), disabled=True)}
                for lbl in labels:
                    column_config[lbl] = st.column_config.CheckboxColumn(lbl)
                edited_program = st.data_editor(
                    program_rows, key="program_editor", use_container_width=True, hide_index=True,
                    column_config=column_config,
                )
                st.session_state.program_schedule = {
                    r["Scope item"]: [bool(r[lbl]) for lbl in labels] for r in edited_program
                }
                st.divider()
                _program_style_control("small")
            else:
                st.info(i18n.t("fee_small_program_empty_info"))

        st.divider()
        @st.fragment
        def _render_letter_pct_fee_table():
            # Wrapped in its own fragment (this used to rerun the entire ~3800-line
            # script on every keystroke, with no caching at all on the Excel/chart
            # regen below -- the worst case of the edit-commit race across all the
            # fee tables). See _render_large_discipline_fee_table() for the general
            # rationale.
            with st.expander(i18n.t("fee_small_pct_split_expander"), expanded=False):
                _fee_include_checkbox("pct_split", "_inc_letter_pct")
                st.caption(i18n.t("fee_small_pct_split_caption"))
                # TODO A2 i18n: shared constant from fee_estimation_engine.py, not owned by this file.
                st.warning(fee_estimation_engine.INDICATIVE_NOTE)

                letter_buildup_discs = [l.discipline for l in st.session_state.discipline_fee_lines]
                letter_buildup_total = sum(l.fee_amount for l in st.session_state.discipline_fee_lines)

                # Prepopulate the total from the discipline fee build-up the first time
                # this is used (0.0 = "not yet set") -- after that it's an independent
                # figure the user can edit freely, even if the build-up total changes
                # later, rather than staying permanently locked to it.
                if not st.session_state.letter_fee_total_override and letter_buildup_total:
                    st.session_state.letter_fee_total_override = letter_buildup_total

                st.number_input(
                    i18n.t("fee_small_total_fee_label"),
                    min_value=0.0, step=1000.0, key="letter_fee_total_override",
                    help=i18n.t("fee_small_total_fee_help"),
                )
                letter_fee_total = st.session_state.letter_fee_total_override

                def _letter_reconcile_estimates(estimates):
                    by_disc = {resourcing.canonical_discipline(e.discipline): e for e in (estimates or [])}
                    reconciled = []
                    for disc in letter_buildup_discs:
                        key = resourcing.canonical_discipline(disc)
                        existing = by_disc.get(key)
                        if existing is not None:
                            reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                                discipline=disc, fee_percentage=existing.fee_percentage,
                                source=existing.source, confidence=existing.confidence,
                                # See the same note on the Large Scope tab.
                                pct_low=existing.pct_low, pct_high=existing.pct_high,
                            ))
                        else:
                            reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                                discipline=disc, fee_percentage=0.0, source="", confidence="",
                            ))
                    return reconciled

                _fee_history_panel("letter_apply_history")

                bcol1, bcol2, bcol3 = st.columns(3)
                with bcol1:
                    if st.button(i18n.t("fee_small_reset_pct_button"), key="letter_reset_from_buildup_btn", type="primary"):
                        if letter_buildup_total > 0:
                            st.session_state.fee_estimates = [
                                fee_estimation_engine.DisciplineFeeEstimate(
                                    discipline=l.discipline,
                                    fee_percentage=round(l.fee_amount / letter_buildup_total * 100, 1),
                                    source=i18n.t("fee_small_source_from_buildup"),
                                    confidence=i18n.t("fee_small_confidence_user_set"),
                                )
                                for l in st.session_state.discipline_fee_lines
                            ]
                        else:
                            st.warning(i18n.t("fee_small_enter_hours_first_warning"))
                with bcol2:
                    if st.button(i18n.t("fee_small_benchmark_button"), key="letter_benchmark_btn", type="primary"):
                        fee_cap = st.session_state.analysis.fee_cap if st.session_state.analysis else None
                        estimates = fee_estimation_engine.estimate_fee_split(st.session_state.project_type, fee_cap)
                        st.session_state.fee_estimates = _letter_reconcile_estimates(estimates)
                with bcol3:
                    refresh_ready = bool(st.session_state.ai_config.get("api_key")) and _current_project_already_paid()
                    # TODO A2 i18n: AI_BENCHMARK_LABEL / _ai_block_reason() / _AI_HINT_SENTENCE are
                    # shared constants/helpers from fee_estimation_engine.py and 10_state_helpers.py,
                    # not owned by this file.
                    if st.button(fee_estimation_engine.AI_BENCHMARK_LABEL, disabled=not refresh_ready,
                                 help=None if refresh_ready else (
                                     _ai_block_reason() if not _current_project_already_paid()
                                     else _AI_HINT_SENTENCE
                                 ), key="letter_refresh_btn", type="primary"):
                        fee_cap = st.session_state.analysis.fee_cap if st.session_state.analysis else None
                        with st.spinner(i18n.t("fee_small_ai_spinner")):
                            _record_ai_click()
                            estimates, _refresh_error = _fee_ai_refresh(letter_buildup_discs, fee_cap)
                        if _refresh_error:
                            # The table is left EXACTLY as it was -- see the
                            # same note on the Large Scope tab.
                            st.error(_refresh_error)
                        else:
                            st.session_state.fee_estimates = _letter_reconcile_estimates(estimates)

                st.session_state.fee_estimates = _letter_reconcile_estimates(st.session_state.fee_estimates)

                letter_fee_pct_rows = [
                    {
                        "discipline": e.discipline,
                        "fee_percentage": e.fee_percentage,
                        "indicative_amount": (f"${letter_fee_total * e.fee_percentage / 100:,.0f}"
                                               if letter_fee_total else "-"),
                        "typical_range": (e.range_text if e.pct_low is not None else ""),
                        "confidence": e.confidence,
                        "source": e.source,
                    }
                    for e in st.session_state.fee_estimates
                ]
                letter_edited_pct = st.data_editor(
                    letter_fee_pct_rows, key="letter_fee_pct_editor", use_container_width=True, hide_index=True,
                    column_config={
                        "discipline": st.column_config.TextColumn(i18n.t("fee_small_col_discipline"), disabled=True),
                        "fee_percentage": st.column_config.NumberColumn(i18n.t("fee_small_col_fee_pct"), min_value=0.0, max_value=100.0, step=0.5, format="%.1f%%"),
                        "indicative_amount": st.column_config.TextColumn(
                            i18n.t("fee_small_col_indicative_amount"), disabled=True,
                            help=i18n.t("fee_small_col_indicative_amount_help"),
                        ),
                        "typical_range": st.column_config.TextColumn(
                            i18n.t("fee_small_col_typical_range"), disabled=True,
                            help=i18n.t("fee_small_col_typical_range_help"),
                        ),
                        "confidence": st.column_config.TextColumn(i18n.t("fee_small_col_confidence")),
                        "source": st.column_config.TextColumn(i18n.t("fee_small_col_source")),
                    },
                )

                # Deferred apply -- same pattern as the discipline fee build-up
                # table's checkbox (see the comment there for the full rationale).
                # The three buttons above are unaffected -- they're deliberate,
                # single-click actions, not rapid per-keystroke edits, so they
                # still take effect immediately.
                letter_pct_raw_sig = tuple(
                    (r.get("discipline"), r.get("fee_percentage"), r.get("confidence"), r.get("source"))
                    for r in letter_edited_pct
                )
                letter_pct_first_load = st.session_state.get("_letter_pct_fee_last_applied_editor_sig") is None
                letter_pct_pending = letter_pct_raw_sig != st.session_state.get("_letter_pct_fee_last_applied_editor_sig")
                # A button, not a checkbox-as-button -- see _fee_apply_control.
                # The two tick_seen bookkeeping keys this used to need are gone
                # with it: a button is only True on the run it is clicked, which
                # is the semantic the checkbox was being made to fake.
                letter_pct_apply_now = _fee_apply_control("_letter_pct_fee_", letter_pct_pending, i18n.t("fee_indent_note_totals_chart"))

                if letter_pct_first_load or (letter_pct_apply_now and letter_pct_pending):
                    # See the same note on the Large Scope tab: the range
                    # belongs to the benchmark, not to a number the user typed.
                    _letter_prior_pct = {e.discipline: e for e in st.session_state.fee_estimates}
                    st.session_state.fee_estimates = [
                        fee_estimation_engine.keep_range_if_unedited(
                            fee_estimation_engine.DisciplineFeeEstimate(
                                discipline=r["discipline"],
                                fee_percentage=float(r["fee_percentage"] or 0),
                                confidence=r["confidence"] or "", source=r["source"] or "",
                            ),
                            _letter_prior_pct.get(r["discipline"]),
                        )
                        for r in letter_edited_pct
                    ]
                    st.session_state._letter_pct_fee_last_applied_editor_sig = letter_pct_raw_sig
                else:
                    st.caption(
                        i18n.t("fee_small_ticked_stale")
                        if letter_pct_pending else
                        i18n.t("fee_small_ticked_current")
                    )

                letter_pct_total = sum(e.fee_percentage for e in st.session_state.fee_estimates)
                st.caption(i18n.t("fee_small_pct_total_caption", pct=f"{letter_pct_total:.1f}"))

                _letter_pct_indicative_amounts = {
                    e.discipline: (letter_fee_total * e.fee_percentage / 100 if letter_fee_total else None)
                    for e in st.session_state.fee_estimates
                }
                letter_pct_xlsx = fee_estimation_engine.fee_estimates_to_excel(
                    st.session_state.fee_estimates,
                    indicative_amounts=_letter_pct_indicative_amounts,
                    theme_name=st.session_state.proposal_theme,
                    project_info=_project_info(),
                )
                if letter_pct_xlsx:
                    st.download_button(
                        i18n.t("fee_small_export_excel_button"), data=letter_pct_xlsx, key="letter_download_pct_fee_xlsx",
                        file_name="indicative_fee_split.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     type="primary")
                else:
                    st.caption(i18n.t("fee_small_export_unavailable_caption"))

                # Chart the $ split once a total is available (matches the $ column and
                # Excel export); otherwise chart the raw percentages.
                if letter_fee_total > 0:
                    letter_pie_items = [(e.discipline, _letter_pct_indicative_amounts.get(e.discipline) or 0) for e in st.session_state.fee_estimates]
                    letter_pie_fmt = lambda v: f"${v:,.0f}"
                    letter_pie_legend_value = "raw"
                else:
                    letter_pie_items = [(e.discipline, e.fee_percentage) for e in st.session_state.fee_estimates]
                    letter_pie_fmt = lambda v: f"{v:.0f}%"
                    letter_pie_legend_value = "share"
                letter_pie_png = graphics_engine.generate_fee_distribution_pie(
                    letter_pie_items, i18n.t("fee_small_pie_title_pct_split"), value_fmt=letter_pie_fmt,
                    legend_value=letter_pie_legend_value,
                )
                if letter_pie_png:
                    st.image(letter_pie_png, use_container_width=True)

        _render_letter_pct_fee_table()

# modules/pages/71_commercial_large.py -- one segment of the CivilProposals app script.
# Tab 9 Fee Estimate -- LARGE SCOPE packs. The Small Scope (letter) branch lives in 70_commercial_small.py.
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
    if not _is_letter():
        @st.fragment
        def _render_large_discipline_fee_table():
            # Wrapped in a fragment so editing a cell only reruns this table
            # (fast, in place) instead of the whole ~3700-line script -- without
            # this, each keystroke-commit reruns everything (every other tab's
            # code, every chart) which is slow enough that fast typing across
            # cells can land before the previous rerun finishes and get
            # silently dropped when the widget remounts. Downstream sections
            # (the "Indicative fee split" below) read st.session_state
            # .discipline_fee_lines directly rather than a local variable here,
            # since this fragment can rerun on its own without the rest of the
            # script -- they'll pick up the latest values on their own next full
            # rerun (e.g. switching tabs).
            st.markdown("#### First-pass discipline fee build-up")
            st.caption(
                "Your own first-pass fee per discipline, built from hours x rate. The table is "
                "seeded from the disciplines the brief calls for, plus Project Management (always "
                "included). Enter total hours and an hourly rate per discipline -- the Total column "
                "is calculated automatically, not typed in directly. Add or remove rows as needed -- "
                "these are your figures, not an AI estimate."
            )
            brief_disc = st.session_state.analysis.disciplines_involved if st.session_state.analysis else []
            if st.session_state.get("dismissed_fee_disciplines") is None:
                st.session_state.dismissed_fee_disciplines = []
            dismissed_fee = {d.lower() for d in st.session_state.dismissed_fee_disciplines}

            if not st.session_state.discipline_fee_lines:
                st.session_state.discipline_fee_lines = resourcing.seed_discipline_fee_lines(brief_disc)
                st.session_state._discipline_fee_editor_version += 1
            else:
                # Add any newly-required disciplines (e.g. after a Tender Analysis re-run
                # picks up more of them) without wiping existing entries -- but never
                # re-add one the user explicitly removed from this table.
                existing_fee_discs = {resourcing.canonical_discipline(l.discipline) for l in st.session_state.discipline_fee_lines}
                for disc in resourcing.required_disciplines(brief_disc):
                    if disc not in existing_fee_discs and disc.lower() not in dismissed_fee:
                        st.session_state.discipline_fee_lines.append(resourcing.DisciplineFeeLine(discipline=disc))
                        # Force the data_editor below to re-seed from the underlying data
                        # model -- it otherwise ignores its `data` argument once its
                        # widget state already exists under a given key. See the
                        # state-defaults comment for _discipline_fee_editor_version.
                        st.session_state._discipline_fee_editor_version += 1

            disc_fee_rows = [
                {
                    "discipline": l.discipline,
                    "total_hours": l.total_hours,
                    "rate_per_hour": l.rate_per_hour,
                    "total": l.fee_amount,
                    "note": l.note,
                }
                for l in st.session_state.discipline_fee_lines
            ]
            before_discs = {r["discipline"].strip() for r in disc_fee_rows if r["discipline"].strip()}

            edited_disc_fees = st.data_editor(
                disc_fee_rows, key=f"discipline_fee_editor_v{st.session_state._discipline_fee_editor_version}",
                use_container_width=True,
                hide_index=True, num_rows="dynamic",
                column_config={
                    "discipline": st.column_config.TextColumn("Discipline", required=True),
                    "total_hours": st.column_config.NumberColumn("Total hours", min_value=0.0, step=1.0, format="%.1f"),
                    "rate_per_hour": st.column_config.NumberColumn("Rate per hour ($)", min_value=0.0, step=5.0, format="$%.0f"),
                    "total": st.column_config.NumberColumn("Total ($, excl. GST)", format="$%.0f", disabled=True,
                                                            help="Calculated automatically -- total hours x rate per hour."),
                    "note": st.column_config.TextColumn("Note"),
                },
            )
            st.caption(
                "To delete a row: tick the checkbox on its left, then either press "
                "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
                "above the table."
            )
            # Deferred apply: rebuilding the model (dedup/dismiss logic) and
            # regenerating the Excel export + pie chart on literally every
            # keystroke-commit was a big contributor to the intermittent
            # value-loss race in this grid -- every rerun while the user was
            # actively typing did real work server-side, widening the window
            # in which a second, fast edit could race the round trip and get
            # silently dropped. Now, reruns while editing do nothing but hold
            # the editor's own state (cheap); the heavier rebuild only runs
            # once, on a deliberate, separate action -- ticking this box --
            # well after typing has settled. Any further edit auto-unticks
            # it, so stale numbers can't linger unnoticed.
            _disc_raw_sig = tuple(
                (str(r.get("discipline") or ""), r.get("total_hours"), r.get("rate_per_hour"), str(r.get("note") or ""))
                for r in edited_disc_fees
            )
            _disc_first_load = st.session_state.get("_disc_fee_last_applied_editor_sig") is None
            _disc_pending = _disc_raw_sig != st.session_state.get("_disc_fee_last_applied_editor_sig")
            # Distinguish "the user just ticked the box this rerun" (must NOT
            # be reset -- that's the click we want to act on) from "the box
            # was already ticked from a previous apply, and a fresh edit
            # since then has made it stale" (SHOULD be reset). Both look
            # identical as (pending=True, tick=True) at the top of a rerun,
            # so _disc_fee_apply_tick_seen tracks whether the tick was
            # already True as of the end of the *previous* rerun -- only
            # then is it safe to call it stale.
            _disc_tick_val = st.session_state.get("_disc_fee_apply_tick", False)
            _disc_tick_seen = st.session_state.get("_disc_fee_apply_tick_seen", False)
            if _disc_pending and _disc_tick_val and _disc_tick_seen:
                st.session_state["_disc_fee_apply_tick"] = False
            disc_apply_now = st.checkbox(
                "Done entering data -- refresh totals & chart",
                key="_disc_fee_apply_tick",
            )
            st.session_state["_disc_fee_apply_tick_seen"] = disc_apply_now

            if _disc_first_load or (disc_apply_now and _disc_pending):
                # Rebuild from the editor, dropping blank-discipline rows, then guarantee
                # Project Management is present even if the user deleted it.
                rebuilt = [
                    resourcing.DisciplineFeeLine(
                        discipline=str(r.get("discipline") or "").strip(),
                        total_hours=float(r.get("total_hours") or 0),
                        rate_per_hour=float(r.get("rate_per_hour") or 0),
                        note=str(r.get("note") or ""),
                    )
                    for r in edited_disc_fees
                    if str(r.get("discipline") or "").strip()
                ]

                # A discipline present before this edit but missing after it was removed
                # via the editor's own delete-row control -- remember that so the
                # brief-sync merge above doesn't just re-add it on the next rerun.
                after_discs = {l.discipline for l in rebuilt}
                removed_now = before_discs - after_discs
                if removed_now:
                    newly_dismissed = {resourcing.canonical_discipline(d) for d in removed_now if resourcing.canonical_discipline(d)}
                    st.session_state.dismissed_fee_disciplines = list(dict.fromkeys(
                        list(st.session_state.dismissed_fee_disciplines) + list(newly_dismissed)
                    ))

                present = [l.discipline for l in rebuilt]
                missing_always = set(resourcing.ensure_project_management_present(present)) - set(present)
                for missing in missing_always:
                    rebuilt.append(resourcing.DisciplineFeeLine(discipline=missing,
                                                                note="Always included -- re-added automatically"))
                if missing_always:
                    # The user deleted Project Management via the editor's row-delete
                    # control -- it's being silently re-added to the data model, but the
                    # editor widget itself won't show it again until its key changes.
                    st.session_state._discipline_fee_editor_version += 1
                st.session_state.discipline_fee_lines = rebuilt
                st.session_state._disc_fee_last_applied_editor_sig = _disc_raw_sig
            else:
                st.caption(
                    "Totals, the chart, and the Excel export below are from the last time "
                    "you ticked the box above -- tick it again to bring them up to date."
                    if _disc_pending else
                    "Totals, the chart, and the Excel export below reflect the ticked data above."
                )

            # Always display from the applied model (session_state), not a
            # freshly-rebuilt local var -- until the box above is (re)ticked,
            # this intentionally still shows the last-applied figures even
            # though the editor itself may have newer, unapplied edits in it.
            rebuilt = st.session_state.discipline_fee_lines

            disc_total = sum(l.fee_amount for l in rebuilt)
            total_hours_all = sum(l.total_hours for l in rebuilt)
            # The blended rate across the whole project (total fee / total hours) --
            # the key sanity-check figure for whether the priced hours/rates make
            # sense in aggregate, not just discipline by discipline.
            avg_rate = (disc_total / total_hours_all) if total_hours_all else None
            mcol1, mcol2 = st.columns(2)
            with mcol1:
                st.markdown(f"**Discipline fee total: ${disc_total:,.0f}**")
            with mcol2:
                st.markdown(f"**Average rate across project: {f'${avg_rate:,.0f}/hr' if avg_rate else '-- (enter hours to calculate)'}**")
            if not any(resourcing.canonical_discipline(l.discipline) == resourcing.ALWAYS_INCLUDED_DISCIPLINE
                       or l.discipline.strip().lower() == resourcing.ALWAYS_INCLUDED_DISCIPLINE.lower()
                       for l in rebuilt):
                st.info("Project Management is always part of the fee build-up and has been re-added.")

            # The Excel export and pie chart are regenerated from `rebuilt` --
            # both are real work (openpyxl workbook + matplotlib render), and
            # without caching that ran again on literally every keystroke
            # commit, even ones that don't touch these disciplines at all.
            # That's wasted time on its own, but it also matters for
            # correctness: it's extra wall-clock inside this fragment's rerun,
            # which widens the window in which a second, fast edit (typing
            # into the next row before this rerun settles) can race the
            # server round-trip and have its own value overwritten by a
            # stale re-render. Skipping the regen when the underlying figures
            # haven't changed since the last render shrinks that window.
            # Keyed by a plain tuple signature (not an object identity) so it
            # survives across reruns via session_state.
            _disc_signature = tuple((l.discipline, l.total_hours, l.rate_per_hour, l.note) for l in rebuilt)
            if st.session_state.get("_disc_fee_cache_sig") != _disc_signature:
                st.session_state._disc_fee_cache_sig = _disc_signature
                st.session_state._disc_fee_cache_xlsx = resourcing.discipline_fee_lines_to_excel(
                    rebuilt, theme_name=st.session_state.proposal_theme,
                    project_info=_project_info())
                st.session_state._disc_fee_cache_pie = graphics_engine.generate_fee_distribution_pie(
                    [(l.discipline, l.fee_amount) for l in rebuilt],
                    "Fee distribution by discipline (hours x rate)",
                )
            hours_xlsx = st.session_state._disc_fee_cache_xlsx
            hours_pie_png = st.session_state._disc_fee_cache_pie
            if hours_xlsx:
                st.download_button(
                    "Export to Excel", data=hours_xlsx, key="download_hours_fee_xlsx",
                    file_name="discipline_fee_build_up.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Includes a Total row and the average rate across the project (total fee / total hours).",
                 type="primary")
            else:
                st.caption("Excel export isn't available right now -- please email hello@civilproposals.com if this keeps happening.")

            if hours_pie_png:
                st.image(hours_pie_png, use_container_width=True)
            else:
                st.caption("Enter hours and a rate for at least one discipline above to see the fee distribution chart.")

        _render_large_discipline_fee_table()

        st.divider()
        @st.fragment
        def _render_large_scope_fee_table():
            # Same fragment-wrap rationale as the discipline table above -- see
            # _render_large_discipline_fee_table().
            st.markdown("#### Scope item / deliverable fee build-up")
            _large_scope_items = st.session_state.analysis.scope_items if st.session_state.analysis else []
            if not _large_scope_items:
                st.info("Run Tender Analysis to extract scope items and deliverables first.")
            else:
                st.caption(fee_estimation_engine.SCOPE_FEE_SEED_NOTE)
                st.caption(
                    "Prepopulated with the scope items/deliverables extracted from the brief, "
                    "one row each, so there's a real starting list to price rather than a blank "
                    "table -- edit, rename, delete, or add rows freely; nothing here is exported "
                    "automatically (the discipline build-up above is what feeds the pack)."
                )
                if not st.session_state.scope_item_fees:
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                        fee_estimation_engine.seed_scope_item_fees(_large_scope_items, None)
                    )
                    st.session_state._large_scope_fee_editor_version += 1
                else:
                    _existing_titles = {f.item_title.strip().lower() for f in st.session_state.scope_item_fees}
                    for _item in _large_scope_items:
                        if _item.title.strip().lower() not in _existing_titles:
                            st.session_state.scope_item_fees.append(
                                fee_estimation_engine.ScopeItemFee(item_title=_item.title, fee_amount=0.0,
                                                                   notes="Enter fee -- no estimate seeded")
                            )
                            # Force the data_editor below to re-seed from the underlying
                            # data model -- it otherwise ignores its `data` argument once
                            # its widget state already exists under a given key. See the
                            # state-defaults comment for _large_scope_fee_editor_version.
                            st.session_state._large_scope_fee_editor_version += 1
                    # Project Management is a fixed line item, additional to whatever
                    # deliverables Tender Analysis extracts -- re-add it if missing.
                    if not any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                               for f in st.session_state.scope_item_fees):
                        st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                            st.session_state.scope_item_fees
                        )
                        st.session_state._large_scope_fee_editor_version += 1

                _large_fee_rows = [
                    {"item_title": f.item_title, "fee_amount": f.fee_amount, "notes": f.notes}
                    for f in st.session_state.scope_item_fees
                ]
                _large_edited_fees = st.data_editor(
                    _large_fee_rows,
                    key=f"large_scope_fee_editor_v{st.session_state._large_scope_fee_editor_version}",
                    use_container_width=True, hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        "item_title": st.column_config.TextColumn("Scope item / deliverable", required=True),
                        "fee_amount": st.column_config.NumberColumn("Fee ($, excl. GST)", min_value=0.0, step=50.0, format="$%.0f"),
                        "notes": st.column_config.TextColumn("Notes"),
                    },
                )
                st.caption(
                    "To delete a row: tick the checkbox on its left, then either press "
                    "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
                    "above the table."
                )
                # Deferred apply -- same pattern as the discipline fee build-up
                # table's checkbox (see the comment there for the full
                # rationale).
                _large_scope_raw_sig = tuple(
                    (str(r.get("item_title") or ""), r.get("fee_amount"), str(r.get("notes") or ""))
                    for r in _large_edited_fees
                )
                _large_scope_first_load = st.session_state.get("_large_scope_fee_last_applied_editor_sig") is None
                _large_scope_pending = _large_scope_raw_sig != st.session_state.get("_large_scope_fee_last_applied_editor_sig")
                _large_scope_tick_val = st.session_state.get("_large_scope_fee_apply_tick", False)
                _large_scope_tick_seen = st.session_state.get("_large_scope_fee_apply_tick_seen", False)
                if _large_scope_pending and _large_scope_tick_val and _large_scope_tick_seen:
                    st.session_state["_large_scope_fee_apply_tick"] = False
                large_scope_apply_now = st.checkbox(
                    "Done entering data -- refresh total",
                    key="_large_scope_fee_apply_tick",
                )
                st.session_state["_large_scope_fee_apply_tick_seen"] = large_scope_apply_now

                if _large_scope_first_load or (large_scope_apply_now and _large_scope_pending):
                    _large_rebuilt_scope_fees = [
                        fee_estimation_engine.ScopeItemFee(
                            item_title=str(r.get("item_title") or "").strip(),
                            fee_amount=float(r.get("fee_amount") or 0), notes=str(r.get("notes") or ""),
                        )
                        for r in _large_edited_fees
                        if str(r.get("item_title") or "").strip()
                    ]
                    # Project Management is a fixed line item -- if the user deleted it via
                    # the editor's own row-delete control, silently re-add it.
                    _large_had_pm = any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                                        for f in _large_rebuilt_scope_fees)
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                        _large_rebuilt_scope_fees
                    )
                    if not _large_had_pm:
                        st.session_state._large_scope_fee_editor_version += 1
                        st.info("Project Management is a fixed line item and has been re-added.")
                    st.session_state._large_scope_fee_last_applied_editor_sig = _large_scope_raw_sig
                else:
                    st.caption(
                        "The total below is from the last time you ticked the box above -- "
                        "tick it again to bring it up to date."
                        if _large_scope_pending else
                        "The total below reflects the ticked data above."
                    )

                _large_scope_fee_total = sum(f.fee_amount for f in st.session_state.scope_item_fees)
                st.markdown(f"**Total: ${_large_scope_fee_total:,.0f}**")

        _render_large_scope_fee_table()

        st.divider()
        st.markdown("#### Delivery program")
        st.caption(
            "A starting delivery schedule across your scope items. Unlike the Small Scope "
            "pack, this isn't embedded in the DOCX -- download it as an editable PowerPoint "
            "table from the Export Pack tab instead, to paste into a program/methodology slide."
        )
        pcol1, pcol2, pcol3 = st.columns([2, 2, 1])
        with pcol1:
            st.number_input("Number of weeks", min_value=1, max_value=52, step=1, key="program_num_weeks")
        with pcol2:
            st.date_input(
                "Anticipated start date (optional)", value=None, key="program_start_date",
                format="DD/MM/YYYY",
                help="Your own expected start, not something read from the brief. Set it "
                     "and every week header becomes a real date (\"Wk 1 - 6 Oct\") in the "
                     "program table and the program PowerPoint. Leave it blank to keep "
                     "plain week numbers.",
            )
        with pcol3:
            st.write("")
            if st.button("Generate default program", type="primary"):
                st.session_state.program_schedule = program_schedule.build_default_program(
                    st.session_state.analysis.scope_items if st.session_state.analysis else [],
                    st.session_state.program_num_weeks,
                )
                st.session_state.program_week_labels = program_schedule.week_labels(
                    st.session_state.program_num_weeks, st.session_state.program_start_date,
                )

        if st.session_state.program_schedule:
            # Relabel every rerun -- see the same note on the Small Scope tab.
            st.session_state.program_week_labels = program_schedule.week_labels(
                _program_week_count(), st.session_state.program_start_date,
            )
            labels = st.session_state.program_week_labels
            program_rows = [
                {"Scope item": title, **{lbl: bool(v) for lbl, v in zip(labels, active)}}
                for title, active in st.session_state.program_schedule.items()
            ]
            program_column_config = {"Scope item": st.column_config.TextColumn("Scope item", disabled=True)}
            for lbl in labels:
                program_column_config[lbl] = st.column_config.CheckboxColumn(lbl)
            edited_program = st.data_editor(
                program_rows, key="program_editor", use_container_width=True, hide_index=True,
                column_config=program_column_config,
            )
            st.session_state.program_schedule = {
                r["Scope item"]: [bool(r[lbl]) for lbl in labels] for r in edited_program
            }
        else:
            st.info("Click 'Generate default program' for an editable starting grid, sized by how many tasks each scope item lists -- adjust the weeks freely afterwards.")

        st.divider()
        @st.fragment
        def _render_large_pct_fee_table():
            # Wrapped in its own fragment -- this used to rerun the entire
            # ~3900-line script on every keystroke, with no caching at all on
            # the Excel/chart regen below. See _render_large_discipline_fee_table()
            # for the general rationale.
            st.markdown("#### Indicative fee split by discipline")
            st.caption(
                "Its discipline list always matches the discipline fee build-up table above -- add "
                "or remove disciplines up there, not here. Fee % is directly editable below; reset "
                "it from the build-up's own $ split, or seed it from the benchmark/AI buttons "
                "(remapped onto the build-up's discipline list either way)."
            )
            st.warning(fee_estimation_engine.INDICATIVE_NOTE)

            # Read from session_state rather than the discipline-table block's own
            # `rebuilt` local (that block is a separate, self-contained
            # @st.fragment, so its locals aren't in scope here) -- equivalent,
            # since that fragment always writes its result to
            # st.session_state.discipline_fee_lines before returning.
            buildup_discs = [l.discipline for l in st.session_state.discipline_fee_lines]
            buildup_total = sum(l.fee_amount for l in st.session_state.discipline_fee_lines)

            # Prepopulate the total from the discipline fee build-up the first time
            # this is used (0.0 = "not yet set") -- after that it's an independent
            # figure the user can edit freely, even if the build-up total changes
            # later, rather than staying permanently locked to it. Same pattern as
            # the Small Scope pack's letter_fee_total_override, below.
            if not st.session_state.fee_estimate_manual_total and buildup_total:
                st.session_state.fee_estimate_manual_total = buildup_total

            st.number_input(
                "Total project fee ($, excl. GST) -- optional",
                min_value=0.0, step=1000.0, key="fee_estimate_manual_total",
                help="Starts prepopulated from the discipline fee build-up total above, then stays "
                     "independently editable -- change it here to use a different total for this "
                     "split's $ column, Excel export, and chart only. Doesn't change the build-up "
                     "table itself.",
            )
            manual_total = st.session_state.fee_estimate_manual_total

            def _reconcile_estimates(estimates):
                by_disc = {resourcing.canonical_discipline(e.discipline): e for e in (estimates or [])}
                reconciled = []
                for disc in buildup_discs:
                    key = resourcing.canonical_discipline(disc)
                    existing = by_disc.get(key)
                    if existing is not None:
                        reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                            discipline=disc, fee_percentage=existing.fee_percentage,
                            source=existing.source, confidence=existing.confidence,
                        ))
                    else:
                        reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                            discipline=disc, fee_percentage=0.0, source="", confidence="",
                        ))
                return reconciled

            bcol1, bcol2, bcol3 = st.columns(3)
            with bcol1:
                if st.button("Reset % from discipline fee build-up", key="reset_from_buildup_btn", type="primary"):
                    if buildup_total > 0:
                        st.session_state.fee_estimates = [
                            fee_estimation_engine.DisciplineFeeEstimate(
                                discipline=l.discipline,
                                fee_percentage=round(l.fee_amount / buildup_total * 100, 1),
                                source="From discipline fee build-up",
                                confidence="User-set",
                            )
                            for l in st.session_state.discipline_fee_lines
                        ]
                    else:
                        st.warning("Enter hours and rates in the discipline fee build-up table above first.")
            with bcol2:
                if st.button("Estimate from bundled benchmarks", key="benchmark_btn", type="primary"):
                    fee_cap = (str(manual_total) if manual_total > 0
                               else (st.session_state.analysis.fee_cap if st.session_state.analysis else None))
                    estimates = fee_estimation_engine.estimate_fee_split(st.session_state.project_type, fee_cap)
                    st.session_state.fee_estimates = _reconcile_estimates(estimates)
            with bcol3:
                refresh_ready = bool(st.session_state.ai_config.get("api_key")) and _current_project_already_paid()
                if st.button("Refresh via AI knowledge (not a live web fetch)", disabled=not refresh_ready,
                             help=None if refresh_ready else (
                                 _PROJECT_NOT_PAID_HINT if not _current_project_already_paid()
                                 else _AI_HINT_SENTENCE
                             ), key="refresh_btn", type="primary"):
                    fee_cap = (str(manual_total) if manual_total > 0
                               else (st.session_state.analysis.fee_cap if st.session_state.analysis else None))
                    with st.spinner("Asking the AI provider for its knowledge of published benchmarks..."):
                        estimates, _refresh_warning = fee_estimation_engine.refresh_estimate_from_web(
                            st.session_state.project_type, buildup_discs, fee_cap, st.session_state.ai_config,
                            scope_summary=(st.session_state.analysis.project_scope
                                           if st.session_state.analysis else ""),
                        )
                    # A silent fallback returned the bundled table looking
                    # exactly like a successful refresh.
                    if _refresh_warning:
                        st.warning(_refresh_warning)
                    st.session_state.fee_estimates = _reconcile_estimates(estimates)

            st.session_state.fee_estimates = _reconcile_estimates(st.session_state.fee_estimates)

            def _indicative_amount(pct):
                if manual_total > 0:
                    return manual_total * pct / 100
                if buildup_total > 0:
                    return buildup_total * pct / 100
                return None

            fee_pct_rows = [
                {
                    "discipline": e.discipline,
                    "fee_percentage": e.fee_percentage,
                    "indicative_amount": (f"${_indicative_amount(e.fee_percentage):,.0f}"
                                           if _indicative_amount(e.fee_percentage) else "-"),
                    "confidence": e.confidence,
                    "source": e.source,
                }
                for e in st.session_state.fee_estimates
            ]
            edited_pct = st.data_editor(
                fee_pct_rows, key="fee_pct_editor", use_container_width=True, hide_index=True,
                column_config={
                    "discipline": st.column_config.TextColumn("Discipline", disabled=True),
                    "fee_percentage": st.column_config.NumberColumn("Fee %", min_value=0.0, max_value=100.0, step=0.5, format="%.1f%%"),
                    "indicative_amount": st.column_config.TextColumn(
                        "Indicative $", disabled=True,
                        help="Fee % x the manual total above (if entered), else x the discipline fee build-up total.",
                    ),
                    "confidence": st.column_config.TextColumn("Confidence"),
                    "source": st.column_config.TextColumn("Source"),
                },
            )

            # Deferred apply -- same pattern as the discipline fee build-up
            # table's checkbox (see the comment there for the full rationale).
            # The three buttons above are unaffected -- they're deliberate,
            # single-click actions, not rapid per-keystroke edits, so they
            # still take effect immediately.
            pct_raw_sig = tuple(
                (r.get("discipline"), r.get("fee_percentage"), r.get("confidence"), r.get("source"))
                for r in edited_pct
            )
            pct_first_load = st.session_state.get("_pct_fee_last_applied_editor_sig") is None
            pct_pending = pct_raw_sig != st.session_state.get("_pct_fee_last_applied_editor_sig")
            pct_tick_val = st.session_state.get("_pct_fee_apply_tick", False)
            pct_tick_seen = st.session_state.get("_pct_fee_apply_tick_seen", False)
            if pct_pending and pct_tick_val and pct_tick_seen:
                st.session_state["_pct_fee_apply_tick"] = False
            pct_apply_now = st.checkbox(
                "Done entering data -- refresh totals & chart",
                key="_pct_fee_apply_tick",
            )
            st.session_state["_pct_fee_apply_tick_seen"] = pct_apply_now

            if pct_first_load or (pct_apply_now and pct_pending):
                st.session_state.fee_estimates = [
                    fee_estimation_engine.DisciplineFeeEstimate(
                        discipline=r["discipline"], fee_percentage=float(r["fee_percentage"] or 0),
                        confidence=r["confidence"] or "", source=r["source"] or "",
                    )
                    for r in edited_pct
                ]
                st.session_state._pct_fee_last_applied_editor_sig = pct_raw_sig
            else:
                st.caption(
                    "Totals, the chart, and the Excel export below are from the last time "
                    "you ticked the box above -- tick it again to bring them up to date."
                    if pct_pending else
                    "Totals, the chart, and the Excel export below reflect the ticked data above."
                )

            pct_total = sum(e.fee_percentage for e in st.session_state.fee_estimates)
            st.caption(f"Total: {pct_total:.1f}% (doesn't need to sum to exactly 100%).")

            _fee_pct_indicative_amounts = {e.discipline: _indicative_amount(e.fee_percentage) for e in st.session_state.fee_estimates}
            pct_xlsx = fee_estimation_engine.fee_estimates_to_excel(
                st.session_state.fee_estimates,
                indicative_amounts=_fee_pct_indicative_amounts,
                theme_name=st.session_state.proposal_theme,
                project_info=_project_info(),
            )
            if pct_xlsx:
                st.download_button(
                    "Export to Excel", data=pct_xlsx, key="download_pct_fee_xlsx",
                    file_name="indicative_fee_split.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 type="primary")
            else:
                st.caption("Excel export isn't available right now -- please email hello@civilproposals.com if this keeps happening.")

            # Chart the $ split once a total (manual or build-up) is available (matches
            # the other pie's units); otherwise chart the raw percentages, since that's
            # the only figure available with no total to anchor to.
            if any(_fee_pct_indicative_amounts.values()):
                pct_pie_items = [(e.discipline, _fee_pct_indicative_amounts.get(e.discipline) or 0) for e in st.session_state.fee_estimates]
                pct_pie_fmt = lambda v: f"${v:,.0f}"
                pct_pie_legend_value = "raw"
            else:
                pct_pie_items = [(e.discipline, e.fee_percentage) for e in st.session_state.fee_estimates]
                pct_pie_fmt = lambda v: f"{v:.0f}%"
                # "share" (not "raw"): if disciplines beyond the top 6 get folded into
                # "Other", the chart's total shrinks below 100 -- showing each slice's
                # recomputed share keeps the legend number matching what's actually
                # drawn, instead of the un-renormalised percentage.
                pct_pie_legend_value = "share"
            pct_pie_png = graphics_engine.generate_fee_distribution_pie(
                pct_pie_items, "Indicative fee split by discipline", value_fmt=pct_pie_fmt,
                legend_value=pct_pie_legend_value,
            )
            if pct_pie_png:
                st.image(pct_pie_png, use_container_width=True)

        _render_large_pct_fee_table()



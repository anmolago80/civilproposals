# modules/pages/60_team.py -- one segment of the CivilProposals app script.
# Tab 8 Team & Resourcing.
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
# Tab 8: Team & Resourcing
# ---------------------------------------------------------------------------

with tabs[7]:
    st.subheader(i18n.t("team_subheader"))
    st.caption(i18n.t("team_caption"))

    if st.session_state.analysis is None:
        st.info(i18n.t("team_run_analysis_first_info"))
    else:
        for _k in ("resource_extra_names", "cv_library_filenames", "cv_extracted_names", "dismissed_disciplines"):
            if st.session_state.get(_k) is None:
                st.session_state[_k] = []

        brief_disciplines = st.session_state.analysis.disciplines_involved or []
        # Project Management is deliberately excluded here -- it's staffed by the
        # Project Manager management role above, not a separate discipline lead.
        # (It still gets its own line in the fee estimate tab.)
        required = resourcing.resourcing_disciplines(brief_disciplines)
        dismissed = {d.lower() for d in st.session_state.dismissed_disciplines}

        # Coerce None -> [] for projects saved before this feature existed (those
        # load these keys back as None under the "not run yet" convention).
        if not st.session_state.resource_plan:
            st.session_state.resource_plan = resourcing.build_resource_plan(
                brief_disciplines, st.session_state.removed_management_roles)
        else:
            # Drop any Project Management discipline-lead row left over from a
            # project saved before this was de-duplicated against the Project
            # Manager management role.
            st.session_state.resource_plan = [
                a for a in st.session_state.resource_plan
                if not (a.slot_kind == "discipline" and resourcing.canonical_discipline(a.slot) == resourcing.ALWAYS_INCLUDED_DISCIPLINE)
            ]
            # Add any newly-detected disciplines without wiping existing assignments --
            # but never re-add a discipline the user has explicitly removed.
            existing_disc_slots = {a.slot for a in st.session_state.resource_plan if a.slot_kind == "discipline"}
            for disc in required:
                if disc not in existing_disc_slots and disc.lower() not in dismissed:
                    st.session_state.resource_plan.append(
                        resourcing.ResourceAssignment(slot=disc, slot_kind="discipline", is_lead=True)
                    )
        # Merge any duplicate/variant disciplines (e.g. two 'Structural ...' rows).
        st.session_state.resource_plan = resourcing.normalize_plan_disciplines(st.session_state.resource_plan)

        # The dropdown name pool, from every available source: names extracted from
        # the CV text by AI, names inferred from CV filenames, any bios already
        # drafted, and anyone typed in manually. All merged and de-duplicated.
        filename_names = resourcing.names_from_filenames(st.session_state.cv_library_filenames)
        known_names = resourcing.cv_derived_names(
            st.session_state.team_members,
            list(st.session_state.cv_extracted_names) + filename_names + list(st.session_state.resource_extra_names),
        )

        # Pull accurate names straight from the CV library text (AI).
        cv_text = st.session_state.company_material_text.get("cv_library", "")
        ai_ready = bool(st.session_state.ai_config.get("api_key")) and bool(cv_text.strip()) and _current_project_already_paid()
        ncol1, ncol2 = st.columns([2, 3])
        with ncol1:
            if st.button(i18n.t("team_load_names_button"), disabled=not ai_ready,
                         help=None if ai_ready else (
                             _ai_block_reason() if not _current_project_already_paid()
                             else i18n.t("team_load_names_help", ai_hint=_AI_HINT_CLAUSE)
                         ), type="primary"):
                with st.spinner(i18n.t("team_spinner_load_names")):
                    try:
                        _record_ai_click()
                        names, warns = team_bios.extract_person_names(cv_text, st.session_state.ai_config)
                        st.session_state.cv_extracted_names = resourcing.dedupe_names(names)
                        if st.session_state.cv_extracted_names:
                            st.success(i18n.t("team_names_found_success", n=len(st.session_state.cv_extracted_names), names=", ".join(st.session_state.cv_extracted_names)))
                        for w in warns:
                            st.warning(w)
                    except Exception as exc:
                        _show_error(i18n.t("team_load_names_error"), exc)
                st.rerun()
        with ncol2:
            if known_names:
                st.caption(i18n.t("team_available_names_caption", names=", ".join(known_names)))
            else:
                st.caption(i18n.t("team_no_names_caption"))

        # The most reliable name source is the CV filenames (one file = one
        # person). A project loaded from an older save won't have them, so nudge
        # the user to re-upload the CV library for instant, complete names.
        if cv_text.strip() and not st.session_state.cv_library_filenames:
            st.caption(i18n.t("team_reupload_cv_tip_caption"))

        st.markdown(i18n.t("team_management_roles_heading"))
        st.caption(i18n.t("team_management_roles_caption"))
        _render_resource_rows("management", known_names)

        # Only offered while the role is actually gone, mirroring how a removed
        # discipline is re-added. Adding it back also clears the removal record,
        # so the reconcile pass stops suppressing it.
        _mgmt_slots = {a.slot for a in st.session_state.resource_plan if a.slot_kind == "management"}
        for _optional_role in sorted(resourcing.OPTIONAL_MANAGEMENT_ROLES):
            if _optional_role in _mgmt_slots:
                continue
            _acol1, _acol2 = st.columns([2, 3])
            with _acol1:
                if st.button(i18n.t("team_add_role_button", role=_optional_role), key=f"_add_mgmt_{_optional_role}",
                             type="primary"):
                    st.session_state.removed_management_roles = [
                        r for r in st.session_state.removed_management_roles if r != _optional_role
                    ]
                    # Slotted back into its proper place in the chain rather
                    # than appended, so the chart and the pen-pic order stay in
                    # resourcing.MANDATORY_ORG_ROLES order.
                    st.session_state.resource_plan.insert(
                        _management_insert_index(st.session_state.resource_plan, _optional_role),
                        resourcing.ResourceAssignment(
                            slot=_optional_role, slot_kind="management", is_lead=True),
                    )
                    st.rerun()
            with _acol2:
                st.caption(i18n.t("team_role_off_chart_caption", role=_optional_role))

        st.divider()
        st.markdown(i18n.t("team_discipline_leads_heading"))
        st.caption(i18n.t("team_discipline_leads_caption"))
        _render_resource_rows("discipline", known_names)

        # Focused re-scan of the brief for disciplines -- catches ones the main
        # analysis missed and infers those the scope implies (e.g. environmental,
        # constructability, rail) without re-running the whole analysis.
        brief_text = st.session_state.tender_extracted.text if st.session_state.tender_extracted else ""
        rescan_ready = bool(st.session_state.ai_config.get("api_key")) and bool(brief_text.strip()) and _current_project_already_paid()
        rcol1, rcol2 = st.columns([2, 3])
        with rcol1:
            if st.button(i18n.t("team_rescan_button"), disabled=not rescan_ready,
                         help=None if rescan_ready else (
                             _ai_block_reason() if not _current_project_already_paid()
                             else i18n.t("team_rescan_help", ai_hint=_AI_HINT_CLAUSE)
                         ), type="primary"):
                with st.spinner(i18n.t("team_spinner_rescan")):
                    try:
                        _record_ai_click()
                        detected, _detect_warnings = tender_analyser.detect_disciplines_from_text(
                            brief_text, st.session_state.ai_config,
                        )
                        for _warning in _detect_warnings:
                            st.warning(_warning)
                        existing = {a.slot for a in st.session_state.resource_plan if a.slot_kind == "discipline"}
                        dismissed_now = {d.lower() for d in st.session_state.dismissed_disciplines}
                        added = []
                        for d in detected:
                            label = resourcing.canonical_discipline(d)
                            # Project Management is never added here -- it's staffed by
                            # the Project Manager management role, not a discipline lead.
                            if (label and label != resourcing.ALWAYS_INCLUDED_DISCIPLINE
                                    and label not in existing and label.lower() not in dismissed_now):
                                st.session_state.resource_plan.append(
                                    resourcing.ResourceAssignment(slot=label, slot_kind="discipline", is_lead=True)
                                )
                                existing.add(label)
                                added.append(label)
                        st.session_state.resource_plan = resourcing.normalize_plan_disciplines(st.session_state.resource_plan)
                        if added:
                            st.success(i18n.t("team_disciplines_added_success", names=", ".join(added)))
                        elif _detect_warnings:
                            # Don't claim "nothing found" when the scan didn't
                            # actually complete -- see the warnings above.
                            pass
                        else:
                            st.info(i18n.t("team_no_new_disciplines_info"))
                    except Exception as exc:
                        _show_error(i18n.t("team_rescan_failed_error"), exc)
                st.rerun()
        with rcol2:
            st.caption(i18n.t("team_rescan_caption"))

        with st.form("add_discipline_resource_form", clear_on_submit=True):
            acol1, acol2 = st.columns([3, 1])
            with acol1:
                new_disc = st.text_input(i18n.t("team_add_discipline_label"), placeholder=i18n.t("team_add_discipline_placeholder"))
            with acol2:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.form_submit_button(i18n.t("team_add_discipline_button"), type="primary") and new_disc.strip():
                    label = resourcing.canonical_discipline(new_disc.strip())
                    if label == resourcing.ALWAYS_INCLUDED_DISCIPLINE:
                        st.warning(i18n.t("team_pm_not_separate_warning"))
                    else:
                        # Un-dismiss if it was previously removed, so re-adding sticks.
                        st.session_state.dismissed_disciplines = [
                            d for d in st.session_state.dismissed_disciplines if d.lower() != label.lower()
                        ]
                        if label not in {a.slot for a in st.session_state.resource_plan if a.slot_kind == "discipline"}:
                            st.session_state.resource_plan.append(
                                resourcing.ResourceAssignment(slot=label, slot_kind="discipline", is_lead=True)
                            )
                    st.rerun()

        st.divider()
        st.markdown(i18n.t("team_add_no_cv_heading"))
        st.caption(i18n.t("team_add_no_cv_caption"))
        with st.form("add_extra_name_form", clear_on_submit=True):
            ncol1, ncol2 = st.columns([3, 1])
            with ncol1:
                extra_name = st.text_input(i18n.t("team_person_name_label"), label_visibility="collapsed", placeholder=i18n.t("team_person_name_placeholder"))
            with ncol2:
                if st.form_submit_button(i18n.t("team_add_name_button"), type="primary") and extra_name.strip():
                    if extra_name.strip() not in st.session_state.resource_extra_names:
                        st.session_state.resource_extra_names.append(extra_name.strip())
                    st.rerun()

        st.divider()
        st.markdown(i18n.t("team_key_personnel_heading"))
        st.caption(i18n.t("team_key_personnel_caption"))
        # One entry per unique person (roles merged) -- so someone leading two disciplines
        # gets a single profile/editor, not duplicates. Matches the deduped export exactly.
        _profile_entries = resourcing.personnel_profiles_deduped(st.session_state.resource_plan)
        _assigned_profile_names = [e["name"] for e in _profile_entries if e["name"]]
        _profile_fill_ready = (
            bool(st.session_state.ai_config.get("api_key")) and bool(cv_text.strip())
            and bool(_assigned_profile_names) and _current_project_already_paid()
        )
        _overwrite_profiles = st.checkbox(
            i18n.t("team_overwrite_checkbox_label"),
            value=False, key="_profile_fill_overwrite",
            help=i18n.t("team_overwrite_checkbox_help"),
        )
        pfcol1, pfcol2 = st.columns([2, 3])
        with pfcol1:
            if st.button(
                i18n.t("team_fill_profile_button"), disabled=not _profile_fill_ready,
                help=None if _profile_fill_ready else (
                    _ai_block_reason() if not _current_project_already_paid()
                    else i18n.t("team_fill_profile_help", ai_hint=_AI_HINT_CLAUSE)
                ),
             type="primary"):
                with st.spinner(i18n.t("team_spinner_fill_profile")):
                    try:
                        _record_ai_click()
                        cv_profiles, warns = team_bios.extract_personnel_profile_fields(
                            cv_text, _assigned_profile_names, st.session_state.ai_config,
                            cv_files=st.session_state.company_material_files.get("cv_library"),
                            # Emphasis context only -- the "on this project, X
                            # will..." line was written with no description of
                            # the project at all, so it could only be generic.
                            analysis=st.session_state.analysis,
                        )
                        filled = []
                        for entry in _profile_entries:
                            a = entry["assignment"]  # write to the person's primary slot
                            key = (entry.get("name") or "").strip().lower()
                            if not key or key not in cv_profiles:
                                continue
                            found = cv_profiles[key]
                            changed = False
                            # The Details expander below renders each field via a keyed
                            # st.text_input/st.text_area (e.g. key=f"prof_qual_{ekey}"). Once a
                            # widget with a given key has rendered once, Streamlit ignores any
                            # future `value=` we pass it and keeps showing its own cached
                            # session_state entry -- so writing straight to `a.field` here is
                            # not enough; the widget's cached copy must be updated too, or the
                            # next rerun (the widget line itself does `a.field = st.text_input(
                            # ..., value=a.field, key=...)`) silently overwrites our fresh value
                            # back to the stale one before the user ever sees it.
                            ekey = (entry.get("name") or "").strip() or a.slot
                            # Default: only fill a blank field (protects the user's own typing).
                            # Overwrite mode: replace the field whenever the CV yielded a value,
                            # so a wrong value left over from an earlier run can be corrected.
                            for field, widget_key in (
                                ("qualification", f"prof_qual_{ekey}"),
                                ("rpeq_status", f"prof_rpeq_{ekey}"),
                                ("years_experience", f"prof_years_{ekey}"),
                                ("value_to_project", f"prof_value_{ekey}"),
                            ):
                                found_val = (found.get(field) or "").strip()
                                cur_val = (getattr(a, field) or "").strip()
                                if found_val and (_overwrite_profiles or not cur_val) and found_val != cur_val:
                                    setattr(a, field, found_val)
                                    st.session_state[widget_key] = found_val
                                    changed = True
                            found_projects = [str(p).strip() for p in (found.get("relevant_projects") or []) if str(p).strip()]
                            cur_projects = getattr(a, "relevant_projects", None) or []
                            if found_projects and (_overwrite_profiles or not cur_projects) and found_projects != cur_projects:
                                a.relevant_projects = found_projects
                                st.session_state[f"prof_relproj_{ekey}"] = "\n".join(found_projects)
                                changed = True
                            if changed:
                                filled.append(entry["name"])
                        if filled:
                            verb = i18n.t("team_verb_updated") if _overwrite_profiles else i18n.t("team_verb_filled")
                            st.success(i18n.t("team_profile_filled_success", verb=verb, names=", ".join(filled)))
                        elif _overwrite_profiles:
                            st.info(i18n.t("team_profile_none_overwrite_info"))
                        else:
                            st.info(i18n.t("team_profile_none_info"))
                        for w in warns:
                            st.warning(w)
                    except Exception as exc:
                        _show_error(i18n.t("team_fill_profile_error"), exc)
                st.rerun()
        with pfcol2:
            st.caption(i18n.t("team_fill_profile_caption"))

        st.markdown("---")
        st.caption(i18n.t("team_include_caption"))
        _suggest_ready = (
            bool(st.session_state.ai_config.get("api_key")) and bool(st.session_state.resource_plan)
            and _current_project_already_paid()
        )
        if st.button(
            i18n.t("team_suggest_button"), disabled=not _suggest_ready,
            help=None if _suggest_ready else (
                _ai_block_reason() if not _current_project_already_paid()
                else i18n.t("team_suggest_help", ai_hint=_AI_HINT_CLAUSE)
            ),
         type="primary"):
            with st.spinner(i18n.t("team_spinner_suggest")):
                try:
                    _record_ai_click()
                    suggestions = resourcing.suggest_proposal_inclusion(
                        st.session_state.resource_plan, st.session_state.analysis, st.session_state.ai_config,
                        output_language=st.session_state.get("output_language", "en"),
                    )
                    st.session_state.personnel_inclusion_suggestions = suggestions
                    # Apply the recommendation to each MERGED profile's tick, keyed on the
                    # primary assignment's own slot (the same "a" the checkbox below reads/
                    # writes for a deduped person) -- not every raw plan row, since someone
                    # holding two slots would otherwise get two different verdicts fighting
                    # over the one checkbox they actually see. Same widget-caching gotcha as
                    # "Fill profile fields from CVs" above: also write the checkbox's own
                    # session_state key, since a widget that's already rendered once ignores a
                    # fresh `value=` and keeps showing its cached copy otherwise.
                    for entry in _profile_entries:
                        a = entry["assignment"]
                        verdict = suggestions.get(a.slot)
                        if verdict is None:
                            continue
                        a.include_in_proposal = bool(verdict["recommended"])
                        person_label = (entry.get("name") or "").strip() or "[unassigned]"
                        ekey_for_entry = person_label if entry.get("name") else a.slot
                        st.session_state[f"prof_include_{ekey_for_entry}"] = a.include_in_proposal
                    st.success(i18n.t("team_suggest_applied_success"))
                except Exception as exc:
                    _show_error(i18n.t("team_suggest_error"), exc)
            st.rerun()

        for entry in _profile_entries:
            a = entry["assignment"]  # profile fields are read/written on the primary slot
            person_label = (entry.get("name") or "").strip() or "[unassigned]"
            role_label = ", ".join(entry.get("roles") or [])
            # A stable per-entry key: the person's name if assigned (so one editor per
            # person even across multiple roles), else the slot for an unassigned row.
            ekey = person_label if entry.get("name") else a.slot
            name = (entry.get("name") or "").strip()

            # A header row shown ABOVE the expander (not inside it), with a per-person
            # "Refresh from CV" button next to the name -- this is deliberately outside
            # the collapsed expander so a person whose pen pic came out empty can be
            # re-read from their own CV file in one click, without opening every row or
            # re-running "Fill profile fields from CVs" for everyone else. Re-uses the
            # same single-person, per-file matching path as that batch button (see
            # team_bios.extract_personnel_profile_fields), just scoped to one name, and
            # always overwrites -- an explicit refresh click means the current values
            # (if any) are what the user is trying to fix.
            # Result of the last "Refresh from CV" click, if any, stashed in
            # session_state so it survives the st.rerun() below. A message shown
            # via st.success/warning/error and then immediately followed by
            # st.rerun() only flashes for an instant in Streamlit -- the rerun
            # starts a brand-new script execution before the person has a chance
            # to read it, which looks exactly like "nothing happened" even when
            # the click worked (or failed) correctly. Stashing it and rendering
            # it on the NEXT run (then clearing it) makes the outcome durable.
            result_key = f"prof_refresh_result_{ekey}"

            hcol1, hcol_tick, hcol2 = st.columns([4, 1.5, 1.3])
            with hcol1:
                st.markdown(f"**{role_label} -- {person_label}**")
            with hcol_tick:
                a.include_in_proposal = st.checkbox(
                    i18n.t("team_include_checkbox_label"), value=a.include_in_proposal, key=f"prof_include_{ekey}",
                )
            with hcol2:
                refresh_ready = (
                    bool(st.session_state.ai_config.get("api_key")) and bool(name)
                    and bool(cv_text.strip()) and _current_project_already_paid()
                )
                if st.button(
                    i18n.t("team_refresh_button"), key=f"prof_refresh_{ekey}", disabled=not refresh_ready,
                    help=None if refresh_ready else (
                        _ai_block_reason() if not _current_project_already_paid()
                        else i18n.t("team_refresh_help", ai_hint=_AI_HINT_CLAUSE)
                    ),
                 type="primary"):
                    messages = []  # [(level, text), ...] -- rendered after the rerun, see result_key above
                    with st.spinner(i18n.t("team_spinner_refresh", name=name)):
                        try:
                            _record_ai_click()
                            cv_profiles, warns = team_bios.extract_personnel_profile_fields(
                                cv_text, [name], st.session_state.ai_config,
                                cv_files=st.session_state.company_material_files.get("cv_library"),
                                analysis=st.session_state.analysis,
                            )
                            found = cv_profiles.get(name.lower())
                            changed = False
                            if found:
                                # As below in the batch "Fill profile fields from CVs" handler:
                                # the Details expander's widgets (key=f"prof_qual_{ekey}" etc.)
                                # cache their own value once rendered, so setting `a.field` alone
                                # gets silently overwritten back to the stale widget value on the
                                # very next rerun unless we also update session_state for that
                                # widget's exact key here.
                                for field, widget_key in (
                                    ("qualification", f"prof_qual_{ekey}"),
                                    ("rpeq_status", f"prof_rpeq_{ekey}"),
                                    ("years_experience", f"prof_years_{ekey}"),
                                    ("value_to_project", f"prof_value_{ekey}"),
                                ):
                                    val = (found.get(field) or "").strip()
                                    if val:
                                        setattr(a, field, val)
                                        st.session_state[widget_key] = val
                                        changed = True
                                found_projects = [str(p).strip() for p in (found.get("relevant_projects") or []) if str(p).strip()]
                                if found_projects:
                                    a.relevant_projects = found_projects
                                    st.session_state[f"prof_relproj_{ekey}"] = "\n".join(found_projects)
                                    changed = True
                            if changed:
                                messages.append(("success", i18n.t("team_refresh_success", name=name)))
                            elif found is not None:
                                # Matched to a CV file, AI call succeeded, but every field came back
                                # empty -- almost always means the CV TEXT on file for this person is
                                # thin/stale (e.g. it was uploaded and extracted before a recent fix to
                                # how CVs are read, so what's cached here is mostly empty template
                                # boilerplate), not that the button failed. Re-uploading their CV in
                                # tab 2 re-extracts it with the current logic and fixes this.
                                messages.append((
                                    "warning",
                                    i18n.t("team_refresh_thin_warning", name=name),
                                ))
                            else:
                                messages.append((
                                    "warning",
                                    i18n.t("team_refresh_not_found_warning", name=name),
                                ))
                            for w in warns:
                                messages.append(("warning", w))
                        except Exception as exc:
                            # Can't use _show_error() here -- its st.error() call
                            # would only flash for an instant before the
                            # st.rerun() below wipes it (see this block's
                            # comment on `messages`/result_key), so the
                            # friendly-message-plus-stderr-log split is done by
                            # hand instead: log the raw exception server-side,
                            # queue only the friendly text for the next run.
                            print(f"[Refresh from CV] {exc}", file=sys.stderr)
                            messages.append((
                                "error",
                                i18n.t("team_refresh_error", name=name),
                            ))
                    st.session_state[result_key] = messages
                    st.rerun()

            pending_messages = st.session_state.pop(result_key, None)
            if pending_messages:
                for level, text in pending_messages:
                    getattr(st, level)(text)

            # The reason behind the current tick -- fixed for the firm's three
            # leadership roles (no scope judgement needed there), or from the last
            # "Suggest which personnel to include" run for a discipline lead. Shown
            # even if the user has since overridden the tick by hand, so they can see
            # what the recommendation was.
            if a.slot in resourcing.FIRM_MANAGEMENT_ROLES:
                st.caption(i18n.t("team_ai_note_prefix", reason=resourcing.firm_leadership_reason(
                    st.session_state.get("output_language", "en"))))
            else:
                _verdict = st.session_state.personnel_inclusion_suggestions.get(a.slot)
                if _verdict:
                    _stance = i18n.t("team_stance_recommended") if _verdict.get("recommended") else i18n.t("team_stance_not_essential")
                    st.caption(i18n.t("team_ai_note_stance_prefix", stance=_stance, reason=_verdict.get('reason', '')))

            with st.expander(i18n.t("team_details_expander"), expanded=False):
                if not (entry.get("name") or "").strip():
                    st.caption(i18n.t("team_assign_name_first_caption"))
                a.qualification = st.text_input(i18n.t("team_qualification_label"), value=a.qualification, key=f"prof_qual_{ekey}")
                a.rpeq_status = st.text_input(i18n.t("team_rpeq_label"), value=a.rpeq_status, key=f"prof_rpeq_{ekey}")
                a.years_experience = st.text_input(i18n.t("team_years_experience_label"), value=a.years_experience, key=f"prof_years_{ekey}")
                a.value_to_project = st.text_area(
                    i18n.t("team_value_to_project_label", person=person_label), value=a.value_to_project,
                    key=f"prof_value_{ekey}", height=70,
                )
                relevant_projects_text = st.text_area(
                    i18n.t("team_relevant_projects_label"),
                    value="\n".join(a.relevant_projects), key=f"prof_relproj_{ekey}", height=70,
                )
                a.relevant_projects = [line.strip() for line in relevant_projects_text.splitlines() if line.strip()]
                local_exp_text = st.text_area(
                    i18n.t("team_local_experience_label"),
                    value="\n".join(a.local_experience), key=f"prof_local_{ekey}", height=70,
                )
                a.local_experience = [line.strip() for line in local_exp_text.splitlines() if line.strip()]
                photo = st.file_uploader(
                    i18n.t("team_headshot_label"), type=["png", "jpg", "jpeg"], key=f"prof_photo_{ekey}",
                    disabled=not (entry.get("name") or "").strip(),
                )
                if photo is not None and (entry.get("name") or "").strip():
                    st.session_state.personnel_photos[
                        photo_key_for(entry.get("assignment"), entry["name"])
                    ] = photo.getvalue()
                existing_profile_photo = st.session_state.personnel_photos.get(
                    photo_key_for(entry.get("assignment"), entry.get("name") or "")
                )
                if existing_profile_photo:
                    st.image(existing_profile_photo, width=120)

        st.divider()
        st.markdown(i18n.t("team_org_chart_heading"))
        _assigned = sum(1 for a in st.session_state.resource_plan if (a.person_name or "").strip())
        st.caption(i18n.t("team_org_chart_caption", assigned=_assigned, total=len(st.session_state.resource_plan)))
        _org_chart_style_control()

        _org_preview = _org_png(st.session_state.org_chart_style)
        if _org_preview:
            st.image(_org_preview, use_container_width=True)
        else:
            st.caption(i18n.t("team_chart_render_failed_caption"))

        # The preview is live; putting it INTO the pack stays an explicit act,
        # so a stray click on a style never silently rewrites what an already
        # generated pack contains.
        _ocol1, _ocol2 = st.columns([2, 3])
        with _ocol1:
            if st.button(i18n.t("team_use_chart_button"), type="primary",
                         disabled=_org_preview is None):
                st.session_state.org_chart_png = _org_preview
                st.session_state.org_chart_png_style = st.session_state.org_chart_style
                st.success(i18n.t("team_chart_saved_success"))
        with _ocol2:
            if not st.session_state.org_chart_png:
                st.caption(i18n.t("team_chart_none_caption"))
            elif st.session_state.org_chart_png_style != st.session_state.org_chart_style:
                st.warning(i18n.t(
                    "team_chart_stale_warning",
                    style=org_chart_render.STYLE_LABELS.get(st.session_state.org_chart_png_style, 'previous'),
                ))
            else:
                st.caption(i18n.t("team_chart_current_caption"))



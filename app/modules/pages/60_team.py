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
    st.subheader("Team & Resourcing")
    st.caption(
        "Identify who staffs each discipline the brief calls for, plus the standing "
        "management roles every job carries, then generate a project org chart for the "
        "Key Personnel section. Names come from your uploaded CV library where possible, "
        "but you can also type in anyone you haven't uploaded a CV for."
    )

    if st.session_state.analysis is None:
        st.info("Run the Tender Analysis first -- the required disciplines come from the brief.")
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
            st.session_state.resource_plan = resourcing.build_resource_plan(brief_disciplines)
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
            if st.button("Load names from CV library", disabled=not ai_ready,
                         help=None if ai_ready else (
                             _PROJECT_NOT_PAID_HINT if not _current_project_already_paid()
                             else f"Upload a CV library (Upload Docs) and {_AI_HINT_CLAUSE}."
                         ), type="primary"):
                with st.spinner("Reading the whole CV library for names (a few seconds per batch)..."):
                    try:
                        names, warns = team_bios.extract_person_names(cv_text, st.session_state.ai_config)
                        st.session_state.cv_extracted_names = resourcing.dedupe_names(names)
                        if st.session_state.cv_extracted_names:
                            st.success(f"Found {len(st.session_state.cv_extracted_names)} name(s): " + ", ".join(st.session_state.cv_extracted_names))
                        for w in warns:
                            st.warning(w)
                    except Exception as exc:
                        _show_error("Could not read names from the CV library", exc)
                st.rerun()
        with ncol2:
            if known_names:
                st.caption("Available names: " + ", ".join(known_names))
            else:
                st.caption("No names yet -- click 'Load names from CV library', or add people manually below.")

        # The most reliable name source is the CV filenames (one file = one
        # person). A project loaded from an older save won't have them, so nudge
        # the user to re-upload the CV library for instant, complete names.
        if cv_text.strip() and not st.session_state.cv_library_filenames:
            st.caption(
                "💡 Tip: for the most complete and accurate list, re-upload your CV library files "
                "in Upload Docs -- each filename gives one person's full name instantly, "
                "with no AI guesswork. (Your loaded project kept the CV text but not the filenames.)"
            )

        st.markdown("#### Management roles")
        st.caption("Always present on the chart: the client's PM at the top, then your Project Director, Project Manager and Design Manager.")
        _render_resource_rows("management", known_names)

        st.divider()
        st.markdown("#### Discipline leads")
        st.caption(
            "One per discipline the brief requires. Add or remove disciplines as needed. "
            "Project Management isn't listed here -- it's staffed by the Project Manager role "
            "above -- but it still gets its own line in the fee estimate tab."
        )
        _render_resource_rows("discipline", known_names)

        # Focused re-scan of the brief for disciplines -- catches ones the main
        # analysis missed and infers those the scope implies (e.g. environmental,
        # constructability, rail) without re-running the whole analysis.
        brief_text = st.session_state.tender_extracted.text if st.session_state.tender_extracted else ""
        rescan_ready = bool(st.session_state.ai_config.get("api_key")) and bool(brief_text.strip()) and _current_project_already_paid()
        rcol1, rcol2 = st.columns([2, 3])
        with rcol1:
            if st.button("Re-scan brief for disciplines", disabled=not rescan_ready,
                         help=None if rescan_ready else (
                             _PROJECT_NOT_PAID_HINT if not _current_project_already_paid()
                             else f"Needs the tender brief (Upload Docs) and {_AI_HINT_CLAUSE}."
                         ), type="primary"):
                with st.spinner("Re-reading the brief for every discipline the scope implies..."):
                    try:
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
                            st.success("Added: " + ", ".join(added))
                        elif _detect_warnings:
                            # Don't claim "nothing found" when the scan didn't
                            # actually complete -- see the warnings above.
                            pass
                        else:
                            st.info("No new disciplines found beyond what's already listed.")
                    except Exception as exc:
                        _show_error("Discipline re-scan failed", exc)
                st.rerun()
        with rcol2:
            st.caption("Reads the brief and infers disciplines the scope implies (environmental, constructability, rail, survey, etc.), even if they weren't named explicitly.")

        with st.form("add_discipline_resource_form", clear_on_submit=True):
            acol1, acol2 = st.columns([3, 1])
            with acol1:
                new_disc = st.text_input("Add a discipline", placeholder="e.g. Landscaping, Surveying, Constructability")
            with acol2:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.form_submit_button("Add discipline", type="primary") and new_disc.strip():
                    label = resourcing.canonical_discipline(new_disc.strip())
                    if label == resourcing.ALWAYS_INCLUDED_DISCIPLINE:
                        st.warning(
                            "Project Management is staffed by the Project Manager role above, "
                            "not added here as a separate discipline. It still has its own line "
                            "in the fee estimate tab."
                        )
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
        st.markdown("#### Add someone without a CV")
        st.caption("Names you type here become available in every dropdown above -- for people you want on the chart who don't have a CV uploaded.")
        with st.form("add_extra_name_form", clear_on_submit=True):
            ncol1, ncol2 = st.columns([3, 1])
            with ncol1:
                extra_name = st.text_input("Person's name", label_visibility="collapsed", placeholder="e.g. Jordan Lee")
            with ncol2:
                if st.form_submit_button("Add name", type="primary") and extra_name.strip():
                    if extra_name.strip() not in st.session_state.resource_extra_names:
                        st.session_state.resource_extra_names.append(extra_name.strip())
                    st.rerun()

        st.divider()
        st.markdown("#### Key personnel profile details")
        st.caption(
            "Feeds the numbered Key Personnel profiles in the exported pack -- Project Director, "
            "Project Manager, Design Manager, then discipline leads, in that order. Everything here "
            "is optional, user-entered text (never guessed): leave a field blank and the export "
            "shows a clearly marked placeholder instead."
        )
        # One entry per unique person (roles merged) -- so someone leading two disciplines
        # gets a single profile/editor, not duplicates. Matches the deduped export exactly.
        _profile_entries = resourcing.personnel_profiles_deduped(st.session_state.resource_plan)
        _assigned_profile_names = [e["name"] for e in _profile_entries if e["name"]]
        _profile_fill_ready = (
            bool(st.session_state.ai_config.get("api_key")) and bool(cv_text.strip())
            and bool(_assigned_profile_names) and _current_project_already_paid()
        )
        _overwrite_profiles = st.checkbox(
            "Overwrite existing values (re-read from CVs, replacing what's there)",
            value=False, key="_profile_fill_overwrite",
            help="Off (default): only fills blank fields, protecting anything you've typed. "
                 "On: re-reads every assigned person's CV and replaces the current values -- "
                 "use this to fix wrong details left over from an earlier run.",
        )
        pfcol1, pfcol2 = st.columns([2, 3])
        with pfcol1:
            if st.button(
                "Fill profile fields from CVs", disabled=not _profile_fill_ready,
                help=None if _profile_fill_ready else (
                    _PROJECT_NOT_PAID_HINT if not _current_project_already_paid()
                    else f"Assign people to roles above, upload a CV library (Upload Docs), and {_AI_HINT_CLAUSE}."
                ),
             type="primary"):
                with st.spinner("Reading each person's CV for registration status, experience and relevance (a few seconds per batch)..."):
                    try:
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
                            verb = "Updated" if _overwrite_profiles else "Filled"
                            st.success(f"{verb} profile details for: {', '.join(filled)}. Review before exporting -- fields left blank mean the CV didn't clearly state that fact.")
                        elif _overwrite_profiles:
                            st.info("No profile details found in the CVs to write -- the CVs don't clearly state these facts, or no assigned person could be matched to a CV file.")
                        else:
                            st.info("No new profile details found -- existing entries were left as-is. Tick 'Overwrite existing values' to re-read and replace them.")
                        for w in warns:
                            st.warning(w)
                    except Exception as exc:
                        _show_error("Could not fill profile fields from CVs", exc)
                st.rerun()
        with pfcol2:
            st.caption(
                "Reads each assigned person's own CV file (in isolation, so no one's details get mixed up "
                "with another person's) for their registration/membership status and stated years of "
                "experience, and drafts an \"On this project, [name] will...\" line from their real background."
            )

        st.markdown("---")
        st.caption(
            "**Include in proposal** -- tick which pen pics actually make it into the exported Key "
            "Personnel section. A full photo + write-up profile takes real page space, so when a "
            "page-limited section is full, untick anyone whose profile isn't essential to include -- "
            "they're still on the job (still in the org chart and fee build-up), they just won't get "
            "a dedicated profile. Project Director/Manager/Design Manager are always recommended "
            "(project leadership), every other tick can be pre-set from an AI read of this project's "
            "scope below, and you can always override any tick by hand."
        )
        _suggest_ready = (
            bool(st.session_state.ai_config.get("api_key")) and bool(st.session_state.resource_plan)
            and _current_project_already_paid()
        )
        if st.button(
            "Suggest which personnel to include (AI)", disabled=not _suggest_ready,
            help=None if _suggest_ready else (
                _PROJECT_NOT_PAID_HINT if not _current_project_already_paid()
                else f"Assign roles above and {_AI_HINT_CLAUSE}."
            ),
         type="primary"):
            with st.spinner("Reading this project's scope to judge which discipline profiles are worth including..."):
                try:
                    suggestions = resourcing.suggest_proposal_inclusion(
                        st.session_state.resource_plan, st.session_state.analysis, st.session_state.ai_config,
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
                    st.success("Recommendations applied -- review the ticks and reasons below, then adjust by hand as needed.")
                except Exception as exc:
                    _show_error("Could not get AI recommendations", exc)
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
                    "Include in proposal", value=a.include_in_proposal, key=f"prof_include_{ekey}",
                )
            with hcol2:
                refresh_ready = (
                    bool(st.session_state.ai_config.get("api_key")) and bool(name)
                    and bool(cv_text.strip()) and _current_project_already_paid()
                )
                if st.button(
                    "Refresh from CV", key=f"prof_refresh_{ekey}", disabled=not refresh_ready,
                    help=None if refresh_ready else (
                        _PROJECT_NOT_PAID_HINT if not _current_project_already_paid()
                        else f"Assign a name, upload a CV library (Upload Docs), and {_AI_HINT_CLAUSE}."
                    ),
                 type="primary"):
                    messages = []  # [(level, text), ...] -- rendered after the rerun, see result_key above
                    with st.spinner(f"Re-reading {name}'s CV..."):
                        try:
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
                                messages.append(("success", f"Refreshed {name} from their own CV file."))
                            elif found is not None:
                                # Matched to a CV file, AI call succeeded, but every field came back
                                # empty -- almost always means the CV TEXT on file for this person is
                                # thin/stale (e.g. it was uploaded and extracted before a recent fix to
                                # how CVs are read, so what's cached here is mostly empty template
                                # boilerplate), not that the button failed. Re-uploading their CV in
                                # tab 2 re-extracts it with the current logic and fixes this.
                                messages.append((
                                    "warning",
                                    f"Read {name}'s CV file but found no details to fill in. This usually means the "
                                    f"text stored for their CV is incomplete (e.g. it was uploaded before a recent "
                                    f"extraction fix) rather than the CV genuinely being empty -- try re-uploading "
                                    f"{name}'s CV file in Upload Docs, then refresh again."
                                ))
                            else:
                                messages.append((
                                    "warning",
                                    f"Couldn't find/re-read {name}'s CV file -- check their filename "
                                    "derives to this exact name, or that their CV is in the library (Upload Docs)."
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
                                f"Could not refresh {name} from their CV -- please try again. If it keeps "
                                "happening, email hello@civilproposals.com and we'll take a look.",
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
                st.caption(f"AI note: {resourcing.FIRM_LEADERSHIP_REASON}")
            else:
                _verdict = st.session_state.personnel_inclusion_suggestions.get(a.slot)
                if _verdict:
                    _stance = "Recommended" if _verdict.get("recommended") else "Not essential"
                    st.caption(f"AI note ({_stance}): {_verdict.get('reason', '')}")

            with st.expander("Details", expanded=False):
                if not (entry.get("name") or "").strip():
                    st.caption("Assign a name to this role above before adding profile details.")
                a.qualification = st.text_input("Qualification", value=a.qualification, key=f"prof_qual_{ekey}")
                a.rpeq_status = st.text_input("RPEQ / registration status", value=a.rpeq_status, key=f"prof_rpeq_{ekey}")
                a.years_experience = st.text_input("Years of experience", value=a.years_experience, key=f"prof_years_{ekey}")
                a.value_to_project = st.text_area(
                    f"On this project, {person_label} will...", value=a.value_to_project,
                    key=f"prof_value_{ekey}", height=70,
                )
                relevant_projects_text = st.text_area(
                    "Relevant project experience (one per line)",
                    value="\n".join(a.relevant_projects), key=f"prof_relproj_{ekey}", height=70,
                )
                a.relevant_projects = [line.strip() for line in relevant_projects_text.splitlines() if line.strip()]
                local_exp_text = st.text_area(
                    "Local district experience (one per line)",
                    value="\n".join(a.local_experience), key=f"prof_local_{ekey}", height=70,
                )
                a.local_experience = [line.strip() for line in local_exp_text.splitlines() if line.strip()]
                photo = st.file_uploader(
                    "Headshot (optional)", type=["png", "jpg", "jpeg"], key=f"prof_photo_{ekey}",
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
        st.markdown("#### Project organisation chart")
        assigned = sum(1 for a in st.session_state.resource_plan if (a.person_name or "").strip())
        st.caption(f"{assigned} of {len(st.session_state.resource_plan)} slots assigned. Unassigned slots show as '[to be assigned]'.")
        if st.button("Generate org chart", type="primary"):
            png = org_chart.render_org_chart(
                st.session_state.resource_plan,
                theme_name=st.session_state.proposal_theme,
                project_title=st.session_state.tender_name or st.session_state.project_name or None,
            )
            st.session_state.org_chart_png = png
            if png:
                st.success("Org chart generated. It will be included in the Key Personnel area of the exported pack.")
            else:
                st.error("Could not render the org chart. Check that at least one role/discipline is present.")
        if st.session_state.org_chart_png:
            st.image(st.session_state.org_chart_png, use_container_width=True)



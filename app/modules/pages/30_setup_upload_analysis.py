# modules/pages/30_setup_upload_analysis.py -- one segment of the CivilProposals app script.
# Tab 1 Project Setup, Tab 2 Upload Documents (incl. tender-package ZIP intake), Tab 3 Tender Analysis.
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
# Tab 1: Project Setup
# ---------------------------------------------------------------------------

with tabs[0]:
    st.subheader("Project Setup")
    st.caption("Basic project details -- used throughout the workflow and on the cover page of the exported pack.")

    st.markdown("**Proposal format**")
    st.caption(
        "The tool is agnostic to what the project actually is -- scope, team, and fees always "
        "come from what you upload, never from the format you pick. This only changes the shape "
        "of the output: a bound Large Scope pack with named sections and page limits, or a "
        "shorter Small Scope pack with the same sections just leaner (typical for a small "
        "brief, or an email-based request from the client)."
    )
    format_label = st.selectbox(
        "Which does this pursuit need?",
        list(PROPOSAL_FORMAT_LABELS.values()),
        index=list(PROPOSAL_FORMAT_LABELS.keys()).index(st.session_state.proposal_format),
        key="proposal_format_select",
    )
    st.session_state.proposal_format = PROPOSAL_FORMAT_KEYS[format_label]

    # Guards against a stale value from an older save/autosave (or the previous
    # project type list) that no longer matches PROJECT_TYPES -- the selectbox
    # below errors if its bound session_state value isn't one of its options.
    if st.session_state.get("project_type") not in PROJECT_TYPES:
        st.session_state.project_type = PROJECT_TYPES[0]

    # Deliberately NOT wrapped in st.form any more. A form doesn't write to
    # session_state until its submit button is pressed, so someone who typed
    # a project name and went straight to Tender Analysis was told "Enter a
    # project name" -- with the name visibly still in the box behind them.
    # That was the single most common first-run trap in the app, and it cost
    # a bid on every occurrence, because nothing about the screen suggested
    # the value hadn't been kept. Field keys are unchanged, so everything
    # reading these keys is unaffected; they now commit as typed.
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Project name", key="project_name")
        st.text_input("Client name", key="client_name")
        st.text_input("Tender / EOI name", key="tender_name")
        st.text_input("Submission date", key="submission_date_input", placeholder="e.g. 14 July 2026")
    with col2:
        st.text_input("Bidder / company name", key="bidder_name")
        st.selectbox("Project type", PROJECT_TYPES, key="project_type")
        st.selectbox("Proposal theme", PROPOSAL_THEMES, key="proposal_theme")
    st.caption("Saved as you type -- there's no separate save step.")

    # The cover page and the brief can disagree about when this is due, and
    # nothing used to say so. The typed date is what gets printed; the
    # extracted one is what the client actually wrote.
    _typed_date = (st.session_state.submission_date_input or "").strip()
    _brief_date = ((getattr(st.session_state.analysis, "submission_date", "") or "").strip()
                   if st.session_state.analysis else "")
    if _typed_date and _brief_date and not _dates_look_equivalent(_typed_date, _brief_date):
        st.warning(
            f"**Submission date mismatch.** You've entered **{_typed_date}**, but the brief's "
            f"own stated date reads **{_brief_date}**. The date you type here is the one "
            f"printed on the cover -- check which is right before exporting."
        )

    def _render_signatory_fields() -> None:
        """The contact/signatory block. Shared by both proposal formats --
        see the two call sites below for why each renders it differently."""
        scol1, scol2 = st.columns(2)
        with scol1:
            st.text_input("Sender name", key="letter_sender_name", placeholder="e.g. Jane Smith")
            st.text_input("Sender title", key="letter_sender_title", placeholder="e.g. Project Director")
        with scol2:
            st.text_input("Sender phone", key="letter_sender_phone")
            st.text_input("Sender email", key="letter_sender_email")
        st.text_input(
            "Registered / business address", key="letter_sender_address",
            placeholder="e.g. Level 3, 100 Example St, Brisbane QLD 4000",
            help="Used to fill the address labels on the client's returnable schedules. "
                 "It is deliberately NOT added to the letter sign-off block, which stays "
                 "name/title/phone/email by design.",
        )

    if _is_letter():
        st.divider()
        st.markdown("#### Sign-off details")
        st.caption(
            "Who signs this pack off -- shown in the closing \"Regards\" block at the end of "
            "the document. The cover page and footer already carry the project/client/bidder "
            "details entered above, so nothing else is needed here. The address is used only "
            "when filling the client's returnable schedules."
        )
        _render_signatory_fields()
    else:
        # Large Scope packs have no sign-off letter, which is why this block
        # used to be hidden entirely for them. But the returnable-schedule
        # filler reads exactly these fields to answer "Contact Person",
        # "Telephone", "Email" and "Registered Office" on the client's own
        # forms -- so a Large Scope user had no way to fill labels the filler
        # was fully capable of filling. Collapsed by default: it is optional
        # here, unlike in a letter pack.
        st.divider()
        with st.expander("Contact / signatory details (optional)"):
            st.caption(
                "Not used in the Large Scope document itself. These are the values the "
                "returnable-schedule filler puts into the client's own forms against "
                "labels like \"Contact Person\", \"Telephone\", \"Email\" and "
                "\"Registered Office\" -- leave them blank and those labels get a "
                "[TO BE COMPLETED] placeholder instead."
            )
            _render_signatory_fields()


# ---------------------------------------------------------------------------
# Tab 2: Upload Documents
# ---------------------------------------------------------------------------

with tabs[1]:
    st.subheader("Upload Documents")
    st.caption("The tender brief is required. Everything else is optional but strongly improves draft quality.")

    st.markdown(
        "**Tender brief (required)** -- PDF, DOCX, TXT, or a whole tender-package **ZIP**. "
        "Sometimes a brief arrives as several separate documents (e.g. the main RFT plus "
        "addenda, schedules, or annexures) -- upload all of them here and they'll be combined "
        "into one brief. A ZIP gets unpacked and sorted automatically: brief + addenda go into "
        "the analysis, returnable schedules are kept aside for filling, drawings are set aside. "
        "If you've already highlighted/commented on any document while reading, upload that "
        "marked-up copy -- your notes get read too."
    )
    if st.session_state.get("_tender_uploader_version") is None:
        st.session_state._tender_uploader_version = 0
    tender_files = st.file_uploader(
        "Upload the tender document(s)", type=["pdf", "docx", "txt", "zip"],
        accept_multiple_files=True,
        key=f"tender_uploader_{st.session_state._tender_uploader_version}",
    )
    # Only (re)extract when the uploaded files actually change -- not on every rerun.
    if tender_files and _files_signature(tender_files) != st.session_state.get("_tender_files_sig"):
        _zip_uploads = [f for f in tender_files if f.name.lower().endswith(".zip")]
        _doc_uploads = [f for f in tender_files if not f.name.lower().endswith(".zip")]
        _package_rows = []      # classification summary rows for the UI
        _package_errors = []
        _package_schedules = {}
        with st.spinner("Extracting text..." if len(tender_files) == 1 else f"Extracting text from {len(tender_files)} files..."):
            per_file = [document_processor.extract_text_from_file(f) for f in _doc_uploads]
            for _zf in _zip_uploads:
                _pkg = package_intake.process_zip(_zf.getvalue(), _zf.name)
                if _pkg.fatal_error:
                    _package_errors.append(_pkg.fatal_error)
                    continue
                per_file.extend(f.extracted for f in _pkg.briefs + _pkg.addenda if f.extracted)
                for _sched in _pkg.schedules:
                    if _sched.file_bytes:
                        _package_schedules[_sched.filename.rsplit("/", 1)[-1]] = _sched.file_bytes
                for _cf in _pkg.all_files():
                    _package_rows.append({
                        "File": _cf.filename,
                        "Filed as": package_intake.CATEGORY_LABELS.get(_cf.category, _cf.category),
                        "Why / what to do": _cf.reason,
                        "_category": _cf.category,
                    })
                _package_errors.extend(_pkg.warnings)
            extracted = document_processor.combine_extracted_documents(per_file)
        st.session_state._tender_files_sig = _files_signature(tender_files)
        st.session_state._package_intake_rows = _package_rows or None
        st.session_state._package_intake_notes = _package_errors or None
        if _package_schedules:
            # Kept for the returnable-schedule filler -- merged, not replaced,
            # same rationale as merge_extracted_material() for company files.
            st.session_state.returnable_schedule_files = {
                **(st.session_state.get("returnable_schedule_files") or {}),
                **_package_schedules,
            }
        if extracted.warning and not extracted.text:
            st.session_state._tender_extract_error = extracted.warning
        elif not extracted.text and _package_rows:
            # ZIP-only upload that contained no analysable brief/addenda --
            # a coherent outcome, not an error: say what WAS found instead.
            st.session_state._tender_extract_error = (
                "No brief or addenda were found in that package (see the breakdown below "
                "for how each file was filed). Upload the brief itself -- as a PDF/DOCX, "
                "or in another ZIP -- to run the analysis."
            )
        else:
            # A genuinely new/changed brief invalidates everything derived
            # from the old one -- see _reset_downstream_from_brief(). Runs
            # before setting the new tender_extracted so the stepper never
            # shows a stale "done" for steps that haven't run against this
            # brief yet.
            _reset_downstream_from_brief()
            st.session_state.tender_extracted = extracted
            st.session_state._tender_extract_error = None

    if st.session_state.get("_tender_extract_error"):
        st.error(st.session_state._tender_extract_error)

    # Package (ZIP) classification breakdown -- persists across reruns so
    # the user can always see where each file in the package ended up.
    if st.session_state.get("_package_intake_notes"):
        for _note in st.session_state._package_intake_notes:
            st.warning(_note)
    if st.session_state.get("_package_intake_rows"):
        with st.expander("Tender package breakdown -- how each file was filed", expanded=True):
            _rows = st.session_state._package_intake_rows
            st.dataframe(
                [{k: v for k, v in r.items() if not k.startswith("_")} for r in _rows],
                use_container_width=True, hide_index=True,
            )
            _n_sched = sum(1 for r in _rows if r["_category"] == "schedule")
            _n_drawings = sum(1 for r in _rows if r["_category"] == "drawing")
            _n_unreadable = sum(1 for r in _rows if r["_category"] == "unreadable")
            if _n_sched:
                st.info(
                    f"{_n_sched} returnable schedule(s) were kept aside -- see the "
                    f"**Returnable Schedules** section on the Export Pack tab to fill them "
                    f"from this project's data."
                )
            if _n_drawings:
                st.caption(f"{_n_drawings} drawing/image file(s) were set aside -- drawings aren't used in the text analysis.")
            if _n_unreadable:
                st.markdown(
                    f"{_n_unreadable} file(s) couldn't be read -- each row above says why and how to fix it, "
                    f"or [email us the file]({package_intake.support_mailto('tender file')}) and we'll process it for you."
                )

    _ext = st.session_state.tender_extracted
    if _ext is not None and _ext.text:
        if _ext.warning:
            st.warning(_ext.warning)
        if getattr(_ext, "ocr_used", False) and not _ext.warning:
            # Standing badge for a project re-loaded from a save (the
            # detailed extraction warning above only exists right after
            # upload) -- the OCR caveat must follow the project around.
            st.warning(
                f"Parts of this brief were read with text recognition (OCR) from scanned "
                f"pages. {document_processor.OCR_VERIFY_TAG}: double-check numbers, dates "
                f"and names against the original document."
            )
        tcol1, tcol2 = st.columns([8, 1])
        with tcol1:
            st.success(
                f"Tender brief loaded -- {len(_ext.text):,} characters"
                + (f" across {_ext.page_count} pages" if _ext.page_count else "")
                + f". Found {len(_ext.headings)} candidate headings, {len(_ext.tables)} table(s), "
                + f"and {len(_ext.annotations)} existing annotation(s)."
            )
        with tcol2:
            if st.button("Clear all", key="clear_tender", help="Remove the uploaded tender document(s) and start over", type="primary"):
                _reset_downstream_from_brief()
                st.session_state.tender_extracted = None
                st.session_state._tender_extract_error = None
                st.session_state._tender_files_sig = None
                st.session_state._tender_uploader_version += 1
                st.rerun()
        if not tender_files:
            st.caption("↩︎ Retained from your saved project (or an earlier upload). Re-upload only if the brief has changed.")
        if _ext.annotations:
            with st.expander(f"Preview {len(_ext.annotations)} annotation(s) found in the PDF(s)"):
                for a in _ext.annotations[:30]:
                    source = f"{a['source_file']}, " if a.get("source_file") else ""
                    st.markdown(f"- **{source}p.{a['page']}** ({a['type']}): _{a.get('comment') or '(highlight only)'}_ — \"{a.get('highlighted_text','')[:150]}\"")

    st.divider()
    st.markdown("**Optional company material** -- upload as many files as you like per category. Multiple files per category are combined.")

    LEGACY_MATERIAL_KEY = "(previously uploaded files)"

    def _sync_material_text(key: str) -> None:
        """Recompute the combined text blob for a category from its per-file
        store -- call this after any add/remove/clear so every reader of
        company_material_text (draft generation, CV matching, etc.) sees the
        current set without needing to know about the per-file breakdown."""
        files_for_key = st.session_state.company_material_files.get(key, {})
        st.session_state.company_material_text[key] = "\n\n".join(files_for_key.values())

    def _clear_material_category(key: str) -> None:
        """Fully reset one company-material category: drop the per-file store, the
        combined text blob, and (for the CV library) the filename list. Also bumps
        that category's uploader widget version so the file chips shown in the
        uploader itself disappear too, not just the stored-text status line below
        it. This is a clean slate for that category -- used by the per-category
        'Clear all' button."""
        st.session_state.company_material_files[key] = {}
        st.session_state.company_material_text[key] = ""
        if key == "cv_library":
            st.session_state.cv_library_filenames = []
        # Reset the signature too -- otherwise re-uploading the exact same file(s)
        # into the fresh widget below would look unchanged and never re-extract.
        st.session_state[f"_matsig_{key}"] = None
        st.session_state[f"_matuploader_version_{key}"] = st.session_state.get(f"_matuploader_version_{key}", 0) + 1

    for key, label in COMPANY_MATERIAL_CATEGORIES.items():
        if st.session_state.get(f"_matuploader_version_{key}") is None:
            st.session_state[f"_matuploader_version_{key}"] = 0
        files = st.file_uploader(
            label, type=["pdf", "docx", "txt"], accept_multiple_files=True,
            key=f"upload_{key}_{st.session_state[f'_matuploader_version_{key}']}",
            help="Uploading adds/updates these files; anything already stored for this category "
                 "is kept, not replaced. Use 'Clear all' below to wipe the category and start over.",
        )
        sig_key = f"_matsig_{key}"
        if files and _files_signature(files) != st.session_state.get(sig_key):
            with st.spinner(f"Extracting {label}..."):
                updates = {}
                for f in files:
                    doc = document_processor.extract_plain_text_from_file(f)
                    if doc.warning and not doc.text:
                        st.warning(doc.warning)
                    elif doc.text:
                        updates[getattr(f, "name", "")] = doc.text
            existing_files_for_key = st.session_state.company_material_files.get(key, {})
            if not existing_files_for_key:
                # Migration for a project saved before per-file tracking existed: it only has
                # one big combined blob, with no per-file breakdown. Seed that blob in as a
                # single legacy entry BEFORE merging the new upload, so uploading just 1-2
                # files doesn't wipe out everyone else's already-extracted text.
                legacy_text = (st.session_state.company_material_text.get(key) or "").strip()
                if legacy_text:
                    existing_files_for_key = {LEGACY_MATERIAL_KEY: legacy_text}
            st.session_state.company_material_files[key] = document_processor.merge_extracted_material(
                existing_files_for_key, updates,
            )
            _sync_material_text(key)
            if key == "cv_library":
                # Grow the filename-suggestion list with the newly uploaded names (union,
                # not replace); the legacy bookkeeping key is never a real filename.
                st.session_state.cv_library_filenames = list(dict.fromkeys(
                    list(st.session_state.cv_library_filenames or []) + list(updates.keys())
                ))
            st.session_state[sig_key] = _files_signature(files)

        if key == "previous_proposals":
            st.caption(
                "📁 To pull in a proposal you've already archived, use the 'Add as reference to "
                "project' button in the Proposal Library popover (top banner) instead of "
                "re-uploading it here."
            )
        if key == "project_references":
            st.caption(
                "📁 To pull in a firm reference project you've uploaded to the Project Reference "
                "Library, use its 'Add to project references' button in the top banner instead "
                "of re-uploading it here."
            )

        # The uploaded files themselves are shown by Streamlit's own uploader widget above
        # (each with its own x). Here we only show a one-line status of what's stored plus a
        # single 'Clear all' button to wipe the category -- no duplicate filename list.
        stored_files = st.session_state.company_material_files.get(key, {})
        existing = (st.session_state.company_material_text.get(key) or "").strip()
        if existing:
            n_files = len([f for f in stored_files if f != LEGACY_MATERIAL_KEY])
            count_bit = f"{n_files} file(s), " if n_files else ""
            scol1, scol2 = st.columns([8, 1])
            with scol1:
                st.caption(f"✅ {label}: {count_bit}{len(existing):,} characters stored.")
            with scol2:
                if st.button("Clear all", key=f"clear_{key}", help=f"Remove all {label.lower()} and start over", type="primary"):
                    _clear_material_category(key)
                    st.rerun()

    if st.session_state.get("_photo_uploader_version") is None:
        st.session_state._photo_uploader_version = 0
    photo_files = st.file_uploader(
        "Project photos", type=["png", "jpg", "jpeg"], accept_multiple_files=True,
        key=f"upload_photos_{st.session_state._photo_uploader_version}",
    )
    if photo_files and _files_signature(photo_files) != st.session_state.get("_photo_files_sig"):
        st.session_state.project_photo_bytes = [f.getvalue() for f in photo_files]
        st.session_state._photo_files_sig = _files_signature(photo_files)
    if st.session_state.project_photo_bytes:
        retained = " (retained from saved project)" if not photo_files else ""
        pcol1, pcol2 = st.columns([8, 1])
        with pcol1:
            st.caption(f"✅ {len(st.session_state.project_photo_bytes)} project photo(s) loaded -- the first is the cover image{retained}.")
        with pcol2:
            if st.button("Clear all", key="clear_photos", help="Remove all project photos and start over", type="primary"):
                st.session_state.project_photo_bytes = []
                st.session_state._photo_files_sig = None
                st.session_state._photo_uploader_version += 1
                st.rerun()

    if st.session_state.get("_branding_uploader_version") is None:
        st.session_state._branding_uploader_version = 0
    branding_files = st.file_uploader(
        "Company branding / image library", type=["png", "jpg", "jpeg"], accept_multiple_files=True,
        key=f"upload_branding_{st.session_state._branding_uploader_version}",
    )
    if branding_files and _files_signature(branding_files) != st.session_state.get("_branding_files_sig"):
        st.session_state.branding_bytes = [f.getvalue() for f in branding_files]
        st.session_state._branding_files_sig = _files_signature(branding_files)
    if st.session_state.branding_bytes:
        retained = " (retained from saved project)" if not branding_files else ""
        bcol1, bcol2 = st.columns([8, 1])
        with bcol1:
            st.caption(f"✅ {len(st.session_state.branding_bytes)} branding image(s) loaded{retained}.")
        with bcol2:
            if st.button("Clear all", key="clear_branding", help="Remove all branding images and start over", type="primary"):
                st.session_state.branding_bytes = []
                st.session_state._branding_files_sig = None
                st.session_state._branding_uploader_version += 1
                st.rerun()

    st.divider()
    st.markdown("#### Reference projects (Relevant Experience section)")
    st.caption(
        "Draft, then review and edit, the distinct past projects the exported pack will show in "
        "Relevant Experience -- revised for consistent tone and relevance to THIS tender, not the "
        "raw uploaded text pasted in. Add a photo per project if you have one, and confirm which "
        "of your key personnel worked on each -- that feeds the Section 2 x Section 3 "
        "cross-reference table automatically. Best done here, early, so it's ready before Export."
    )
    raw_refs_text = (st.session_state.company_material_text.get("project_references") or "").strip()
    if not raw_refs_text:
        st.info("Upload 'Project references' material above to draft reference projects from it, or add one manually below.")
    elif not st.session_state.reference_projects:
        # Uploading the raw material only extracts its text -- it does NOT
        # automatically turn into reference project entries. That second
        # step (the button right below) is easy to miss, since the upload
        # widget itself shows a reassuring green "X file(s) stored"
        # confirmation that looks like the whole job is done. Called out
        # explicitly here so "I uploaded my references but nothing's
        # happening" has an obvious next step instead of looking broken.
        st.info(
            "Material uploaded and read. Click **Draft reference projects from uploaded material** "
            "below to have the AI turn it into the individual project entries shown further down -- "
            "uploading alone doesn't create them yet."
        )

    refs_ai_ready = bool(st.session_state.ai_config.get("api_key")) and bool(raw_refs_text) and _current_project_already_paid()
    if st.button("Draft reference projects from uploaded material", disabled=not refs_ai_ready,
                 help=None if refs_ai_ready else (
                     _PROJECT_NOT_PAID_HINT if not _current_project_already_paid()
                     else f"Upload 'Project references' material above and {_AI_HINT_CLAUSE}."
                 ), type="primary"):
        with st.spinner("Reading project reference material and drafting revised, relevance-led entries..."):
            try:
                analysis_for_context = st.session_state.analysis
                drafted, warnings = reference_projects_module.draft_reference_projects(
                    raw_refs_text,
                    project_scope=(analysis_for_context.project_scope if analysis_for_context else ""),
                    disciplines=(analysis_for_context.disciplines_involved if analysis_for_context else []),
                    # Relevance is what these entries are FOR, and the
                    # strongest relevance a past project can have -- same
                    # client, same objective -- couldn't be spotted, because
                    # neither was ever passed in.
                    client_name=st.session_state.client_name,
                    client_objectives=(analysis_for_context.client_objectives if analysis_for_context else []),
                    config=st.session_state.ai_config,
                )
                st.session_state.reference_projects = drafted
                st.session_state.reference_project_warnings = warnings
                st.success(f"Drafted {len(drafted)} reference project(s). Review and edit every field below before export.")
                if not analysis_for_context:
                    st.info("Tender Analysis hasn't run yet -- re-run this once it has, so relevance can be tailored to the actual brief.")
            except Exception as exc:
                _show_error("Reference project drafting failed", exc)

    if st.session_state.reference_project_warnings:
        st.warning("\n\n".join(st.session_state.reference_project_warnings))

    if st.session_state.reference_projects is None:
        st.session_state.reference_projects = []

    _known_personnel_names = resourcing.cv_derived_names(
        st.session_state.team_members,
        list(st.session_state.cv_extracted_names)
        + resourcing.names_from_filenames(st.session_state.cv_library_filenames)
        + list(st.session_state.resource_extra_names)
        + [a.person_name for a in st.session_state.resource_plan if (a.person_name or "").strip()],
    )

    _remove_ref_index = None
    for i, proj in enumerate(st.session_state.reference_projects):
        with st.expander(f"{proj.title or f'Reference project {i + 1}'}" + (f" -- {proj.client}" if proj.client else ""), expanded=False):
            proj.title = st.text_input("Project title", value=proj.title, key=f"ref_title_{i}")
            proj.client = st.text_input("Client", value=proj.client, key=f"ref_client_{i}")
            proj.description = st.text_area("Description (revised for consistency/relevance)", value=proj.description, key=f"ref_desc_{i}", height=110)
            proj.relevance_text = st.text_area("Relevance to this tender", value=proj.relevance_text, key=f"ref_rel_{i}", height=70)
            options = sorted(set(_known_personnel_names) | set(proj.personnel_involved))
            proj.personnel_involved = st.multiselect(
                "Key personnel who worked on this project", options,
                default=[n for n in proj.personnel_involved if n in options], key=f"ref_pers_{i}",
            )
            photo = st.file_uploader("Project photo (optional)", type=["png", "jpg", "jpeg"], key=f"ref_photo_{i}")
            if photo is not None:
                st.session_state.reference_project_photos[proj.title] = photo.getvalue()
            existing_ref_photo = st.session_state.reference_project_photos.get(proj.title)
            if existing_ref_photo:
                st.image(existing_ref_photo, width=160)
            if st.button("Remove this reference project", key=f"ref_remove_{i}", type="primary"):
                _remove_ref_index = i
    if _remove_ref_index is not None:
        st.session_state.reference_projects.pop(_remove_ref_index)
        st.rerun()

    with st.form("add_reference_project_form", clear_on_submit=True):
        st.markdown("**Add a reference project manually**")
        new_ref_title = st.text_input("Project title")
        new_ref_client = st.text_input("Client")
        if st.form_submit_button("Add reference project", type="primary") and new_ref_title.strip():
            st.session_state.reference_projects.append(
                reference_projects_module.ReferenceProject(title=new_ref_title.strip(), client=new_ref_client.strip())
            )
            st.rerun()


# ---------------------------------------------------------------------------
# Tab 3: Tender Analysis
# ---------------------------------------------------------------------------

with tabs[2]:
    st.subheader("Tender Analysis")
    st.caption("Extracts scope, objectives, mandatory requirements, evaluation criteria, weightings, page limits, deliverables, forms, and risks from the uploaded brief.")

    # A project name is required before Tender Analysis can run at all --
    # not just a UX nicety. It's the identity that anchors the paywall: see
    # _project_key below, which auth.record_proposal_usage() uses to decide
    # whether this run has already been billed. Without a name (blank
    # Project Setup), that key used to collapse to an empty string, which
    # record_proposal_usage() silently refused to record at all -- meaning
    # trial_proposals_used never incremented and get_access_status() kept
    # reporting a fresh, unused trial forever. Requiring a name here closes
    # that off at the one place it can be closed for good, rather than
    # relying on record_proposal_usage() alone (which now raises instead of
    # silently no-op'ing, but by then it's too late to stop the AI call).
    _has_project_name = bool((st.session_state.project_name or "").strip())
    ready = (
        st.session_state.tender_extracted is not None
        and bool(st.session_state.ai_config.get("api_key"))
        and _has_project_name
    )
    if not ready:
        if st.session_state.tender_extracted is not None and not _has_project_name:
            st.info("Enter a project name on the Project Setup tab before running Tender Analysis.")
        else:
            st.info(f"Upload a tender brief (Upload Docs) and {_AI_HINT_CLAUSE} to run analysis.")

    # This is the metered action: the first time a given project+document
    # runs Tender Analysis, it consumes the account's free trial bid(s) (see
    # auth.record_proposal_usage; auth.DEFAULT_TRIAL_LIMIT -- 1, see
    # auth.get_access_status). Re-running analysis on the SAME project AND
    # SAME document never counts twice. The key folds in a hash of the
    # brief's own extracted text (not just the user-typed project/tender/
    # client names) on purpose -- keying on the typed names alone would let
    # someone keep "Project A" as the name, swap in a completely different
    # tender brief, and re-run for free indefinitely; the hash means a
    # materially different document is always a new, billable project even
    # under an unchanged name. Once the trial is used up, the button is
    # replaced with an upgrade prompt instead of silently doing nothing --
    # except for auth.UNLIMITED_ACCOUNTS, who never hit limit_reached at all
    # (see get_access_status) so never see this prompt.
    _brief_text_for_key = st.session_state.tender_extracted.text if st.session_state.tender_extracted else ""
    _brief_hash = hashlib.sha256(_brief_text_for_key.encode("utf-8")).hexdigest()[:16] if _brief_text_for_key else ""
    _project_key = (
        f"{st.session_state.project_name}|{st.session_state.tender_name}|"
        f"{st.session_state.client_name}|{_brief_hash}"
    ).strip("|")
    _already_counted = False
    if IS_SAAS_MODE and current_user:
        with db.get_session() as _s:
            _already_counted = _s.query(db.ProposalUsage).filter(
                db.ProposalUsage.user_id == current_user.id,
                db.ProposalUsage.project_key == _project_key.lower(),
            ).first() is not None
    _trial_blocked = IS_SAAS_MODE and current_user and not _access["allowed"] and not _already_counted

    if _trial_blocked or (IS_SAAS_MODE and current_user and _access["limit_reached"] and not _already_counted):
        if _access["past_due"]:
            # Same monthly quota as an active subscriber (see
            # auth.get_access_status), but the actionable fix here is fixing
            # payment, not buying more -- lead with that.
            st.warning(
                "Your payment is past due, and you've also used this cycle's "
                f"{_access['subscription_bid_limit']} included bid(s). Update your payment method to keep "
                "your subscription active, or buy a pay-as-you-go bid to keep going right now."
            )
        elif _access["subscribed"]:
            st.warning(
                f"You've used all {_access['subscription_bid_limit']} bid(s) included in this billing "
                "cycle's Monthly plan. Buy a pay-as-you-go bid to keep going now, or wait for renewal."
            )
        else:
            st.warning(
                f"You've used all {_access['trial_limit']} free trial bid(s). "
                "Upgrade to keep going -- pay per bid, or subscribe monthly. See pricing on the homepage."
            )
        _render_upgrade_buttons(current_user, key_prefix="_tab3",
                                 already_subscribed=_access["subscribed"] or _access["past_due"])

    # Tell people exactly what clicking the button below is about to spend --
    # previously nothing here said this consumes the account's one free
    # trial bid, so someone testing with a throwaway/wrong file could burn
    # it by accident and land on the paywall with no idea why. Skipped
    # entirely for re-runs of the exact same project+document (see
    # _already_counted above -- those are free) and for unlimited accounts.
    if IS_SAAS_MODE and current_user and ready and not _trial_blocked and not _access["unlimited"]:
        if _already_counted:
            st.caption("You've already run analysis on this exact project and document -- re-running it now won't use another bid.")
        elif _access["subscribed"] or _access["past_due"]:
            if _access["subscription_bids_remaining"] > 0:
                st.caption(
                    f"This will use 1 of your {_access['subscription_bids_remaining']} remaining bid(s) "
                    "in this billing cycle."
                )
            else:
                st.caption(f"This will use 1 pay-as-you-go bid credit (you have {_access['bid_credits']} left).")
        elif _access["trial_remaining"] > 0:
            st.caption(f"This will use your {_access['trial_remaining']} free trial bid -- make sure this is the right document first.")
        else:
            st.caption(f"This will use 1 pay-as-you-go bid credit (you have {_access['bid_credits']} left).")

    if st.button("Run Tender Analysis", type="primary", disabled=not ready or _trial_blocked):
        extracted = st.session_state.tender_extracted
        progress = st.progress(0.0, text="Analysing...")

        def _progress_cb(done, total):
            progress.progress((done + 1) / max(total, 1), text=f"Analysing part {done + 1}/{total}...")

        try:
            # Runs on the background job worker for logged-in SaaS users
            # once REDIS_URL is configured (see modules/job_queue.py and
            # DEPLOY.md's "Background jobs" section) -- this is the
            # single slowest AI call in the app for a long brief, and
            # running it inline in the main web process was blocking
            # every other concurrently-connected user's Streamlit session
            # while it ran. Falls back to running inline (same as always)
            # with the same granular per-chunk progress bar when the
            # queue isn't available yet -- see _run_job_or_inline. The
            # queued path gets a REDACTED ai_config (api_key="") and a
            # different target function (job_queue.run_tender_analysis_job,
            # which re-fills the key from the worker process's own env --
            # see job_queue.py's docstring) so the real server Anthropic key
            # never ends up pickled into Redis.
            _redacted_ai_config = {**st.session_state.ai_config, "api_key": ""}
            analysis = _run_job_or_inline(
                "tender_analysis", tender_analyser.analyse_tender,
                args=(extracted.text, extracted.annotations, st.session_state.ai_config),
                # The brief's own tables. pdfplumber has always pulled these
                # out (the upload panel even counts them) and the analysis
                # never saw them -- which is where the evaluation criteria and
                # their weightings usually live.
                kwargs={"tables": getattr(extracted, "tables", None)},
                progress=progress,
                queued_text="Queued for analysis...", running_text="Analysing...",
                inline_extra_kwargs={"progress_callback": _progress_cb},
                queue_func=job_queue.run_tender_analysis_job,
                queue_args=(extracted.text, extracted.annotations, _redacted_ai_config),
            )
            st.session_state.analysis = analysis
            progress.progress(1.0, text="Done.")
            st.success("Tender analysis complete.")
            if IS_SAAS_MODE and current_user:
                auth.record_proposal_usage(current_user, _project_key, st.session_state.project_name)
                # Signup-funnel step 3 (activation): a bid actually analysed.
                analytics.track_event("Bid Analysed")
        except Exception as exc:
            _show_error("Analysis failed", exc)

    analysis = st.session_state.analysis
    if analysis:
        if getattr(st.session_state.tender_extracted, "ocr_used", False):
            st.warning(
                f"This analysis is based on text read with OCR from scanned pages. "
                f"{document_processor.OCR_VERIFY_TAG}: double-check extracted requirements, "
                f"dates, and numbers against the original document."
            )
        st.markdown("#### Project scope")
        st.write(analysis.project_scope or "_not extracted_")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Client objectives")
            st.write(analysis.client_objectives or "_none extracted_")
            st.markdown("#### Mandatory requirements")
            st.write(analysis.mandatory_requirements or "_none extracted_")
            st.markdown("#### Deliverables")
            st.write(analysis.deliverables or "_none extracted_")
        with col2:
            st.markdown(f"**Submission date:** {analysis.submission_date or '_not stated_'}")
            st.markdown(f"**Total page limit:** {analysis.total_page_limit or '_not stated_'}")
            st.markdown(f"**Fee cap:** {analysis.fee_cap or '_not stated_'}")
            st.markdown(f"**Uses named selection criteria (SC1/SC2 style):** {'Yes' if analysis.uses_named_selection_criteria else 'No'}")
            st.markdown("#### Required forms / schedules")
            st.write(analysis.required_forms or "_none extracted_")

        st.markdown("#### Evaluation / selection criteria")
        if analysis.evaluation_criteria:
            st.dataframe(
                [{
                    "Code": c.criterion_code or "-", "Name": c.name,
                    "Weighting": f"{c.detected_weighting:.0f}%" if c.detected_weighting is not None else ("Mandatory gate" if c.is_mandatory_gate else "-"),
                    "Page limit": c.page_limit or "-", "Format rules": c.format_requirements or "-",
                } for c in analysis.evaluation_criteria],
                use_container_width=True,
            )
        else:
            st.write("_No evaluation criteria extracted._")

        if analysis.user_flagged_items:
            st.markdown("#### Items you flagged via annotations")
            for item in analysis.user_flagged_items:
                st.markdown(f"- **p.{item.get('page','?')}:** {item.get('note')} — _{item.get('context','')[:150]}_")

        if analysis.risks:
            st.markdown("#### Risks noted in the brief")
            st.write(analysis.risks)

        if analysis.analysis_warnings:
            st.warning("Extraction warnings -- verify these manually against the brief:\n\n" + "\n".join(f"- {w}" for w in analysis.analysis_warnings))



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
    st.subheader(i18n.t("setup_subheader"))
    st.caption(i18n.t("setup_caption"))

    st.markdown(i18n.t("setup_format_heading"))
    st.caption(i18n.t("setup_format_caption"))
    format_label = st.selectbox(
        i18n.t("setup_format_select_label"),
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
        st.text_input(i18n.t("setup_project_name_label"), key="project_name")
        st.text_input(i18n.t("setup_client_name_label"), key="client_name")
        st.text_input(i18n.t("setup_tender_name_label"), key="tender_name")
        st.text_input(i18n.t("setup_submission_date_label"), key="submission_date_input", placeholder=i18n.t("setup_submission_date_placeholder"))
    with col2:
        st.text_input(i18n.t("setup_bidder_name_label"), key="bidder_name")
        st.selectbox(i18n.t("setup_project_type_label"), PROJECT_TYPES, key="project_type")
        st.selectbox(i18n.t("setup_proposal_theme_label"), PROPOSAL_THEMES, key="proposal_theme")
        # Language of the AI-GENERATED proposal content (drafts, executive summary,
        # etc.) that ends up in the exported DOCX/PPTX -- a per-PROJECT choice,
        # separate from the app's own UI language (the switcher in the sidebar).
        # Always shows "English"/"Español" in their own language regardless of the
        # current UI language, since this is a language-name picker, not a phrase
        # to translate -- see modules/i18n.py's LANGUAGES dict.
        _output_language_label = st.selectbox(
            i18n.t("setup_output_language_label"),
            list(i18n.LANGUAGES.values()),
            index=list(i18n.LANGUAGES.keys()).index(st.session_state.get("output_language", "en")),
            key="output_language_select",
            help=i18n.t("setup_output_language_help"),
        )
        st.session_state.output_language = {v: k for k, v in i18n.LANGUAGES.items()}[_output_language_label]
    st.caption(i18n.t("setup_autosave_caption"))

    if IS_SAAS_MODE and current_user:
        with st.popover(i18n.t("bid_includes_popover_title")):
            st.markdown(i18n.t("bid_includes_popover_body"))

    # Audit fix Part 3b: re-derive "is the currently loaded project paid?"
    # from the database on EVERY rerun of this tab, not only right after a
    # live analysis run -- see _maybe_snapshot_paid_identity()'s docstring
    # for why this is what makes the rename-confirm dialog below survive a
    # page refresh, a fresh login, or a project reloaded from a previous
    # session, instead of only working within the same browser tab that
    # happened to run the analysis.
    _maybe_snapshot_paid_identity()

    # Part C: renaming (or swapping the client/tender name on) an
    # already-PAID project computes a different billing identity -- see
    # _current_project_key()'s docstring -- so the paid analysis stays
    # attached to the name it was actually billed under. This can't block
    # the edit itself (Project Setup's fields commit live, with no submit
    # step to intercept -- see the comment above), so instead it surfaces
    # right after the change is detected, once per new identity.
    _pending_rename_key = _pending_rename_confirmation()
    if _pending_rename_key:
        @st.dialog(i18n.t("rename_confirm_title"))
        def _rename_confirm_dialog():
            st.write(i18n.t("rename_confirm_body"))
            _rc_col1, _rc_col2 = st.columns(2)
            with _rc_col1:
                # Audit fix Part 3b: migrates the paid billing/passes
                # records to the new identity (see
                # auth.migrate_project_identity()) so the rename never
                # actually costs the payment -- see _confirm_rename()'s
                # docstring.
                if st.button(i18n.t("rename_confirm_yes"), type="primary", key="_rename_confirm_yes_btn"):
                    _confirm_rename(_pending_rename_key)
                    st.rerun()
            with _rc_col2:
                # Audit fix Part 3b: actually cancels now -- reverts the
                # three editable identity fields to their last-known-paid
                # values (see _cancel_rename()'s docstring), rather than
                # just dismissing the dialog while leaving the edit in
                # place.
                if st.button(i18n.t("rename_confirm_cancel"), key="_rename_confirm_cancel_btn"):
                    _cancel_rename(_pending_rename_key)
                    st.rerun()
        _rename_confirm_dialog()

    # The cover page and the brief can disagree about when this is due, and
    # nothing used to say so. The typed date is what gets printed; the
    # extracted one is what the client actually wrote.
    _typed_date = (st.session_state.submission_date_input or "").strip()
    _brief_date = ((getattr(st.session_state.analysis, "submission_date", "") or "").strip()
                   if st.session_state.analysis else "")
    if _typed_date and _brief_date and not _dates_look_equivalent(_typed_date, _brief_date):
        st.warning(i18n.t("setup_date_mismatch_warning", typed_date=_typed_date, brief_date=_brief_date))

    def _render_signatory_fields() -> None:
        """The contact/signatory block. Shared by both proposal formats --
        see the two call sites below for why each renders it differently."""
        scol1, scol2 = st.columns(2)
        with scol1:
            st.text_input(i18n.t("setup_sender_name_label"), key="letter_sender_name", placeholder=i18n.t("setup_sender_name_placeholder"))
            st.text_input(i18n.t("setup_sender_title_label"), key="letter_sender_title", placeholder=i18n.t("setup_sender_title_placeholder"))
        with scol2:
            st.text_input(i18n.t("setup_sender_phone_label"), key="letter_sender_phone")
            st.text_input(i18n.t("setup_sender_email_label"), key="letter_sender_email")
        st.text_input(
            i18n.t("setup_sender_address_label"), key="letter_sender_address",
            placeholder=i18n.t("setup_sender_address_placeholder"),
            help=i18n.t("setup_sender_address_help"),
        )

    if _is_letter():
        st.divider()
        st.markdown(i18n.t("setup_signoff_heading"))
        st.caption(i18n.t("setup_signoff_caption"))
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
        with st.expander(i18n.t("setup_contact_expander")):
            st.caption(i18n.t("setup_contact_expander_caption"))
            _render_signatory_fields()


# ---------------------------------------------------------------------------
# Tab 2: Upload Documents
# ---------------------------------------------------------------------------

with tabs[1]:
    st.subheader(i18n.t("upload_subheader"))
    st.caption(i18n.t("upload_caption"))

    st.markdown(i18n.t("upload_brief_intro"))
    if st.session_state.get("_tender_uploader_version") is None:
        st.session_state._tender_uploader_version = 0
    tender_files = st.file_uploader(
        i18n.t("upload_tender_files_label"), type=["pdf", "docx", "txt", "zip"],
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

        # Trial upload limit on brief + addenda FILE COUNT (Part 1 -- see
        # modules/limits.py). Counted across BOTH plain document uploads
        # and whatever a ZIP unpacks to a brief/addendum -- a ZIP is a
        # container, not itself "one file" for this limit. UNLIMITED_ACCOUNTS
        # bypass entirely (_files_budget stays None = unlimited). Classification
        # still runs over EVERYTHING (the breakdown table below always lists
        # every file in a ZIP); only INGESTION (what feeds the analysis) is
        # capped, with each skipped file's own row saying so.
        _files_budget = None
        if IS_SAAS_MODE and current_user and not _access.get("unlimited"):
            _files_budget = limits.limits_for(current_user, _access)["tender_files"]

        with st.spinner(i18n.t("upload_extracting_single") if len(tender_files) == 1 else i18n.t("upload_extracting_multi", n=len(tender_files))):
            _doc_uploads_kept = _doc_uploads
            if _files_budget is not None and len(_doc_uploads) > _files_budget:
                _doc_uploads_kept, _docs_limit_msg = limits.enforce_count_limit(_doc_uploads, "tender_files", _access)
                if _docs_limit_msg:
                    _package_errors.append(_docs_limit_msg)
            per_file = [document_processor.extract_text_from_file(f) for f in _doc_uploads_kept]
            if _files_budget is not None:
                _files_budget = max(0, _files_budget - len(_doc_uploads_kept))
            _zip_skipped = 0
            for _zf in _zip_uploads:
                _pkg = package_intake.process_zip(_zf.getvalue(), _zf.name)
                if _pkg.fatal_error:
                    _package_errors.append(_pkg.fatal_error)
                    continue
                for _cf in _pkg.briefs + _pkg.addenda:
                    if not _cf.extracted:
                        continue
                    if _files_budget is None or _files_budget > 0:
                        per_file.append(_cf.extracted)
                        if _files_budget is not None:
                            _files_budget -= 1
                    else:
                        _zip_skipped += 1
                        _trial_limit, _paid_limit = limits.UPLOAD_LIMITS["tender_files"]
                        _cf.reason = i18n.t(
                            "upload_zip_not_ingested_reason",
                            trial_limit=_trial_limit, paid_limit=_paid_limit, original_reason=_cf.reason,
                        )
                for _sched in _pkg.schedules:
                    if _sched.file_bytes:
                        _package_schedules[_sched.filename.rsplit("/", 1)[-1]] = _sched.file_bytes
                for _cf in _pkg.all_files():
                    _package_rows.append({
                        i18n.t("upload_col_file"): _cf.filename,
                        i18n.t("upload_col_filed_as"): package_intake.CATEGORY_LABELS.get(_cf.category, _cf.category),
                        i18n.t("upload_col_why_what_to_do"): _cf.reason,
                        "_category": _cf.category,
                    })
                _package_errors.extend(_pkg.warnings)
            if _zip_skipped:
                _trial_limit, _paid_limit = limits.UPLOAD_LIMITS["tender_files"]
                _package_errors.append(i18n.t(
                    "upload_zip_skipped_summary",
                    n=_zip_skipped, trial_limit=_trial_limit, paid_limit=_paid_limit,
                ))
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
            st.session_state._tender_extract_error = i18n.t("upload_no_brief_found_error")
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
        with st.expander(i18n.t("upload_breakdown_expander"), expanded=True):
            _rows = st.session_state._package_intake_rows
            st.dataframe(
                [{k: v for k, v in r.items() if not k.startswith("_")} for r in _rows],
                use_container_width=True, hide_index=True,
            )
            _n_sched = sum(1 for r in _rows if r["_category"] == "schedule")
            _n_drawings = sum(1 for r in _rows if r["_category"] == "drawing")
            _n_unreadable = sum(1 for r in _rows if r["_category"] == "unreadable")
            if _n_sched:
                st.info(i18n.t("upload_schedules_kept_aside_info", n=_n_sched))
            if _n_drawings:
                st.caption(i18n.t("upload_drawings_set_aside_caption", n=_n_drawings))
            if _n_unreadable:
                st.markdown(i18n.t(
                    "upload_unreadable_markdown",
                    n=_n_unreadable, mailto=package_intake.support_mailto('tender file'),
                ))

    _ext = st.session_state.tender_extracted
    if _ext is not None and _ext.text:
        if _ext.warning:
            st.warning(_ext.warning)
        if getattr(_ext, "ocr_used", False) and not _ext.warning:
            # Standing badge for a project re-loaded from a save (the
            # detailed extraction warning above only exists right after
            # upload) -- the OCR caveat must follow the project around.
            st.warning(i18n.t("upload_ocr_warning", ocr_tag=document_processor.OCR_VERIFY_TAG))
        tcol1, tcol2 = st.columns([8, 1])
        with tcol1:
            st.success(i18n.t(
                "upload_brief_loaded_success",
                chars=f"{len(_ext.text):,}",
                pages_part=(i18n.t("upload_brief_loaded_pages_part", pages=_ext.page_count) if _ext.page_count else ""),
                headings=len(_ext.headings), tables=len(_ext.tables), annotations=len(_ext.annotations),
            ))
        with tcol2:
            if st.button(i18n.t("upload_clear_all_button"), key="clear_tender", help=i18n.t("upload_clear_tender_help"), type="primary"):
                _reset_downstream_from_brief()
                st.session_state.tender_extracted = None
                st.session_state._tender_extract_error = None
                st.session_state._tender_files_sig = None
                st.session_state._tender_uploader_version += 1
                st.rerun()
        if not tender_files:
            st.caption(i18n.t("upload_retained_caption"))
        if _ext.annotations:
            with st.expander(i18n.t("upload_annotations_expander", n=len(_ext.annotations))):
                for a in _ext.annotations[:30]:
                    source = f"{a['source_file']}, " if a.get("source_file") else ""
                    st.markdown(f"- **{source}p.{a['page']}** ({a['type']}): _{a.get('comment') or i18n.t('upload_annotation_highlight_only')}_ — \"{a.get('highlighted_text','')[:150]}\"")

    st.divider()
    st.markdown(i18n.t("upload_company_material_heading"))

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
            help=i18n.t("upload_material_uploader_help"),
        )
        sig_key = f"_matsig_{key}"
        if files and _files_signature(files) != st.session_state.get(sig_key):
            # Trial upload limit (Part 1) -- this category MERGES new files
            # with whatever's already stored (see the migration/merge logic
            # below), so the cap has to account for what's already there,
            # not just this batch: enforce_count_limit() alone only knows
            # about a single selection. UNLIMITED_ACCOUNTS bypass entirely.
            if IS_SAAS_MODE and current_user and not _access.get("unlimited"):
                _cat_limit = limits.limits_for(current_user, _access)[key]
                _existing_count = len([
                    f for f in st.session_state.company_material_files.get(key, {}) if f != LEGACY_MATERIAL_KEY
                ])
                _budget = max(0, _cat_limit - _existing_count)
                if len(files) > _budget:
                    _kept, _dropped = files[:_budget], files[_budget:]
                    _dropped_names = ", ".join(getattr(f, "name", None) or "unnamed file" for f in _dropped[:5])
                    if len(_dropped) > 5:
                        _dropped_names += f", and {len(_dropped) - 5} more"
                    _tier_word = i18n.t("limits_tier_paid") if limits.is_paid_tier(_access) else i18n.t("limits_tier_trial")
                    st.warning(
                        i18n.t(
                            "upload_material_limit_warning",
                            tier=_tier_word, limit=_cat_limit, label=limits.upload_label(key),
                            existing=_existing_count,
                            added_clause=(
                                i18n.t("upload_material_added_some", kept=len(_kept), total=len(files))
                                if _kept else i18n.t("upload_material_added_none")
                            ),
                            dropped=_dropped_names,
                        )
                        + limits.upgrade_clause(key, _access)
                    )
                    files = _kept
            with st.spinner(i18n.t("upload_extracting_category_spinner", label=label)):
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
            st.caption(i18n.t("upload_prev_proposals_caption"))
        if key == "project_references":
            st.caption(i18n.t("upload_project_references_caption"))

        # The uploaded files themselves are shown by Streamlit's own uploader widget above
        # (each with its own x). Here we only show a one-line status of what's stored plus a
        # single 'Clear all' button to wipe the category -- no duplicate filename list.
        stored_files = st.session_state.company_material_files.get(key, {})
        existing = (st.session_state.company_material_text.get(key) or "").strip()
        if existing:
            n_files = len([f for f in stored_files if f != LEGACY_MATERIAL_KEY])
            count_bit = i18n.t("upload_material_file_count_bit", n=n_files) if n_files else ""
            scol1, scol2 = st.columns([8, 1])
            with scol1:
                st.caption(i18n.t("upload_material_stored_caption", label=label, count_bit=count_bit, chars=len(existing)))
            with scol2:
                if st.button(i18n.t("upload_clear_all_button"), key=f"clear_{key}", help=i18n.t("upload_clear_category_help", label=label.lower()), type="primary"):
                    _clear_material_category(key)
                    st.rerun()

    if st.session_state.get("_photo_uploader_version") is None:
        st.session_state._photo_uploader_version = 0
    photo_files = st.file_uploader(
        i18n.t("upload_photos_label"), type=["png", "jpg", "jpeg"], accept_multiple_files=True,
        key=f"upload_photos_{st.session_state._photo_uploader_version}",
    )
    if photo_files and _files_signature(photo_files) != st.session_state.get("_photo_files_sig"):
        if IS_SAAS_MODE and current_user and not _access.get("unlimited"):
            photo_files, _photo_limit_msg = limits.enforce_count_limit(photo_files, "project_photos", _access)
            if _photo_limit_msg:
                st.warning(_photo_limit_msg)
        st.session_state.project_photo_bytes = [f.getvalue() for f in photo_files]
        st.session_state._photo_files_sig = _files_signature(photo_files)
    if st.session_state.project_photo_bytes:
        retained = i18n.t("upload_retained_suffix") if not photo_files else ""
        pcol1, pcol2 = st.columns([8, 1])
        with pcol1:
            st.caption(i18n.t("upload_photos_loaded_caption", n=len(st.session_state.project_photo_bytes), retained=retained))
        with pcol2:
            if st.button(i18n.t("upload_clear_all_button"), key="clear_photos", help=i18n.t("upload_clear_photos_help"), type="primary"):
                st.session_state.project_photo_bytes = []
                st.session_state._photo_files_sig = None
                st.session_state._photo_uploader_version += 1
                st.rerun()

    if st.session_state.get("_branding_uploader_version") is None:
        st.session_state._branding_uploader_version = 0
    branding_files = st.file_uploader(
        i18n.t("upload_branding_label"), type=["png", "jpg", "jpeg"], accept_multiple_files=True,
        key=f"upload_branding_{st.session_state._branding_uploader_version}",
    )
    if branding_files and _files_signature(branding_files) != st.session_state.get("_branding_files_sig"):
        if IS_SAAS_MODE and current_user and not _access.get("unlimited"):
            branding_files, _branding_limit_msg = limits.enforce_count_limit(branding_files, "branding_images", _access)
            if _branding_limit_msg:
                st.warning(_branding_limit_msg)
        st.session_state.branding_bytes = [f.getvalue() for f in branding_files]
        st.session_state._branding_files_sig = _files_signature(branding_files)
    if st.session_state.branding_bytes:
        retained = i18n.t("upload_retained_suffix") if not branding_files else ""
        bcol1, bcol2 = st.columns([8, 1])
        with bcol1:
            st.caption(i18n.t("upload_branding_loaded_caption", n=len(st.session_state.branding_bytes), retained=retained))
        with bcol2:
            if st.button(i18n.t("upload_clear_all_button"), key="clear_branding", help=i18n.t("upload_clear_branding_help"), type="primary"):
                st.session_state.branding_bytes = []
                st.session_state._branding_files_sig = None
                st.session_state._branding_uploader_version += 1
                st.rerun()

    st.divider()
    st.markdown(i18n.t("upload_refprojects_heading"))
    st.caption(i18n.t("upload_refprojects_caption"))
    raw_refs_text = (st.session_state.company_material_text.get("project_references") or "").strip()
    if not raw_refs_text:
        st.info(i18n.t("upload_refprojects_upload_first_info"))
    elif not st.session_state.reference_projects:
        # Uploading the raw material only extracts its text -- it does NOT
        # automatically turn into reference project entries. That second
        # step (the button right below) is easy to miss, since the upload
        # widget itself shows a reassuring green "X file(s) stored"
        # confirmation that looks like the whole job is done. Called out
        # explicitly here so "I uploaded my references but nothing's
        # happening" has an obvious next step instead of looking broken.
        st.info(i18n.t("upload_refprojects_draft_hint_info"))

    refs_ai_ready = bool(st.session_state.ai_config.get("api_key")) and bool(raw_refs_text) and _current_project_already_paid()
    if st.button(i18n.t("upload_draft_refprojects_button"), disabled=not refs_ai_ready,
                 help=None if refs_ai_ready else (
                     _ai_block_reason() if not _current_project_already_paid()
                     else i18n.t("upload_draft_refprojects_help", ai_hint=_AI_HINT_CLAUSE)
                 ), type="primary"):
        with st.spinner(i18n.t("upload_draft_refprojects_spinner")):
            try:
                _record_ai_click()
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
                st.success(i18n.t("upload_refprojects_drafted_success", n=len(drafted)))
                if not analysis_for_context:
                    st.info(i18n.t("upload_refprojects_no_analysis_info"))
            except Exception as exc:
                _show_error(i18n.t("upload_refprojects_drafting_failed_error"), exc)

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
        with st.expander(f"{proj.title or i18n.t('upload_refproject_untitled', n=i + 1)}" + (f" -- {proj.client}" if proj.client else ""), expanded=False):
            proj.title = st.text_input(i18n.t("upload_ref_project_title_label"), value=proj.title, key=f"ref_title_{i}")
            proj.client = st.text_input(i18n.t("upload_ref_client_label"), value=proj.client, key=f"ref_client_{i}")
            proj.description = st.text_area(i18n.t("upload_ref_description_label"), value=proj.description, key=f"ref_desc_{i}", height=110)
            proj.relevance_text = st.text_area(i18n.t("upload_ref_relevance_label"), value=proj.relevance_text, key=f"ref_rel_{i}", height=70)
            options = sorted(set(_known_personnel_names) | set(proj.personnel_involved))
            proj.personnel_involved = st.multiselect(
                i18n.t("upload_ref_personnel_label"), options,
                default=[n for n in proj.personnel_involved if n in options], key=f"ref_pers_{i}",
            )
            photo = st.file_uploader(i18n.t("upload_ref_photo_label"), type=["png", "jpg", "jpeg"], key=f"ref_photo_{i}")
            if photo is not None:
                st.session_state.reference_project_photos[photo_key_for(proj, proj.title)] = photo.getvalue()
            existing_ref_photo = st.session_state.reference_project_photos.get(photo_key_for(proj, proj.title))
            if existing_ref_photo:
                st.image(existing_ref_photo, width=160)
            if st.button(i18n.t("upload_ref_remove_button"), key=f"ref_remove_{i}", type="primary"):
                _remove_ref_index = i
    if _remove_ref_index is not None:
        st.session_state.reference_projects.pop(_remove_ref_index)
        st.rerun()

    with st.form("add_reference_project_form", clear_on_submit=True):
        st.markdown(i18n.t("upload_add_ref_manual_heading"))
        new_ref_title = st.text_input(i18n.t("upload_ref_project_title_label"))
        new_ref_client = st.text_input(i18n.t("upload_ref_client_label"))
        if st.form_submit_button(i18n.t("upload_add_ref_button"), type="primary") and new_ref_title.strip():
            st.session_state.reference_projects.append(
                reference_projects_module.ReferenceProject(title=new_ref_title.strip(), client=new_ref_client.strip())
            )
            st.rerun()


# ---------------------------------------------------------------------------
# Tab 3: Tender Analysis
# ---------------------------------------------------------------------------

with tabs[2]:
    st.subheader(i18n.t("analysis_subheader"))
    st.caption(i18n.t("analysis_caption"))

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
            st.info(i18n.t("analysis_need_project_name_info"))
        else:
            st.info(i18n.t("analysis_need_brief_and_ai_info", ai_hint=_AI_HINT_CLAUSE))

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

    # Part B / B2: re-running Tender Analysis on a project that's ALREADY
    # been recorded (see _already_counted above) used to always be free --
    # correct for the idempotent "same project + same document, don't
    # double-charge" case, but wrong once B2 redefined a "pass" as one full
    # generation cycle: a trial-funded project gets exactly one pass, ever
    # (Part B), and a paid project's re-runs draw down its 5-pass allowance
    # (Part B2), not an unconditional free re-run forever. Both checks are
    # no-ops (False/unlimited) outside SaaS mode or for UNLIMITED_ACCOUNTS.
    _repeat_funded_by = auth.project_funded_by(current_user, _project_key) if (IS_SAAS_MODE and current_user and _already_counted) else ""
    _repeat_is_trial = _repeat_funded_by in ("", "trial")
    _repeat_passes = (
        auth.project_passes_status(current_user, _project_key)
        if (IS_SAAS_MODE and current_user and _already_counted and not _repeat_is_trial and not _access.get("unlimited"))
        else {"has_passes": False, "purchased": 0, "used": 0, "remaining": 0}
    )
    # A trial-funded project's one pass was already spent by the run that
    # set _already_counted True in the first place -- any further click is
    # a second pass it never had. A paid project can re-run as long as
    # project_passes_status shows any remaining; once that hits 0, it needs
    # a top-up (see the "Buy 5 more passes" button below), same as running
    # out of the trial needs an upgrade.
    _repeat_blocked = (
        IS_SAAS_MODE and current_user and _already_counted and not _access.get("unlimited")
        and (_repeat_is_trial or _repeat_passes["remaining"] <= 0)
    )

    # Trial page-cap hard block (Part 1) and the account-level AI-spend
    # ceiling / fair-use rate limit (Parts 2-3, see modules/limits.py and
    # _ai_gate_msg computed once per script run in 00_init.py) -- both
    # apply to Tender Analysis too, alongside the bid-count paywall above.
    # UNLIMITED_ACCOUNTS bypass both (_ai_gate_msg is already None for them;
    # tender_page_cap_message() returns None for UNLIMITED_ACCOUNTS and any
    # paid tier under its own 300-page ceiling -- Audit Round 2, Part 8
    # added that paid ceiling; it used to be trial-only despite the module
    # comment claiming otherwise).
    _page_cap_msg = None
    _page_soft_warn_msg = None
    if IS_SAAS_MODE and current_user and st.session_state.tender_extracted and st.session_state.tender_extracted.page_count:
        _page_cap_msg = limits.tender_page_cap_message(st.session_state.tender_extracted.page_count, _access)
        # Non-blocking -- deliberately NOT folded into _extra_blocked_msg
        # below, so it never disables the Run button. Only ever returns
        # something when _page_cap_msg above is None (200-300 pages, paid,
        # not yet at the hard stop), so the two are never shown together.
        _page_soft_warn_msg = limits.tender_page_soft_warn_message(st.session_state.tender_extracted.page_count, _access)
    _extra_blocked_msg = _page_cap_msg or _ai_gate_msg
    if _page_soft_warn_msg:
        st.info(_page_soft_warn_msg)

    if _repeat_blocked and _repeat_is_trial:
        # Part B: the free trial's one-and-only generation pass on this
        # project has already been spent -- re-running analysis again
        # (even on the exact same document) now needs a paid bid, unlike
        # the old unconditional "same project, always free" behaviour.
        # Audit fix Part 1a: pass THIS project's key through so a $50
        # purchase from here actually unlocks it (see
        # auth.apply_project_bid_topup()) instead of landing as an
        # unrelated account credit that leaves this project stuck forever.
        st.warning(i18n.t("free_tier_generate_used"))
        _render_upgrade_buttons(current_user, key_prefix="_tab3_repeat_trial",
                                 already_subscribed=_access["subscribed"] or _access["past_due"],
                                 topup_project_key=_project_key)
    elif _repeat_blocked:
        # Paid project, but its 5-pass allowance (Part B2) is used up.
        st.warning(i18n.t("passes_exhausted"))
        # Audit fix Part 8: was a two-step button-then-link_button flow --
        # the exact vanishing-link bug 00_init.py's own comment documents
        # and _render_upgrade_buttons() was rewritten to avoid (see that
        # function's docstring), and the same fix already applied to this
        # same button in 80_export.py. A single link_button, backed by the
        # cached-URL helper, removes the round trip and stops minting a
        # fresh Stripe Checkout Session on every rerun.
        try:
            _checkout_url = _get_or_create_checkout_url(current_user, "bid", topup_project_key=_project_key)
            st.link_button(i18n.t("passes_topup_button"), _checkout_url, key="_tab3_passes_topup_btn", type="primary")
        except Exception as exc:
            _show_error(i18n.t("analysis_checkout_failed_error"), exc)
    elif _trial_blocked or (IS_SAAS_MODE and current_user and _access["limit_reached"] and not _already_counted):
        if _access["past_due"]:
            # Same monthly quota as an active subscriber (see
            # auth.get_access_status), but the actionable fix here is fixing
            # payment, not buying more -- lead with that.
            st.warning(i18n.t("analysis_past_due_warning", limit=_access['subscription_bid_limit']))
        elif _access["subscribed"]:
            st.warning(i18n.t("analysis_subscribed_limit_warning", limit=_access['subscription_bid_limit']))
        else:
            st.warning(i18n.t("analysis_trial_exhausted_warning", limit=_access['trial_limit']))
        _render_upgrade_buttons(current_user, key_prefix="_tab3",
                                 already_subscribed=_access["subscribed"] or _access["past_due"])
    elif _extra_blocked_msg:
        # A distinct reason from the bid-count paywall above (which doesn't
        # apply here -- the account may have plenty of bid capacity left):
        # too many pages for the trial, or the account-level AI-spend
        # ceiling / fair-use rate limit. Never shown together with the
        # paywall message above (that `elif`) since one blocked reason is
        # already enough explanation.
        st.warning(_extra_blocked_msg)
        if _page_cap_msg:
            _render_upgrade_buttons(current_user, key_prefix="_tab3_pagecap",
                                     already_subscribed=_access["subscribed"] or _access["past_due"])

    # Tell people exactly what clicking the button below is about to spend --
    # previously nothing here said this consumes the account's one free
    # trial bid, so someone testing with a throwaway/wrong file could burn
    # it by accident and land on the paywall with no idea why. Skipped
    # entirely for re-runs of the exact same project+document (see
    # _already_counted above -- those are free) and for unlimited accounts.
    if IS_SAAS_MODE and current_user and ready and not _trial_blocked and not _repeat_blocked and not _access["unlimited"]:
        if _already_counted and not _repeat_is_trial:
            # Part B2: a paid project's re-run now spends one of its 5
            # passes (not free forever the way it used to be) -- say so,
            # same spirit as the "this will use 1 bid" captions below for a
            # first run.
            st.caption(i18n.t("passes_remaining_caption",
                               remaining=_repeat_passes["remaining"], total=_repeat_passes["purchased"])
                       + " -- running analysis again will use one.")
        elif _access["subscribed"] or _access["past_due"]:
            if _access["subscription_bids_remaining"] > 0:
                st.caption(i18n.t("analysis_subscription_bids_caption", remaining=_access['subscription_bids_remaining']))
            else:
                st.caption(i18n.t("analysis_payg_caption", credits=_access['bid_credits']))
        elif _access["trial_remaining"] > 0:
            st.caption(i18n.t("analysis_trial_remaining_caption", remaining=_access['trial_remaining']))
        else:
            st.caption(i18n.t("analysis_payg_caption", credits=_access['bid_credits']))

    if st.button(i18n.t("analysis_run_button"), type="primary", disabled=not ready or _trial_blocked or _repeat_blocked or bool(_extra_blocked_msg)):
        # Audit fix Part 1c: for a repeat run on an already-funded PAID
        # project, spend the pass ATOMICALLY and BEFORE the (expensive,
        # billable) AI call runs -- see auth.consume_project_pass()'s
        # guarded UPDATE. The `disabled=` computation above already
        # refuses this click when _repeat_blocked is True, but that check
        # and this one are two different script runs: two browser tabs (or
        # a double-click) can both render the button enabled while exactly
        # one pass remains, and both reach this handler. Only one of the
        # two atomic UPDATEs below can actually match "passes_used <
        # passes_purchased" and increment -- the other gets False and is
        # turned away here, before it ever starts the AI call, instead of
        # both running the analysis and only discovering afterward (as the
        # old read-check-increment-after-the-fact version did) that one of
        # them had nothing left to spend.
        _pass_ok = True
        if IS_SAAS_MODE and current_user and _already_counted and not _repeat_is_trial and not _access.get("unlimited"):
            _pass_ok = auth.consume_project_pass(current_user, _project_key)
            if not _pass_ok:
                st.warning(i18n.t("passes_exhausted"))

        if _pass_ok:
            extracted = st.session_state.tender_extracted
            progress = st.progress(0.0, text=i18n.t("analysis_progress_text"))

            def _progress_cb(done, total):
                progress.progress((done + 1) / max(total, 1), text=i18n.t("analysis_progress_detail", done=done + 1, total=total))

            try:
                _record_ai_click()
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
                    kwargs={
                        "tables": getattr(extracted, "tables", None),
                        "output_language": st.session_state.get("output_language", "en"),
                    },
                    progress=progress,
                    queued_text=i18n.t("analysis_queued_text"), running_text=i18n.t("analysis_progress_text"),
                    inline_extra_kwargs={"progress_callback": _progress_cb},
                    queue_func=job_queue.run_tender_analysis_job,
                    queue_args=(extracted.text, extracted.annotations, _redacted_ai_config),
                )
                st.session_state.analysis = analysis
                progress.progress(1.0, text=i18n.t("drafting_done_text"))
                st.success(i18n.t("analysis_complete_success"))
                if IS_SAAS_MODE and current_user:
                    if _already_counted:
                        # Part B2: this is a repeat run on an already-funded
                        # PAID project (a trial-funded or first-ever repeat
                        # would have been _repeat_blocked above, and the button
                        # disabled). The pass itself was already spent
                        # ATOMICALLY, BEFORE this AI call ran (see the
                        # consume_project_pass() call above) -- nothing
                        # further to charge here.
                        pass
                    else:
                        auth.record_proposal_usage(current_user, _project_key, st.session_state.project_name)
                        # Signup-funnel step 3 (activation): a bid actually analysed.
                        analytics.track_event("Bid Analysed")
                    # Part C: remember this as the last-confirmed PAID identity
                    # (no-op for a trial-funded run) -- see
                    # _maybe_snapshot_paid_identity()'s docstring for why this
                    # has to happen right HERE (the moment a paid generation
                    # cycle actually completes) rather than on every rerun.
                    _maybe_snapshot_paid_identity()
            except Exception as exc:
                _show_error(i18n.t("analysis_failed_error"), exc)

    analysis = st.session_state.analysis
    if analysis:
        if getattr(st.session_state.tender_extracted, "ocr_used", False):
            st.warning(i18n.t("analysis_ocr_warning", ocr_tag=document_processor.OCR_VERIFY_TAG))
        st.markdown(i18n.t("analysis_project_scope_heading"))
        st.write(analysis.project_scope or i18n.t("analysis_not_extracted"))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(i18n.t("analysis_client_objectives_heading"))
            st.write(analysis.client_objectives or i18n.t("analysis_none_extracted"))
            st.markdown(i18n.t("analysis_mandatory_requirements_heading"))
            st.write(analysis.mandatory_requirements or i18n.t("analysis_none_extracted"))
            st.markdown(i18n.t("analysis_deliverables_heading"))
            st.write(analysis.deliverables or i18n.t("analysis_none_extracted"))
        with col2:
            st.markdown(i18n.t("analysis_submission_date_label", text=analysis.submission_date or i18n.t("analysis_not_stated")))
            st.markdown(i18n.t("analysis_total_page_limit_label", text=analysis.total_page_limit or i18n.t("analysis_not_stated")))
            st.markdown(i18n.t("analysis_fee_cap_label", text=analysis.fee_cap or i18n.t("analysis_not_stated")))
            st.markdown(i18n.t("analysis_uses_named_criteria_label", answer=(i18n.t("analysis_yes") if analysis.uses_named_selection_criteria else i18n.t("analysis_no"))))
            st.markdown(i18n.t("analysis_required_forms_heading"))
            st.write(analysis.required_forms or i18n.t("analysis_none_extracted"))

        st.markdown(i18n.t("analysis_evaluation_criteria_heading"))
        if analysis.evaluation_criteria:
            st.dataframe(
                [{
                    i18n.t("analysis_col_code"): c.criterion_code or "-", i18n.t("analysis_col_name"): c.name,
                    i18n.t("analysis_col_weighting"): f"{c.detected_weighting:.0f}%" if c.detected_weighting is not None else (i18n.t("analysis_mandatory_gate") if c.is_mandatory_gate else "-"),
                    i18n.t("analysis_col_page_limit"): c.page_limit or "-", i18n.t("analysis_col_format_rules"): c.format_requirements or "-",
                } for c in analysis.evaluation_criteria],
                use_container_width=True,
            )
        else:
            st.write(i18n.t("analysis_no_evaluation_criteria"))

        if analysis.user_flagged_items:
            st.markdown(i18n.t("analysis_flagged_items_heading"))
            for item in analysis.user_flagged_items:
                st.markdown(f"- **p.{item.get('page','?')}:** {item.get('note')} — _{item.get('context','')[:150]}_")

        if analysis.risks:
            st.markdown(i18n.t("analysis_risks_heading"))
            st.write(analysis.risks)

        if analysis.analysis_warnings:
            st.warning(i18n.t("analysis_extraction_warnings_prefix") + "\n".join(f"- {w}" for w in analysis.analysis_warnings))



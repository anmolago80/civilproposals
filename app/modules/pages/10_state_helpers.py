# modules/pages/10_state_helpers.py -- one segment of the CivilProposals app script.
# Session-state defaults and every shared helper: job-queue-or-inline runner, project identity/key, paid-status checks, structure rebuild, save/load/autosave.
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
# Session state helpers
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "project_name": "", "client_name": "", "tender_name": "",
        "submission_date_input": "", "bidder_name": "", "proposal_theme": "Corporate",
        "project_type": PROJECT_TYPES[0],
        "tender_extracted": None,
        "company_material_text": {},
        "company_material_files": {},  # {category: {filename: extracted_text}} -- per-file, so a
                                        # re-upload can update/remove individual files (see the
                                        # Upload Documents tab) instead of replacing the whole category.
        "company_uploaded_flags": {},
        "returnable_schedule_files": {},  # {filename: raw bytes} -- returnable schedules from a package ZIP (see package_intake)
        "project_photo_bytes": [],
        "branding_bytes": [],
        # Pre-filled from ANTHROPIC_API_KEY in a local .env file, if present (see
        # load_dotenv() at the top of this file) -- so this tab doesn't need to be
        # re-filled in on every launch. Still fully editable/overridable below.
        "ai_config": {
            "provider": "Anthropic Claude",
            "api_key": _ENV_ANTHROPIC_KEY,
            "model": ai_interface.get_default_model("Anthropic Claude") if _ENV_ANTHROPIC_KEY else "",
            "endpoint": "",
        },
        "copilot_client_id": "", "copilot_tenant_id": "",
        "copilot_access_token": "", "copilot_token_cache": "", "copilot_username": "",
        # Whether the sidebar's Claude API key field should persist to the local
        # .env file -- defaults to on if a key was already loaded from .env at
        # startup (i.e. it was remembered before), off otherwise.
        "_remember_claude_key": bool(_ENV_ANTHROPIC_KEY),
        "analysis": None,
        "weighted_criteria": None,
        "allocations": None,
        "sections": None,
        "guidance_notes": None,
        "compliance_items": None,
        "gap_items": None,
        "drafts": None,
        "executive_summary": None,
        "team_intro": None,
        "experience_intro": None,
        "project_differentiator": "",
        "project_sales_pitch": "",
        "pitch_review": None,
        "pitch_questions": None,
        "tender_summary_buffer": None,
        "graphics": None,
        "weighting_chart_png": None,
        "fee_estimates": None,
        "docx_buffer": None,
        "quotes": [],
        "section_divider_config": {},
        "divider_images": {},
        "cover_hero_png": None,
        # Small Scope pack (short, brief-driven response pack) -- one more option within
        # the same pipeline, not a separate app. See PROPOSAL_FORMAT_LABELS above.
        "proposal_format": "formal",
        # Which proposal_format st.session_state.sections was actually built under --
        # see _structure_format_stale(). None until Proposal Structure (tab 4) is
        # generated at least once.
        "_sections_built_format": None,
        # Sign-off details only -- the cover page/footer already carry project, client,
        # and bidder details, so no separate recipient/ref/date/subject fields are needed.
        "letter_sender_name": "", "letter_sender_title": "",
        "letter_sender_phone": "", "letter_sender_email": "",
        # Read by returnable_schedules.build_fill_data for the "Registered
        # Office"/"Business Address" labels on the client's own forms.
        # Deliberately NOT part of the letter sign-off block -- see the note
        # in export_docx._build_letter_signoff.
        "letter_sender_address": "",
        "terms_of_engagement_text": "",
        "team_members": [],
        "team_photos": {},
        "team_bio_warnings": [],
        # Resourcing plan + org chart (Team & Resourcing tab). resource_plan is a
        # list of resourcing.ResourceAssignment; org_chart_png is the generated PNG.
        "resource_plan": [],
        "resource_extra_names": [],
        "dismissed_disciplines": [],
        # AI-suggested "include in proposal" verdicts for the Key Personnel pen pics
        # (Team & Resourcing tab) -- {slot: {"recommended": bool, "reason": str}},
        # from resourcing.suggest_proposal_inclusion(). Empty until the "Suggest
        # which personnel to include" button is run; purely advisory -- the actual
        # include/exclude state lives on each ResourceAssignment.include_in_proposal.
        "personnel_inclusion_suggestions": {},
        "cv_library_filenames": [],
        "cv_extracted_names": [],
        "org_chart_png": None,
        "body_font": "Arial",
        # Key-personnel headshots (Team & Resourcing tab), keyed by person_name --
        # same pattern as team_photos. None means "not run yet" is not applicable
        # here (it's always a dict, possibly empty).
        "personnel_photos": {},
        # Reference projects (Upload Documents tab) -- structured Section 2 content
        # drafted/revised from the "Project references" upload; see
        # modules/reference_projects.py. None means the drafting step hasn't run
        # yet (distinct from "ran and found nothing"); reference_project_photos is
        # always a dict, keyed by reference project title.
        "reference_projects": None,
        "reference_project_photos": {},
        "reference_project_warnings": [],
        # First-pass manual discipline fee build-up (Fee tab). List of
        # resourcing.DisciplineFeeLine; always includes Project Management.
        "discipline_fee_lines": [],
        # Disciplines the user explicitly removed from the Fee Estimate table --
        # never re-added by the brief-sync merge (separate from
        # dismissed_disciplines, which is the Team & Resourcing tab's own list).
        "dismissed_fee_disciplines": [],
        # Bump counters folded into the discipline/scope-item fee data_editor
        # widget keys below -- st.data_editor with a fixed key ignores its
        # `data` argument on every rerun after the first (the widget owns its
        # state once created), so merging a newly-extracted discipline or
        # scope item into the underlying session_state list alone is not
        # enough: the editor keeps showing whatever it first rendered,
        # forever, even across a fresh Tender Analysis run. Bumping the
        # version whenever a genuinely new row gets merged in forces a fresh
        # widget instance (which picks up the merged data) without touching
        # the key on every ordinary rerun, which would instead throw away
        # in-progress edits. See the merge blocks on the Fee Estimate tab.
        "_discipline_fee_editor_version": 0,
        "_scope_fee_editor_version": 0,
        "_large_scope_fee_editor_version": 0,
        # Cache for the discipline fee tables' Excel export + pie chart, so a
        # fragment rerun that doesn't change the underlying hours/rates
        # doesn't waste time (or widen the edit-commit race window) redoing
        # that work -- see the discipline fee table fragments below.
        "_disc_fee_cache_sig": None,
        "_disc_fee_cache_xlsx": None,
        "_disc_fee_cache_pie": None,
        "_letter_disc_fee_cache_sig": None,
        "_letter_disc_fee_cache_xlsx": None,
        "_letter_disc_fee_cache_pie": None,
        # Deferred-apply state for the discipline fee tables -- the rebuild
        # (dedup/dismiss logic) and the cache above only run when the user
        # explicitly ticks a "done entering data" box, rather than on every
        # keystroke-commit. See the checkbox handling in the discipline fee
        # table fragments below for why.
        "_disc_fee_apply_tick": False,
        "_disc_fee_apply_tick_seen": False,
        "_disc_fee_last_applied_editor_sig": None,
        "_letter_disc_fee_apply_tick": False,
        "_letter_disc_fee_apply_tick_seen": False,
        "_letter_disc_fee_last_applied_editor_sig": None,
        # Same deferred-apply pattern, extended to the other three fee-editing
        # tables (scope item / deliverable fee build-up, both pack sizes, and
        # the discipline fee % split, both pack sizes).
        "_scope_fee_apply_tick": False,
        "_scope_fee_apply_tick_seen": False,
        "_scope_fee_last_applied_editor_sig": None,
        "_large_scope_fee_apply_tick": False,
        "_large_scope_fee_apply_tick_seen": False,
        "_large_scope_fee_last_applied_editor_sig": None,
        "_pct_fee_apply_tick": False,
        "_pct_fee_apply_tick_seen": False,
        "_pct_fee_last_applied_editor_sig": None,
        "_letter_pct_fee_apply_tick": False,
        "_letter_pct_fee_apply_tick_seen": False,
        "_letter_pct_fee_last_applied_editor_sig": None,
        "scope_item_fees": [],
        "fee_seed_total": 0.0,
        # Manually-entered total project fee for the indicative benchmark split
        # below -- overrides the brief's stated fee cap (if any) so the user can
        # still see a $ split even when the brief never states a ceiling.
        "fee_estimate_manual_total": 0.0,
        # Small Scope pack's own total for its "Discipline fee split (%)" table --
        # separate from fee_estimate_manual_total (Large Scope's own, unrelated
        # override) since this one auto-prepopulates from the discipline fee
        # build-up total the first time it's used (0.0 = "not yet set"), then
        # stays independently editable. See the Fee Estimate tab.
        "letter_fee_total_override": 0.0,
        # The reviewed methodology stage grid (methodology_stages.MethodologyStage
        # list). None means "the stage drafter has never been run" -- distinct
        # from [] which would mean "run, and produced nothing".
        "methodology_stages": None,
        # Whether the user has confirmed their firm issues Work Verification
        # Records. Never assumed: the WVR line used to print as fact in every
        # methodology export without the app ever being told.
        "methodology_wvr_confirmed": False,
        "program_num_weeks": 6,
        "program_schedule": {},
        "program_week_labels": [],
        # The user's own anticipated start date for the delivery program
        # (datetime.date | None). Optional: set it and every week header
        # becomes a real calendar date via program_schedule.week_labels().
        # Never derived from the brief -- a guessed start date in a program
        # table would be an invented fact.
        "program_start_date": None,
        # Save/Load Project bookkeeping (sidebar) -- not project content itself.
        "_project_save_bytes": None,
        "_last_loaded_project_name": "",
        "_autosave_enabled": True,
        "_last_autosave_ts": 0.0,
        "_last_autosave_path": "",
        "_last_autosave_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _run_job_or_inline(job_type, func, args=(), kwargs=None, progress=None,
                        queued_text="Queued...", running_text="Working...",
                        inline_extra_kwargs=None, queue_func=None, queue_args=None):
    """
    Runs func(*args, **kwargs) either in the background job queue (see
    modules/job_queue.py) or inline in this process, and either way blocks
    until it's done and returns func's return value -- every call site
    keeps its existing "click button, wait, see result" behaviour. The only
    thing that changes is WHERE the AI-call/CPU time is actually spent.

    The queue is used only when all of these are true: this is a logged-in
    SaaS user (current_user is set -- local/dev use with SAAS_MODE=false
    has no account to own a job), AND a Redis-backed queue is actually
    configured (job_queue.redis_available()) -- i.e. the worker service
    from DEPLOY.md's "Background jobs" section has been deployed. Otherwise
    this falls back to calling func directly, exactly as every one of these
    call sites always worked before background jobs existed, using
    inline_extra_kwargs for anything that only makes sense in-process (a
    live progress_callback closure can't be pickled across the process
    boundary to a worker, so it's never passed to the queued path).

    queue_func/queue_args let a call site enqueue a DIFFERENT function/args
    than the ones it runs inline with -- used by both current call sites to
    enqueue a job_queue.run_*_job() wrapper with a redacted ai_config
    (api_key="") instead of func/args' real one, so the real server
    Anthropic key never ends up pickled into Redis (see job_queue.py's
    docstring). Falls back to func/args when not given, so this stays a
    no-op for any future call site that doesn't need the distinction.

    Deliberately never a hard dependency on the queue: turning it on is
    just setting REDIS_URL and deploying the worker service, nothing here
    has to change, and this app never breaks just because that hasn't
    happened yet.
    """
    kwargs = kwargs or {}
    use_queue = IS_SAAS_MODE and current_user and job_queue.redis_available()

    if not use_queue:
        return func(*args, **kwargs, **(inline_extra_kwargs or {}))

    enqueue_func = queue_func or func
    enqueue_args = args if queue_args is None else queue_args
    enqueue_kwargs = dict(kwargs)
    if queue_func is not None:
        # Both job_queue.run_*_job wrappers accept usage_context -- plain
        # strings attributing the job's AI calls to this user/project for
        # per-bid cost logging (db.AiCallLog). Only added when a wrapper is
        # in use: a future call site that enqueues its function directly
        # shouldn't get a kwarg it never asked for.
        enqueue_kwargs["usage_context"] = {
            "user_id": current_user.id,
            "project_key": _current_project_key(),
            "project_name": st.session_state.get("project_name", ""),
            "purpose": job_type,
        }
    job_id = job_queue.enqueue(current_user.id, job_type, enqueue_func, *enqueue_args, **enqueue_kwargs)
    if progress:
        progress.progress(0.05, text=queued_text)

    # Hard ceiling on how long this waits, in case a job is enqueued but
    # never picked up (e.g. the worker service -- see modules/worker.py --
    # is down or was never deployed) or somehow never resolves. Without
    # this, that "queued" status is indistinguishable from "still working"
    # forever, and the caller's `while True` would poll indefinitely with
    # the progress bar stuck creeping toward 90% -- which, to whoever's
    # sitting there watching their one free trial bid, looks exactly like
    # the product being broken, not like a transient infra problem. Set
    # comfortably above job_queue.JOB_TIMEOUT_SECONDS (RQ's own 15-minute
    # execution ceiling once a worker actually starts the job) so a
    # legitimately long-running job is never preempted before RQ itself
    # would have given up on it.
    MAX_WAIT_SECONDS = 20 * 60
    elapsed = 0.0
    poll_interval = 1.5
    while elapsed < MAX_WAIT_SECONDS:
        status = job_queue.get_status(job_id, current_user.id)
        if status["status"] == "finished":
            return status["result"]
        if status["status"] in ("failed", "not_found"):
            raise RuntimeError(status["error"] or "The background job failed.")
        if progress:
            # Indeterminate-ish: creeps toward 90% over ~3 minutes rather
            # than claiming a precision this polling loop doesn't have --
            # queued jobs have no live per-chunk/per-section count to show
            # (see this function's docstring), just "still working".
            progress.progress(min(0.05 + elapsed / 180.0, 0.9), text=running_text)
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise RuntimeError(
        "This is taking much longer than expected and may mean the background worker is "
        "offline. Nothing was charged for this attempt beyond what the trial/subscription "
        "gate already checked -- try again in a few minutes, and contact "
        "hello@civilproposals.com if it keeps happening."
    )


def _ocr_export_note() -> str | None:
    """The "OCR-derived -- verify carefully" notice for exported documents
    (see export_docx._add_ocr_notice), or None when none of the brief's text
    came from OCR. Kept here so all four export call sites share one wording."""
    _ext = st.session_state.get("tender_extracted")
    if not getattr(_ext, "ocr_used", False):
        return None
    pages = getattr(_ext, "ocr_pages", []) or []
    page_part = f" (page {', '.join(str(p) for p in pages[:12])}{' and more' if len(pages) > 12 else ''})" if pages else ""
    return (
        f"Parts of the tender brief this pack is based on were read with text recognition "
        f"(OCR) from scanned pages{page_part}. {document_processor.OCR_VERIFY_TAG}: OCR can "
        f"misread numbers, dates, and names -- verify extracted requirements, figures, and "
        f"names against the original brief before this document goes anywhere near a "
        f"submission. Delete this notice once verified."
    )


def _project_info() -> dict:
    return {
        "project_name": st.session_state.project_name,
        "client_name": st.session_state.client_name,
        "tender_name": st.session_state.tender_name,
        "submission_date": st.session_state.submission_date_input,
        "bidder_name": st.session_state.bidder_name,
        "proposal_theme": st.session_state.proposal_theme,
        "project_type": st.session_state.project_type,
    }


def _current_project_key() -> str:
    """Same identity/hash scheme as the Tender Analysis tab's own
    _project_key (see that tab's comment for why the brief's own text is
    hashed into it, not just the typed names) -- pulled out here so every
    downstream/auxiliary AI feature can check the SAME project's paid
    status without duplicating this logic at every call site."""
    _brief_text = st.session_state.tender_extracted.text if st.session_state.tender_extracted else ""
    _brief_hash = hashlib.sha256(_brief_text.encode("utf-8")).hexdigest()[:16] if _brief_text else ""
    return (
        f"{st.session_state.project_name}|{st.session_state.tender_name}|"
        f"{st.session_state.client_name}|{_brief_hash}"
    ).strip("|")


def _current_project_already_paid() -> bool:
    """True once THIS project has actually had a bid spent on it via
    auth.record_proposal_usage() -- i.e. Tender Analysis has genuinely run
    (and been paid/trialled/subscribed-for) for it, not just that the
    account currently HOLDS some unspent capacity somewhere.

    Every downstream/auxiliary AI feature below (CV name extraction,
    discipline re-scan, team bios, fee benchmark refresh, draft generation,
    exec summary, pitch review) gates on THIS, in addition to or instead of
    _access["allowed"], for two opposite reasons that both trace back to
    the same fix:
      - _access["allowed"] alone was too PERMISSIVE: it only means "this
        account has some capacity somewhere" and never changes just because
        one of these particular calls is made (nothing here decrements
        anything the way Tender Analysis does) -- so an account sitting on
        one never-spent trial bid could hammer CV extraction / discipline
        re-scan / bios / benchmark refresh an unlimited number of times,
        forever, without ever actually running (or paying for) a Tender
        Analysis on any project.
      - _access["allowed"] alone was also too RESTRICTIVE right after the
        trial bid actually gets spent: the instant Tender Analysis consumes
        the account's one trial bid, _access["allowed"] flips to False for
        the whole account, which used to block draft generation / exec
        summary / pitch review even on the SAME project that bid was just
        spent analysing -- so a trial user could see an analysis and then
        immediately hit a paywall before ever seeing a draft, contradicting
        the "your first full bid gets you a drafted proposal pack" promise
        (see the welcome email).
    Checking "has THIS specific project already been paid for" instead of
    "does the account have spare capacity right now" fixes both at once:
    once you've paid to analyse a project, everything else about producing
    THAT proposal is included, and nothing about a project you haven't paid
    for yet is.

    Unlimited accounts (auth.UNLIMITED_ACCOUNTS) and non-SaaS/local use
    always pass -- same as everywhere else that checks _access."""
    if not IS_SAAS_MODE or not current_user:
        return True
    if _access.get("unlimited"):
        return True
    _key = _current_project_key()
    if not _key:
        return False
    with db.get_session() as s:
        return s.query(db.ProposalUsage).filter(
            db.ProposalUsage.user_id == current_user.id,
            db.ProposalUsage.project_key == _key.lower(),
        ).first() is not None


def _company_materials_flags() -> dict:
    flags = {f"has_{k}": bool(st.session_state.company_material_text.get(k)) for k in COMPANY_MATERIAL_CATEGORIES}
    flags["has_project_photos"] = bool(st.session_state.project_photo_bytes)
    flags["has_company_image_library"] = bool(st.session_state.branding_bytes)
    # Firm-profile facts count as materials too -- an insurance requirement
    # is covered when the firm profile actually holds the insurance, not only
    # when a company-profile document happens to have been uploaded.
    flags.update(_firm_materials_flags())
    return flags


def _rebuild_structure():
    """Re-derive weighting -> pages -> sections -> guidance notes as one consistent chain.
    proposal_format only changes which branch build_proposal_structure() takes at the end --
    weighting and page allocation are always derived the same way from the same brief."""
    analysis = st.session_state.analysis
    weighted = weighting_engine.apply_weighting(analysis)
    allocations = page_allocation.allocate_pages(weighted, analysis)
    sections = proposal_structure.build_proposal_structure(
        analysis, weighted, allocations, proposal_format=st.session_state.proposal_format,
    )
    st.session_state.weighted_criteria = weighted
    st.session_state.allocations = allocations
    st.session_state.sections = sections
    st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(sections)
    # Remember which format these sections were built for -- see
    # _structure_format_stale() below. Without this, switching the Proposal
    # format selector (tab 1) after already generating structure leaves
    # st.session_state.sections holding the OLD format's section titles
    # (e.g. "Executive Summary"/"Relevant Experience" instead of "Project
    # Understanding"/"Methodology and Deliverables"), so _draftable_sections()
    # silently matches nothing -- drafting "succeeds" against an empty list
    # and the user sees "Draft generation complete" with nothing to show for
    # it, no error anywhere.
    st.session_state["_sections_built_format"] = st.session_state.proposal_format


def _reset_downstream_from_brief() -> None:
    """Resets every piece of state derived from the tender brief -- call this
    whenever the brief itself is replaced or cleared (see the Upload Docs
    tab: a fresh upload that changes the file signature, or the "Clear all"
    button). Without this, replacing the brief only reset tender_extracted
    itself, leaving Tender Analysis, Structure, Page Allocation, Draft
    Responses, Graphics & Design, Team & Resourcing, and Fee Estimate all
    still holding the PREVIOUS brief's results -- so the sidebar stepper
    kept showing those steps as done (green) for a brand new project that
    hadn't actually gone through them yet. Deliberately leaves Project
    Setup fields (project/client/tender name, etc.) and firm-level company
    materials (CV library, past proposals, branding) untouched -- neither
    is derived from the brief itself, so there's no reason to clear them
    when the brief changes."""
    downstream_defaults = {
        "analysis": None,
        "weighted_criteria": None,
        "allocations": None,
        "sections": None,
        "guidance_notes": None,
        "compliance_items": None,
        "gap_items": None,
        "drafts": None,
        "executive_summary": None,
        "team_intro": None,
        "experience_intro": None,
        "pitch_review": None,
        "pitch_questions": None,
        "tender_summary_buffer": None,
        "graphics": None,
        "weighting_chart_png": None,
        "fee_estimates": None,
        "docx_buffer": None,
        "divider_images": {},
        "cover_hero_png": None,
        "_sections_built_format": None,
        "resource_plan": [],
        "discipline_fee_lines": [],
        "scope_item_fees": [],
        "org_chart_png": None,
        "reference_projects": None,
        "reference_project_photos": {},
        "reference_project_warnings": [],
        "program_schedule": {},
        "program_week_labels": [],
        "personnel_photos": {},
        "personnel_inclusion_suggestions": {},
        "dismissed_disciplines": [],
        "dismissed_fee_disciplines": [],
        "fee_seed_total": 0.0,
        "fee_estimate_manual_total": 0.0,
        "letter_fee_total_override": 0.0,
    }
    for key, value in downstream_defaults.items():
        st.session_state[key] = value


def _structure_format_stale() -> bool:
    """True when sections exist but were generated under a different Proposal
    format than the one currently selected -- see the comment in
    _rebuild_structure() above for why this matters."""
    return (
        st.session_state.sections is not None
        and st.session_state.get("_sections_built_format") != st.session_state.proposal_format
    )


def _is_letter() -> bool:
    return st.session_state.proposal_format == "letter"


def _firm_profile() -> "object | None":
    """This account's firm profile, or None.

    Cached for the run: it is read by the sidebar, the project seeder and
    several exporters, and re-querying per rerun for a row that changes
    perhaps once a year is waste. Never raises -- a database hiccup must
    degrade to "no profile" (i.e. today's placeholders), not to an error
    page in the middle of a bid."""
    if "_firm_profile_cache" not in st.session_state:
        try:
            st.session_state._firm_profile_cache = firm_profile.get_profile(
                current_user.id if (IS_SAAS_MODE and current_user) else None  # noqa: F821
            )
        except Exception:
            st.session_state._firm_profile_cache = None
    return st.session_state._firm_profile_cache


def _firm_profile_is_empty() -> bool:
    return firm_profile.is_empty(_firm_profile())


def _firm_materials_flags() -> dict:
    """Firm-profile facts the compliance matrix should treat as covered."""
    profile = _firm_profile()
    return {
        "firm_profile_has_insurances": bool(firm_profile.insurances(profile)),
        "firm_profile_has_certifications": bool(firm_profile.certifications(profile)),
    }


def _firm_export_context() -> dict:
    """The firm profile as the exporters want it (see
    firm_profile.export_context) -- one bundle rather than six new keyword
    arguments on two already-long builder signatures."""
    return firm_profile.export_context(_firm_profile(), st.session_state.get("bidder_name", ""))


def _seed_project_from_firm_profile() -> None:
    """Fill this project's blank fields from the firm profile.

    Only ever writes where the project's own value is still empty. A seed
    that overwrote something typed for THIS bid would be the worst kind of
    bug in a proposal tool -- silent, and wrong in a document."""
    profile = _firm_profile()
    if profile is None:
        return
    for key, value in firm_profile.project_seed(profile).items():
        if not (st.session_state.get(key) or "").strip():
            st.session_state[key] = value
    # A firm that has recorded its QA/Work Verification commitment has
    # answered the methodology table's WVR question -- see Batch 2's honesty
    # fix. Still only a seed: unticking it on a bid sticks for that bid.
    if (getattr(profile, "qa_statement", "") or "").strip():
        st.session_state.methodology_wvr_confirmed = True


def _program_week_count() -> int:
    """How many week columns the delivery program actually has.

    Read from the schedule itself rather than from program_num_weeks: the two
    drift apart the moment someone changes the week count without pressing
    "Generate default program" again, and week labels that outnumber the
    grid's columns (or fall short of them) silently mislabel the whole
    program."""
    rows = (st.session_state.get("program_schedule") or {}).values()
    widths = [len(row) for row in rows]
    return max(widths) if widths else int(st.session_state.get("program_num_weeks") or 0)


# Small Scope pack sections that are actually free text to be AI-drafted-then-edited, same as
# every section in the Large Scope pack. The other sections (Scope of Work, Project Team, Fees,
# Program) are built from structured data the user supplies directly (scope_items already
# extracted from the brief, CV-drafted team bios, the fee table, the program grid) -- running
# them through the generic AI drafter would just waste calls on content nothing downstream uses.
LETTER_DRAFTABLE_TITLES = {"Project Understanding", "Methodology and Deliverables"}


def _draftable_sections(sections: list) -> list:
    if st.session_state.proposal_format == "letter":
        return [s for s in sections if s.title in LETTER_DRAFTABLE_TITLES]
    return sections


def _project_identifier() -> str:
    """What a local auto-save file / "Recent projects" entry gets named after.
    See local_project_store.project_identifier() -- prefers the descriptive
    project name over the tender/EOI name, which is often left generic."""
    return local_project_store.project_identifier(st.session_state.project_name, st.session_state.tender_name)


def _files_signature(files) -> tuple:
    """A cheap identity for a set of uploaded files (name + size), so we can tell
    when the uploads have actually changed and avoid re-extracting the same files
    on every Streamlit rerun (reruns fire on nearly every interaction, and
    re-parsing large PDFs each time is what makes the app feel frozen)."""
    return tuple((getattr(f, "name", ""), getattr(f, "size", None)) for f in (files or []))


def _render_resource_rows(kind: str, known_names: list) -> None:
    """Render the assign-a-person rows for the Team & Resourcing tab, for either
    the 'management' roles or the 'discipline' leads. Each row lets the user pick
    a known (CV-derived or typed) name or choose '(type a name)' to enter someone
    ad hoc; discipline rows can also be removed. Mutates st.session_state.resource_plan
    in place.

    For 'discipline' rows only, a lead can also carry any number of support
    members underneath it (e.g. "Ryan Swagemakers" added under the "Structural"
    lead, "Mat Williams") -- each with their own free-text title for this
    project (e.g. "Bridge Engineer"), since a support member's title is rarely
    just the discipline name. Support rows always render immediately after
    their lead (see resourcing.normalize_plan_disciplines, which keeps the plan
    grouped that way), indented with an "under <lead>" caption."""
    TYPE_SENTINEL = "— type a name —"
    UNASSIGNED = "(unassigned)"
    options = [UNASSIGNED] + known_names + [TYPE_SENTINEL]
    remove_index = None
    add_support_after = None  # index of the lead row to add a new support row under
    plan = st.session_state.resource_plan
    for i, a in enumerate(plan):
        if a.slot_kind != kind:
            continue
        is_support = kind == "discipline" and not a.is_lead
        cols = st.columns([3, 3, 1, 1]) if kind == "discipline" else st.columns([3, 3, 1])
        with cols[0]:
            if is_support:
                st.caption(f"↳ under {a.slot}")
                a.custom_title = st.text_input(
                    "Title", value=a.custom_title, key=f"res_title_{kind}_{i}",
                    label_visibility="collapsed",
                    placeholder="Their title on this project, e.g. Bridge Engineer",
                )
            else:
                st.markdown(f"**{a.slot}**")
        with cols[1]:
            current = (a.person_name or "").strip()
            if current and current in known_names:
                idx = options.index(current)
            elif current:
                idx = options.index(TYPE_SENTINEL)
            else:
                idx = 0
            choice = st.selectbox(
                "Assigned to", options, index=idx,
                key=f"res_sel_{kind}_{i}", label_visibility="collapsed",
            )
            if choice == TYPE_SENTINEL:
                typed = st.text_input(
                    "Name", value=current if current not in known_names else "",
                    key=f"res_txt_{kind}_{i}", label_visibility="collapsed",
                    placeholder="Type the person's name",
                )
                a.person_name = typed.strip()
                a.from_cv = False
            elif choice == UNASSIGNED:
                a.person_name = ""
                a.from_cv = False
            else:
                a.person_name = choice
                a.from_cv = choice in known_names
        if kind == "discipline":
            with cols[2]:
                if not is_support and st.button(
                    "+ member", key=f"res_addsup_{kind}_{i}", help="Add a team member under this lead",
                 type="primary"):
                    add_support_after = i
            with cols[3]:
                if st.button(
                    "✕", key=f"res_del_{kind}_{i}",
                    help="Remove this discipline (and anyone added under it)" if not is_support else "Remove this team member",
                 type="primary"):
                    remove_index = i
    if add_support_after is not None:
        lead = plan[add_support_after]
        # Insert right after the lead's existing block (the lead plus any
        # support rows already under it), so the plan stays grouped/contiguous
        # for every downstream reader (org chart, Small Scope Project Team,
        # resourcing.discipline_groups/normalize_plan_disciplines).
        insert_at = add_support_after + 1
        while (insert_at < len(plan) and plan[insert_at].slot_kind == "discipline"
               and not plan[insert_at].is_lead and plan[insert_at].slot == lead.slot):
            insert_at += 1
        plan.insert(insert_at, resourcing.ResourceAssignment(slot=lead.slot, slot_kind="discipline", is_lead=False))
        st.rerun()
    if remove_index is not None:
        removed = plan.pop(remove_index)
        if removed.is_lead:
            # Cascade: a removed lead's support rows have nothing left to be
            # nested under, so they go too rather than becoming orphans.
            plan[:] = [x for x in plan if not (x.slot_kind == "discipline" and not x.is_lead and x.slot == removed.slot)]
            # Remember the removal so the brief re-sync doesn't immediately re-add it.
            label = resourcing.canonical_discipline(removed.slot)
            if label and label not in st.session_state.dismissed_disciplines:
                st.session_state.dismissed_disciplines.append(label)
        st.rerun()


# The six "Done entering data -- refresh ..." deferred-apply fee tables (see
# _render_large_discipline_fee_table() and its siblings) each track their own
# "*_last_applied_editor_sig" -- None means "never applied yet, bypass the
# tick requirement on the very next render." That bypass can fire once
# *before* a project is ever loaded (e.g. against the empty/default project
# these tables briefly render against right after account creation, seeded
# with nothing but the always-included "Project Management" line), which
# permanently consumes it with a near-empty baseline. Loading a real project
# afterwards then makes every one of these tables look permanently "pending"
# (mismatched against that stale one-row baseline) even though the user
# hasn't touched anything -- confirmed via a debug probe showing exactly this
# for the large-scope "Indicative fee split by discipline" table. Resetting
# all of them here, alongside the loaded values, gives a freshly (re)loaded
# project a genuine first-load bypass keyed to its own real data.
_FEE_TABLE_APPLY_STATE_PREFIXES = (
    "_disc_fee_", "_letter_disc_fee_",
    "_scope_fee_", "_large_scope_fee_",
    "_pct_fee_", "_letter_pct_fee_",
)


def _apply_loaded_project(loaded_state: dict, source_label: str) -> None:
    """Shared by both the local 'Open' button and the manual zip uploader --
    overwrites every project_store-managed session_state key with the loaded
    values, resets save/export bookkeeping that no longer applies to the
    newly-loaded project, and reruns so every tab reflects it immediately."""
    for k, v in loaded_state.items():
        st.session_state[k] = v
    st.session_state._project_save_bytes = None
    st.session_state.docx_buffer = None
    for prefix in _FEE_TABLE_APPLY_STATE_PREFIXES:
        st.session_state[f"{prefix}last_applied_editor_sig"] = None
        st.session_state[f"{prefix}apply_tick"] = False
        st.session_state[f"{prefix}apply_tick_seen"] = False
    # The "re-enter your AI provider settings" follow-up only applies in the
    # desktop/BYOK build, where ai_config lives purely in session_state and
    # loading a project doesn't touch it, but a fresh session might not have
    # a key typed in yet. In SaaS mode ai_config is auto-filled from the
    # server-side ANTHROPIC_API_KEY at session start (see _ENV_ANTHROPIC_KEY)
    # and never needs re-entering, so telling a SaaS customer to go do that
    # in a sidebar field that doesn't exist for them was just wrong.
    if IS_SAAS_MODE:
        st.success(f"Loaded project from {source_label}.")
    else:
        st.success(f"Loaded project from {source_label}. Re-enter your AI provider settings in the sidebar to continue.")
    st.rerun()


def _maybe_autosave() -> None:
    """Called once per script run, after every tab has had a chance to mutate
    session_state. Debounced by AUTOSAVE_INTERVAL_SECONDS rather than saving
    on literally every rerun (Streamlit reruns on most widget interactions,
    including every single data_editor cell edit in the Fees & Program tab --
    writing a multi-MB zip to disk that often would be wasteful and could lag
    the UI). Silently skipped if there's no project name yet, so a blank
    session doesn't create a stray 'untitled_project' file.

    In SAAS_MODE, saves to the database under the logged-in user's account
    (cloud_project_store) instead of the server's local disk -- otherwise
    every user's in-progress work (uploaded briefs, drafts, team CVs) exists
    ONLY in that one browser tab's live session, and is lost outright on any
    page refresh, dropped connection, or redeploy, with no way to recover it
    (see the "My projects" sidebar section, which reads from the same
    table). local_project_store is kept for the non-SaaS local prototype."""
    if not st.session_state._autosave_enabled:
        return
    project_id = _project_identifier()
    if not project_id:
        # No project/tender name yet -- this used to skip autosave entirely
        # until one was entered, which meant a user who'd already uploaded a
        # real tender brief (the slow, easy-to-forget step) but simply
        # hadn't gotten to Project Setup yet would lose that brief outright
        # on any refresh, dropped connection, or accidental tab close --
        # exactly the state a rushing trial user is in. Once there's real
        # content worth not losing, fall back to a fixed "Untitled project"
        # slot instead of skipping -- multiple different unnamed projects in
        # the same account will share and overwrite that one slot until
        # each is given its own name, but that's an acceptable trade-off
        # for a "don't lose today's work" safety net, not a version
        # history. Still skipped entirely for a genuinely blank session (no
        # name AND no uploaded brief yet) so opening the app doesn't create
        # a stray entry before there's anything worth saving.
        if st.session_state.tender_extracted is None:
            return
        project_id = "Untitled project"
    now = time.time()
    if now - st.session_state._last_autosave_ts < AUTOSAVE_INTERVAL_SECONDS:
        return
    try:
        # Serialize once up front (this is the same work save_cloud()/
        # save_local() used to each do internally) so its content hash can
        # be compared against the last save's hash -- if nothing that
        # save_project() actually captures has changed since then, skip the
        # write entirely. Hashing costs something every interval too, but
        # it's in-process and cheap; the write it can now skip is the
        # expensive part at scale (for cloud_project_store specifically: a
        # network round trip writing a multi-MB blob to Postgres, on every
        # interval, for every active user, whether or not anything in it
        # actually changed).
        blob = project_store.save_project(st.session_state)
        content_hash = hashlib.sha256(blob).hexdigest()
        if content_hash == st.session_state.get("_last_autosave_hash"):
            st.session_state._last_autosave_ts = now
            return
        if IS_SAAS_MODE and current_user:
            slug = cloud_project_store.save_cloud(current_user.id, project_id, blob)
            st.session_state._last_autosave_ts = now
            st.session_state._last_autosave_path = slug
            st.session_state._last_autosave_error = ""
        else:
            path = local_project_store.save_local(project_id, blob)
            st.session_state._last_autosave_ts = now
            st.session_state._last_autosave_path = path
            st.session_state._last_autosave_error = ""
        st.session_state["_last_autosave_hash"] = content_hash
    except Exception as exc:
        # Auto-save is a convenience, not a step the user is waiting on -- a failure here
        # (e.g. disk full, folder permissions, a transient DB hiccup) shouldn't interrupt
        # whatever they were doing, so this still doesn't raise/stop the script. But it
        # used to swallow the error completely (bare `except: pass`), which is exactly
        # how a real problem -- like the DATABASE_URL misconfiguration found and fixed
        # earlier -- could silently fail every single save with the user having no way
        # to know, only discovering it later when a project they thought was saved
        # wasn't there. Recording it here lets the "My projects" section surface a
        # visible warning instead (see the sidebar code that reads
        # _last_autosave_error), and _last_autosave_ts is deliberately NOT updated on
        # failure, so the very next rerun retries immediately rather than waiting out
        # the normal debounce interval.
        st.session_state._last_autosave_error = str(exc) or exc.__class__.__name__


def _ensure_divider_config(sections) -> None:
    """Give every current section a sensible default divider design (layout + which
    uploaded photo, if any) the first time it's seen, without clobbering choices the
    user already made. Called each time the Graphics & Design tab renders."""
    photos = st.session_state.project_photo_bytes
    config = st.session_state.section_divider_config
    for i, s in enumerate(sections):
        if s.title not in config:
            layout = "Photo + gradient" if photos else "Solid colour"
            config[s.title] = {
                "layout": layout,
                "photo_index": (i % len(photos)) if photos else None,
                "quote_index": None,
                "photo_caption": "",
            }
        else:
            # Back-fill for configs created before "photo_caption" existed
            # (older saved/autosaved projects) -- never clobber a value
            # that's already there.
            config[s.title].setdefault("photo_caption", "")
    # Drop config for sections that no longer exist (e.g. after a structure rebuild).
    current_titles = {s.title for s in sections}
    for stale in [t for t in config if t not in current_titles]:
        del config[stale]


_init_state()

# Seed a NEW project's blank fields from the firm profile -- bidder name,
# signatory block, standing terms. Once per session, not per rerun: seeding
# on every rerun would silently refill a field the user had deliberately
# cleared for this bid, which is exactly the kind of quiet wrongness a
# proposal tool must not have. Loading a saved project overwrites these
# fields from the file anyway, so the two paths don't fight.
if not st.session_state.get("_firm_profile_seeded"):
    try:
        _seed_project_from_firm_profile()
    except Exception:
        pass
    st.session_state._firm_profile_seeded = True

# Attribute every AI call made inline in THIS script run (i.e. not via the
# job queue -- that path carries its own usage_context, see
# _run_job_or_inline) to the logged-in user and current project, for
# per-bid cost logging (db.AiCallLog). Re-set on every rerun because the
# project fields can change between runs. Best-effort on purpose.
try:
    ai_interface.set_usage_context(
        user_id=current_user.id if (IS_SAAS_MODE and current_user) else None,
        project_key=_current_project_key(),
        project_name=st.session_state.get("project_name", ""),
    )
except Exception:
    pass



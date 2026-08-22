"""
artifact_download_gate.py

The free-trial "one download of each of three artifacts, ever" gate.

Round 3, Part 5c: this logic used to live entirely inside
modules/pages/10_state_helpers.py as three functions
(_free_artifact_already_downloaded, _mark_free_artifact_downloaded,
_free_artifact_download_blocked) reading current_user/_access/IS_SAAS_MODE
as module-level globals -- values app.py's exec-composition shares across
modules/pages/*.py (see app.py's own docstring), never available outside a
real page render. That made the actual gating DECISION untestable: the only
existing coverage (test_billing_i18n.py's test_free_tier_rename_bypass_closed)
could exercise the raw db.ArtifactEvent insert/query it's built on, but
never call the real functions a download button calls, or prove that
marking a download and then re-checking the gate actually behaves as one
flow.

Extracted here as the SAME logic, taking the live-session values (user id,
whether the current project is free-tier) as explicit parameters instead of
reading them from globals -- a pure refactor, not a behaviour change.
modules/pages/10_state_helpers.py's three functions are now thin wrappers
that supply those parameters from the real session and, for
mark_downloaded(), react to its return value the way the page needs to
(setting st.session_state on an unexpected error). Every comment below
carrying an "Audit fix Part 2b/2c" tag is preserved verbatim from the
original functions -- the reasoning didn't change, only where the code lives.
"""

from __future__ import annotations

# Keys match the `artifact_type` values written to db.ArtifactEvent and read
# by modules/pages/80_export.py's download buttons. Kept here (rather than
# only in 10_state_helpers.py, which still re-exports this same tuple) since
# this module owns the gating decision that reads it.
FREE_TIER_ARTIFACTS = ("proposal_docx", "tender_summary_docx", "org_chart_pptx")

# Audit fix Part 2b: a fixed sentinel, not a real project's key -- see
# already_downloaded()/mark_downloaded()'s docstrings for why.
TRIAL_ARTIFACT_EVENT_SENTINEL_KEY = ""


def already_downloaded(db, user_id: str, artifact_type: str, is_free_tier: bool) -> bool:
    """True once this ACCOUNT's ONE free download of `artifact_type` (one of
    FREE_TIER_ARTIFACTS) has already happened. `is_free_tier` is the
    caller's own _project_is_free_tier() result -- only meaningful while
    True, since a paid project never writes or checks these rows at all
    (see db.ArtifactEvent's docstring).

    Audit fix Part 2b: checked by (user_id, artifact_type) alone, NOT also
    by project_key -- previously scoping by project_key meant the free
    download was really "once per project IDENTITY", and project identity
    folds in a hash of the brief text (see _current_project_key()), so
    editing even one character of the project/tender/client name computed
    a brand new, never-downloaded-from identity with no ArtifactEvent rows
    against it: a fresh "one free download" on demand, repeatable forever
    on the trial tier. The trial is fundamentally ONE bid; "one free
    download of each artifact on the trial, ever" (account-wide) is the
    correct rule and closes the rename bypass outright. Deliberately
    ignores project_key on the read side too, so an ArtifactEvent row
    written under the OLD per-project scheme (before this fix shipped)
    still correctly counts as "already used" -- no data migration needed,
    see mark_downloaded()'s sentinel-key approach below."""
    if not is_free_tier:
        return False
    with db.get_session() as s:
        return s.query(db.ArtifactEvent).filter(
            db.ArtifactEvent.user_id == user_id,
            db.ArtifactEvent.artifact_type == artifact_type,
        ).first() is not None


def mark_downloaded(db, user_id: str, artifact_type: str, is_free_tier: bool) -> bool:
    """Records that this ACCOUNT's one free download of `artifact_type` has
    now happened. Call this the moment a free-tier download actually fires
    (see modules/pages/80_export.py's on_click= callbacks) -- never for a
    paid project (`is_free_tier=False`), which has no download cap to track.

    Returns True if a genuine, unexpected database error occurred (the
    caller should surface this as a retry warning); False on ordinary
    success OR on the harmless expected "already downloaded" duplicate-key
    case -- both look the same from here on out (the row exists).

    Audit fix Part 2b: writes with project_key=TRIAL_ARTIFACT_EVENT_SENTINEL_KEY
    (a fixed empty string, not this project's real key) so the EXISTING
    unique constraint on (user_id, project_key, artifact_type) enforces
    "once per account", not "once per project" -- see
    already_downloaded()'s docstring for why per-project scoping was a
    rename-driven bypass, and why this needs no database schema change: a
    real project's key is always non-empty (a project name is required
    before Tender Analysis can even run), so the sentinel can never
    collide with one.

    Audit fix Part 2c: previously caught a bare `except Exception` and
    silently swallowed it -- meaning ANY database hiccup on this insert
    (not just the expected duplicate-key "already downloaded" case) failed
    OPEN, granting an unmetered extra download with no record and no sign
    anything went wrong. Now only a genuine duplicate-key IntegrityError
    (the harmless, expected "already downloaded" outcome -- including a
    concurrent click racing this exact insert) is swallowed; any other
    failure is reported back via the return value instead of silently
    succeeding."""
    if not is_free_tier:
        return False
    from sqlalchemy.exc import IntegrityError
    with db.get_session() as s:
        s.add(db.ArtifactEvent(
            user_id=user_id, project_key=TRIAL_ARTIFACT_EVENT_SENTINEL_KEY,
            artifact_type=artifact_type,
        ))
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
        except Exception:
            s.rollback()
            return True
    return False


def blocked(is_free_tier: bool, artifact_type: str, already_downloaded_result: bool,
           free_tier_artifacts: tuple = FREE_TIER_ARTIFACTS) -> bool:
    """The single decision a download button gates on: True means show the
    paywall message instead of the file. False for every paid/unlimited/
    non-SaaS project (unlimited re-downloads -- Part B2's "buying a bid
    unlocks everything" rule), and for a free-tier project's FIRST download
    of one of the three free_tier_artifacts; True for a free-tier project's
    second+ download of one of those three, or for ANY download of an
    artifact not on the free list at all (Methodology/Program PPTX, filled
    schedules).

    `already_downloaded_result`: the caller's own already_downloaded() call
    -- kept as an explicit parameter rather than called again in here, so a
    caller that already has the answer (or is testing this decision in
    isolation) doesn't pay for or fake a second database round-trip."""
    if not is_free_tier:
        return False
    if artifact_type not in free_tier_artifacts:
        return True
    return already_downloaded_result

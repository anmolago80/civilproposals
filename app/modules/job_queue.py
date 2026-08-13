"""
job_queue.py

Background job queue (Redis Queue / RQ) for the two operations in this app
that are slow AND heavy enough to visibly slow down every OTHER
concurrently-connected user's Streamlit session if they run inline in the
main web process: Tender Analysis (tender_analyser.analyse_tender) and Draft
Generation (draft_generator.generate_all_drafts, which itself already fires
up to MAX_CONCURRENT_DRAFTS AI calls at once for a big pack). Streamlit runs
every user's session as a thread inside ONE shared Python process, so a
slow, GIL-holding operation for one customer measurably slows down other
customers' concurrent requests, not just the one that triggered it -- moving
this work into a separate `rq worker` process (see worker.py) fixes that at
the source, rather than trying to make the operation itself faster.

Usage from app.py (see _run_job_or_inline there): enqueue() takes the
already-existing module-level function (tender_analyser.analyse_tender,
draft_generator.generate_all_drafts) directly -- no separate "job function"
wrapper needed, since RQ can pickle a reference to any importable top-level
function and both the web process and the worker process (worker.py) import
the exact same modules/ package. The one thing that can't cross that
boundary is a live progress_callback closure (nothing in Redis can call back
into a specific browser tab's Streamlit script run), so queued calls always
run with progress_callback=None -- the Streamlit side polls for the whole
job finishing instead of a live per-chunk/per-section count. See the
queued_text/running_text handling in app.py's _run_job_or_inline for how
that's presented in the UI instead.

Design notes:
- The RQ job's OWN id is used as this app's job id everywhere -- no separate
  uuid layer. db.Job is a thin, permanent index: which user owns which job
  id, and its last-known status. It is NOT where job inputs or outputs
  live -- see db.Job's docstring for why (short version: API keys are an
  input to both jobs this module runs, and this table must not become a
  second, longer-lived place one of those ends up written to).
- Job arguments and the job's return value live in Redis, via RQ's own
  mechanism (job.args / job.result), governed by RESULT_TTL_SECONDS /
  FAILURE_TTL_SECONDS below -- long enough for a realistic "alt-tabbed away
  and came back" gap, short enough that nothing sits in Redis indefinitely.
- Every status/result lookup takes the requesting user_id and checks it
  against db.Job.user_id before touching Redis at all -- an RQ job id is
  not a secret (it's a URL/query-param-shaped string that could leak into
  logs), so ownership must be re-checked server-side on every poll, not
  just trusted from whatever id the client last had in memory.
- run_tender_analysis_job() / run_draft_generation_job() below exist
  specifically so the Anthropic API key never has to be part of a queued
  job's pickled payload in SaaS mode. This queue is ONLY ever used in SaaS
  mode (see app.py's _run_job_or_inline: use_queue requires IS_SAAS_MODE),
  where ai_config's api_key is always the same single server-side
  ANTHROPIC_API_KEY -- the sidebar field that lets a desktop/BYOK user
  paste their own key is hidden entirely in SaaS mode (see app.py), so
  there's no per-user key to preserve here, only one shared production
  credential. Enqueuing the real key with every job meant it sat in Redis,
  in plaintext, for up to RESULT_TTL_SECONDS on every single queued job --
  a Redis compromise would have hand-charged spend on this account's
  Anthropic key, uncapped, to anyone who read it out. app.py now passes a
  REDACTED ai_config (api_key="") into the queue instead, and these two
  wrapper functions re-fill it from THIS PROCESS's own ANTHROPIC_API_KEY
  env var right before calling the real analysis/drafting function -- so
  the worker service needs that variable set now (it didn't before; see
  worker.py's docstring and DEPLOY.md).
"""

from __future__ import annotations

import os

from redis import Redis
from rq import Queue
from rq.job import Job as RQJob
from rq.exceptions import NoSuchJobError

from modules import db, draft_generator, tender_analyser

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
QUEUE_NAME = "civilproposals"

# How long RQ keeps a finished job's return value (or a failed job's
# traceback) around in Redis before it's evicted.
RESULT_TTL_SECONDS = 60 * 60 * 2       # 2 hours
FAILURE_TTL_SECONDS = 60 * 60 * 2      # 2 hours
JOB_TIMEOUT_SECONDS = 60 * 15          # generous ceiling for a big drafting pack

_redis_conn = None


def redis_available() -> bool:
    """False when REDIS_URL isn't set yet -- e.g. before the Railway Redis
    service + worker service have been provisioned (see DEPLOY.md), or in
    local/dev use. Callers (see app.py's _run_job_or_inline) fall back to
    running the work inline, synchronously, exactly as this app always did
    before background jobs existed -- so nothing here is a hard dependency."""
    return bool(REDIS_URL)


def _get_redis() -> Redis:
    global _redis_conn
    if _redis_conn is None:
        if not REDIS_URL:
            raise RuntimeError(
                "REDIS_URL is not set -- background jobs need a Redis service attached. "
                "Check redis_available() before calling enqueue()/get_status()."
            )
        _redis_conn = Redis.from_url(REDIS_URL)
    return _redis_conn


def _get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_get_redis())


def enqueue(user_id: str, job_type: str, func, *args, **kwargs) -> str:
    """Enqueues `func(*args, **kwargs)` to run in the worker process (see
    worker.py), records an owning db.Job row, and returns the job id to poll
    with via get_status(). `func` must be a module-level function importable
    the same way in both the web process and the worker process -- an
    instance method or a closure (e.g. a Streamlit progress_callback) can't
    be pickled across the process boundary."""
    queue = _get_queue()
    rq_job = queue.enqueue(
        func, *args,
        job_timeout=JOB_TIMEOUT_SECONDS,
        result_ttl=RESULT_TTL_SECONDS,
        failure_ttl=FAILURE_TTL_SECONDS,
        **kwargs,
    )
    with db.get_session() as s:
        s.add(db.Job(id=rq_job.id, user_id=user_id, job_type=job_type, status="queued"))
        s.commit()
    return rq_job.id


def get_status(job_id: str, user_id: str) -> dict:
    """Returns {"status": ..., "result": ..., "error": ...}.

    `status` is one of "queued", "started", "finished", "failed", or
    "not_found" -- the last one covers both a genuinely unknown job id and
    one that belongs to a different user, deliberately giving the same
    response either way so this can't be used to probe which job ids exist.
    Only "finished" ever sets "result"; only "failed" ever sets "error"."""
    with db.get_session() as s:
        owned = s.query(db.Job).filter(db.Job.id == job_id, db.Job.user_id == user_id).first()
    if not owned:
        return {"status": "not_found", "result": None, "error": None}

    try:
        rq_job = RQJob.fetch(job_id, connection=_get_redis())
    except NoSuchJobError:
        # Expired out of Redis (TTL) before ever being polled to completion,
        # or the worker service was never actually running -- either way,
        # from the polling side this would otherwise look identical to
        # "still queued forever", so surface it as a clear failure instead.
        message = (
            "This job expired before a worker process picked it up. Make sure the "
            "background worker service is deployed and running (see DEPLOY.md)."
        )
        _update_job_row(job_id, "failed", message)
        return {"status": "failed", "result": None, "error": message}

    rq_status = rq_job.get_status(refresh=True)
    if rq_status in ("queued", "deferred", "scheduled"):
        status = "queued"
    elif rq_status == "started":
        status = "started"
    elif rq_status == "finished":
        status = "finished"
    else:
        status = "failed"

    error = None
    if status == "failed":
        error = _short_error(rq_job.exc_info) or "The job failed for an unknown reason."
    if status != owned.status:
        _update_job_row(job_id, status, error or "")

    return {
        "status": status,
        "result": rq_job.result if status == "finished" else None,
        "error": error,
    }


def _update_job_row(job_id: str, status: str, error_message: str) -> None:
    with db.get_session() as s:
        row = s.query(db.Job).filter(db.Job.id == job_id).first()
        if row:
            row.status = status
            row.error_message = (error_message or "")[:2000]
            s.commit()


def _resolve_server_api_key(ai_config: dict) -> dict:
    """Takes the (deliberately redacted, api_key="") ai_config dict that
    actually gets pickled into the job payload (see this module's docstring)
    and returns a copy with api_key re-filled from THIS PROCESS's -- i.e.
    the worker process's -- own ANTHROPIC_API_KEY env var, right before the
    real analysis/drafting call. Only fills in a key when one isn't already
    present, so this stays harmless (a no-op) if it's ever handed a
    non-redacted config -- though in practice that never happens, since this
    queue is only ever used in SaaS mode, where ai_config's api_key is
    always this same single server-side key to begin with (see app.py)."""
    if ai_config.get("api_key"):
        return ai_config
    return {
        **ai_config,
        "provider": ai_config.get("provider") or "anthropic",
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    }


def _apply_usage_context(usage_context: dict | None, default_purpose: str) -> None:
    """Sets ai_interface's cost-attribution context for this worker-side job
    run (see ai_interface.set_usage_context / db.AiCallLog). The context
    dict is plain strings (user id, project key/name) -- safe to pickle into
    the job payload, unlike an API key. Best-effort: attribution failing
    must never fail the job itself."""
    try:
        from modules import ai_interface
        usage_context = usage_context or {}
        ai_interface.set_usage_context(
            user_id=usage_context.get("user_id"),
            project_key=usage_context.get("project_key", ""),
            project_name=usage_context.get("project_name", ""),
            purpose=usage_context.get("purpose") or default_purpose,
        )
    except Exception:
        pass


def run_tender_analysis_job(document_text: str, annotations, ai_config: dict,
                            usage_context: dict | None = None, **kwargs):
    """Queued-job entry point for tender_analyser.analyse_tender -- app.py
    enqueues THIS function for the SaaS/queued path (instead of enqueuing
    analyse_tender directly) specifically so the real Anthropic key never
    has to be part of the pickled job payload. `ai_config` arrives here
    redacted (api_key="") and gets re-filled from this worker process's own
    ANTHROPIC_API_KEY env var immediately below, right before the real call
    -- see this module's docstring for the full rationale.

    `usage_context` (optional) attributes this job's AI calls to a
    user/project for per-bid cost logging -- see _apply_usage_context()."""
    _apply_usage_context(usage_context, "tender_analysis")
    return tender_analyser.analyse_tender(
        document_text, annotations, _resolve_server_api_key(ai_config), **kwargs
    )


def run_draft_generation_job(sections, analysis, company_material_text: dict, ai_config: dict,
                             usage_context: dict | None = None, **kwargs):
    """Queued-job entry point for draft_generator.generate_all_drafts -- same
    rationale and mechanism as run_tender_analysis_job() above."""
    _apply_usage_context(usage_context, "draft_generation")
    return draft_generator.generate_all_drafts(
        sections, analysis, company_material_text, _resolve_server_api_key(ai_config), **kwargs
    )


def _short_error(exc_info: str | None) -> str | None:
    """RQ's exc_info is a full worker-side traceback string; the last
    non-empty line is normally the actual exception message, which is the
    only part worth showing a user -- the rest is worker-process internals
    they can't act on."""
    if not exc_info:
        return None
    lines = [line for line in exc_info.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else None

"""
worker.py

Entry point for the background job worker process -- this is what a second
Railway service (e.g. "civilproposals-worker") should run, as a completely
separate deployment from the main Streamlit web service. Its only job is to
pull queued work (Tender Analysis, Draft Generation -- see
modules/job_queue.py for what gets queued and why) off the "civilproposals"
Redis queue and run it, so a slow AI call or a big multi-section drafting
pass never shares a process (or a GIL) with anyone else's live Streamlit
session on the web service.

Run locally with:  python worker.py
On Railway: create a second service from the same repo, with start command
`python worker.py`, and give it the same REDIS_URL and DATABASE_URL
environment variables as the web service (see DEPLOY.md's "Background
jobs" section for the full setup). It does NOT need any AI provider API key
of its own -- every AI call a job makes uses whichever key the requesting
user pasted into their own session (BYOK), passed through as part of the
job's arguments.
"""

from __future__ import annotations

import sys

from redis import Redis
from rq import Worker

from modules import db
from modules.job_queue import QUEUE_NAME, REDIS_URL


def main() -> None:
    if not REDIS_URL:
        print(
            "REDIS_URL is not set -- attach a Redis service and share its connection URL "
            "with this worker service (see DEPLOY.md's 'Background jobs' section).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Make sure the jobs table (and everything else) exists before the
    # first job needs it -- same idempotent call app.py makes on startup.
    db.init_db()

    connection = Redis.from_url(REDIS_URL)
    worker = Worker([QUEUE_NAME], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()

"""SQLite job and reel store for Reel.

Provides schema creation, atomic job/reel claiming, and status/progress tracking
at {data_dir}/reel.db.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from reel.common.config import load_config

JobStatus = Literal["queued", "running", "done", "failed"]
ReelStatus = Literal["queued", "running", "done", "failed"]


class JobRecord(BaseModel):
    """Pydantic model representing a row in the jobs table."""

    model_config = ConfigDict(extra="ignore")

    id: str
    status: JobStatus = "queued"
    stage: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    input_path: str
    source: str = "upload"
    filename: str
    duration_s: float | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class ReelRecord(BaseModel):
    """Pydantic model representing a row in the reels table."""

    model_config = ConfigDict(extra="ignore")

    job_id: str
    mode: str
    status: ReelStatus = "queued"
    path: str | None = None
    duration_s: float | None = None
    event_ids: list[str] = Field(default_factory=list)
    exclude_event_ids: list[str] = Field(default_factory=list)
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


def get_default_db_path(data_dir: Path | str | None = None) -> Path:
    """Return the default SQLite database path at {data_dir}/reel.db."""
    if data_dir is not None:
        base = Path(data_dir)
    else:
        base = Path(load_config().data_dir)
    return base / "reel.db"


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def get_db_connection(db_path: Path | str) -> sqlite3.Connection:
    """Open a SQLite connection configured for concurrent access."""
    path = Path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path | str) -> None:
    """Create the jobs and reels tables if they do not already exist."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'queued',
                    stage TEXT,
                    progress REAL NOT NULL DEFAULT 0.0,
                    input_path TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'upload',
                    filename TEXT NOT NULL,
                    duration_s REAL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                ON jobs(status, created_at);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reels (
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    path TEXT,
                    duration_s REAL,
                    event_ids TEXT DEFAULT '[]',
                    exclude_event_ids TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    PRIMARY KEY (job_id, mode)
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reels_status_created
                ON reels(status, created_at);
                """
            )
    finally:
        conn.close()


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        id=row["id"],
        status=row["status"],
        stage=row["stage"],
        progress=float(row["progress"]),
        input_path=row["input_path"],
        source=row["source"],
        filename=row["filename"],
        duration_s=float(row["duration_s"]) if row["duration_s"] is not None else None,
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error=row["error"],
    )


def _row_to_reel(row: sqlite3.Row) -> ReelRecord:
    event_ids = json.loads(row["event_ids"]) if row["event_ids"] else []
    exclude_ids = json.loads(row["exclude_event_ids"]) if row["exclude_event_ids"] else []
    return ReelRecord(
        job_id=row["job_id"],
        mode=row["mode"],
        status=row["status"],
        path=row["path"],
        duration_s=float(row["duration_s"]) if row["duration_s"] is not None else None,
        event_ids=event_ids,
        exclude_event_ids=exclude_ids,
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error=row["error"],
    )


# ---------------------------------------------------------------------------
# Job Operations
# ---------------------------------------------------------------------------


def create_job(
    db_path: Path | str,
    input_path: str,
    source: str = "upload",
    filename: str | None = None,
    duration_s: float | None = None,
    job_id: str | None = None,
) -> JobRecord:
    """Create a new job in queued status with progress 0."""
    init_db(db_path)
    jid = job_id or f"job-{uuid.uuid4().hex[:12]}"
    fname = filename or Path(input_path).name
    now = _utc_now_iso()

    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, status, stage, progress, input_path, source, filename,
                    duration_s, created_at
                ) VALUES (?, 'queued', NULL, 0.0, ?, ?, ?, ?, ?);
                """,
                (jid, input_path, source, fname, duration_s, now),
            )
    finally:
        conn.close()

    job = get_job(db_path, jid)
    if job is None:
        raise RuntimeError(f"Failed to create job {jid}")
    return job


def get_job(db_path: Path | str, job_id: str) -> JobRecord | None:
    """Retrieve a job by its unique identifier."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cur = conn.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        row = cur.fetchone()
        return _row_to_job(row) if row else None
    finally:
        conn.close()


def list_jobs(db_path: Path | str) -> list[JobRecord]:
    """Return all jobs ordered by creation date descending."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cur = conn.execute("SELECT * FROM jobs ORDER BY datetime(created_at) DESC;")
        return [_row_to_job(r) for r in cur.fetchall()]
    finally:
        conn.close()


def claim_next_job(db_path: Path | str) -> JobRecord | None:
    """Atomically claim the oldest queued job and mark it as running."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cur = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status = 'queued'
            ORDER BY datetime(created_at) ASC, id ASC
            LIMIT 1;
            """
        )
        row = cur.fetchone()
        if not row:
            conn.execute("COMMIT;")
            return None

        job_id = row["id"]
        now = _utc_now_iso()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                started_at = ?,
                stage = COALESCE(stage, 'ingest')
            WHERE id = ?;
            """,
            (now, job_id),
        )
        conn.execute("COMMIT;")

        # Fetch the updated record
        cur = conn.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        return _row_to_job(cur.fetchone())
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()


def update_progress(
    db_path: Path | str,
    job_id: str,
    stage: str,
    progress: float,
) -> None:
    """Update progress and stage for a running job, ensuring progress never decreases."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            # Clamp between 0.0 and 100.0, and never decrease
            target_prog = max(0.0, min(100.0, float(progress)))
            conn.execute(
                """
                UPDATE jobs
                SET stage = ?,
                    progress = MAX(progress, ?)
                WHERE id = ? AND status = 'running';
                """,
                (stage, target_prog, job_id),
            )
    finally:
        conn.close()


def start_job(db_path: Path | str, job_id: str) -> None:
    """Mark a specific job as running (used when running a job outside the worker)."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?;",
                (_utc_now_iso(), job_id),
            )
    finally:
        conn.close()


def finish_job(db_path: Path | str, job_id: str) -> None:
    """Mark a job as successfully finished with 100% progress."""
    init_db(db_path)
    now = _utc_now_iso()
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'done',
                    progress = 100.0,
                    finished_at = ?
                WHERE id = ?;
                """,
                (now, job_id),
            )
    finally:
        conn.close()


def fail_job(db_path: Path | str, job_id: str, message: str) -> None:
    """Mark a job as failed with an error message."""
    init_db(db_path)
    now = _utc_now_iso()
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    error = ?,
                    finished_at = ?
                WHERE id = ?;
                """,
                (message, now, job_id),
            )
    finally:
        conn.close()


def requeue_stale_jobs(db_path: Path | str) -> int:
    """Reset jobs left running (e.g. from a killed worker) back to queued."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = 'queued',
                    error = 'Interrupted: re-queued on worker restart'
                WHERE status = 'running';
                """
            )
            return cur.rowcount
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Reel Operations
# ---------------------------------------------------------------------------


def create_reel_request(
    db_path: Path | str,
    job_id: str,
    mode: str,
    exclude_event_ids: list[str] | None = None,
) -> ReelRecord:
    """Create or update a reel request for (job_id, mode) in queued status."""
    init_db(db_path)
    exclude_ids = exclude_event_ids or []
    exclude_json = json.dumps(exclude_ids)
    now = _utc_now_iso()

    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO reels (
                    job_id, mode, status, exclude_event_ids, created_at,
                    started_at, finished_at, error
                ) VALUES (?, ?, 'queued', ?, ?, NULL, NULL, NULL)
                ON CONFLICT(job_id, mode) DO UPDATE SET
                    status = 'queued',
                    exclude_event_ids = excluded.exclude_event_ids,
                    started_at = NULL,
                    finished_at = NULL,
                    error = NULL;
                """,
                (job_id, mode, exclude_json, now),
            )
    finally:
        conn.close()

    reel = get_reel(db_path, job_id, mode)
    if reel is None:
        raise RuntimeError(f"Failed to create reel request for {job_id} {mode}")
    return reel


def get_reel(db_path: Path | str, job_id: str, mode: str) -> ReelRecord | None:
    """Retrieve a reel record by job ID and mode."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM reels WHERE job_id = ? AND mode = ?;",
            (job_id, mode),
        )
        row = cur.fetchone()
        return _row_to_reel(row) if row else None
    finally:
        conn.close()


def list_reels_for_job(db_path: Path | str, job_id: str) -> list[ReelRecord]:
    """Return all reel requests for a given job."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM reels WHERE job_id = ? ORDER BY mode ASC;",
            (job_id,),
        )
        return [_row_to_reel(r) for r in cur.fetchall()]
    finally:
        conn.close()


def claim_next_reel(db_path: Path | str) -> ReelRecord | None:
    """Atomically claim the oldest queued reel request."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cur = conn.execute(
            """
            SELECT * FROM reels
            WHERE status = 'queued'
            ORDER BY datetime(created_at) ASC
            LIMIT 1;
            """
        )
        row = cur.fetchone()
        if not row:
            conn.execute("COMMIT;")
            return None

        job_id = row["job_id"]
        mode = row["mode"]
        now = _utc_now_iso()
        conn.execute(
            """
            UPDATE reels
            SET status = 'running',
                started_at = ?
            WHERE job_id = ? AND mode = ?;
            """,
            (now, job_id, mode),
        )
        conn.execute("COMMIT;")

        cur = conn.execute(
            "SELECT * FROM reels WHERE job_id = ? AND mode = ?;",
            (job_id, mode),
        )
        return _row_to_reel(cur.fetchone())
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()


def finish_reel(
    db_path: Path | str,
    job_id: str,
    mode: str,
    path: str | None = None,
    duration_s: float | None = None,
    event_ids: list[str] | None = None,
) -> None:
    """Mark a reel request as successfully finished."""
    init_db(db_path)
    now = _utc_now_iso()
    events_json = json.dumps(event_ids or [])
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE reels
                SET status = 'done',
                    path = ?,
                    duration_s = ?,
                    event_ids = ?,
                    finished_at = ?
                WHERE job_id = ? AND mode = ?;
                """,
                (path, duration_s, events_json, now, job_id, mode),
            )
    finally:
        conn.close()


def fail_reel(db_path: Path | str, job_id: str, mode: str, message: str) -> None:
    """Mark a reel request as failed with an error message."""
    init_db(db_path)
    now = _utc_now_iso()
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE reels
                SET status = 'failed',
                    error = ?,
                    finished_at = ?
                WHERE job_id = ? AND mode = ?;
                """,
                (message, now, job_id, mode),
            )
    finally:
        conn.close()

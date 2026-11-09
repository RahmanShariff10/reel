"""FastAPI app for Reel: uploads, job creation and status, and file serving.

The API only creates jobs, reports status and serves files; all heavy work happens in the
worker process. Run with ``python -m reel.api.main``.
"""

from __future__ import annotations

import mimetypes
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from reel.common.config import load_config
from reel.jobs.store import JobRecord, create_job, get_default_db_path, get_job, init_db, list_jobs

VIDEO_EXTENSIONS = {".mp4", ".mkv"}
_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_PART_SUFFIX = ".part"
_STATUS_CODES = {404: "not_found", 405: "method_not_allowed"}


class ApiError(Exception):
    """An error returned to the client in the API's error format."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class JobCreate(BaseModel):
    """Body of ``POST /api/jobs``: exactly one of the two fields."""

    upload_id: str | None = None
    local_path: str | None = None


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _is_video(name: str) -> bool:
    return Path(name).suffix.lower() in VIDEO_EXTENSIONS


def _job_summary(job: JobRecord) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "filename": job.filename,
        "status": job.status,
        "created_at": job.created_at,
        "duration_s": job.duration_s,
    }


def _job_status(job: JobRecord) -> dict[str, Any]:
    body: dict[str, Any] = {
        "job_id": job.id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "created_at": job.created_at,
        "filename": job.filename,
    }
    if job.error:
        body["error"] = job.error
    return body


def _resolve_upload(uploads_dir: Path, upload_id: str) -> Path:
    if not _UPLOAD_ID_RE.match(upload_id):
        raise ApiError(404, "upload_not_found", f"No upload with id {upload_id!r}.")
    folder = uploads_dir / upload_id
    files = (
        [p for p in folder.iterdir() if p.is_file() and not p.name.endswith(_PART_SUFFIX)]
        if folder.is_dir()
        else []
    )
    if not files:
        raise ApiError(404, "upload_not_found", f"No upload with id {upload_id!r}.")
    return files[0]


def _resolve_local(local_path: str) -> Path:
    path = Path(local_path).expanduser()
    if not _is_video(path.name):
        raise ApiError(400, "unsupported_file_type", "Only .mp4 and .mkv files are accepted.")
    if not path.is_file():
        raise ApiError(400, "local_file_not_found", f"No file found at {local_path!r}.")
    return path.resolve()


def create_app(data_dir: Path | str | None = None, db_path: Path | str | None = None) -> FastAPI:
    """Build the API. Paths default to the configured data directory."""
    root = Path(data_dir) if data_dir is not None else Path(load_config().data_dir)
    db = Path(db_path) if db_path is not None else get_default_db_path(root)
    uploads_dir = root / "uploads"
    jobs_dir = root / "jobs"
    init_db(db)

    app = FastAPI(title="Reel")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Accept-Ranges", "Content-Range", "Content-Length"],
    )

    @app.exception_handler(ApiError)
    async def _on_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _on_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return _error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return _error_response(422, "validation_error", problems)

    @app.put("/api/uploads")
    async def upload(request: Request, filename: str) -> dict[str, Any]:
        name = Path(filename.replace("\\", "/")).name
        if not name or name in {".", ".."}:
            raise ApiError(400, "invalid_filename", "A file name is required.")
        if not _is_video(name):
            raise ApiError(415, "unsupported_file_type", "Only .mp4 and .mkv files are accepted.")

        upload_id = uuid.uuid4().hex
        folder = uploads_dir / upload_id
        folder.mkdir(parents=True)
        partial = folder / f"{name}{_PART_SUFFIX}"
        size = 0
        try:
            with open(partial, "wb") as fh:
                async for chunk in request.stream():
                    fh.write(chunk)
                    size += len(chunk)
            if size == 0:
                raise ApiError(400, "empty_upload", "The uploaded file is empty.")
            partial.replace(folder / name)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return {"upload_id": upload_id, "filename": name, "size_bytes": size}

    @app.post("/api/jobs", status_code=201)
    def create(body: JobCreate) -> dict[str, str]:
        if bool(body.upload_id) == bool(body.local_path):
            raise ApiError(
                400, "invalid_request", "Send exactly one of upload_id or local_path."
            )
        if body.upload_id:
            path, source = _resolve_upload(uploads_dir, body.upload_id), "upload"
        else:
            path, source = _resolve_local(str(body.local_path)), "local"
        job = create_job(db, input_path=str(path), source=source, filename=path.name)
        return {"job_id": job.id}

    @app.get("/api/jobs")
    def jobs() -> list[dict[str, Any]]:
        return [_job_summary(job) for job in list_jobs(db)]

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        job = get_job(db, job_id)
        if job is None:
            raise ApiError(404, "job_not_found", f"No job with id {job_id!r}.")
        return _job_status(job)

    @app.get("/api/files/{job_id}/{file_path:path}")
    def files(job_id: str, file_path: str) -> FileResponse:
        base = jobs_dir.resolve()
        job_root = (base / job_id).resolve()
        target = (job_root / file_path).resolve()
        if job_root.parent != base or not target.is_relative_to(job_root):
            raise ApiError(403, "path_not_allowed", "That path is outside the job folder.")
        if not target.is_file():
            raise ApiError(404, "file_not_found", f"No file at {file_path!r} for this job.")
        media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return FileResponse(target, media_type=media_type)

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "reel.api.main:app",
        host=os.environ.get("REEL_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("REEL_API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()

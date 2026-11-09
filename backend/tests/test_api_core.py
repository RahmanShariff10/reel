"""Tests for slice-05-api-core.

Acceptance criteria:
- A 200 MB body sent in chunks is saved byte-identical; the response has upload_id and size_bytes.
- A .txt filename gives 415 in the error format.
- A valid upload_id gives 201 with job_id, and the job is queued in the database.
- A local_path that doesn't exist or isn't mp4/mkv gives 400 with a clear error code.
- An unknown job id gives 404 in the error format.
- A Range request gives 206 with the right bytes and Content-Range header.
- A path containing ../ is rejected and nothing outside the job folder is served.
- A request from http://localhost:3000 is allowed by CORS.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from reel.api.main import create_app
from reel.jobs.store import get_default_db_path, get_job

MB = 1024 * 1024
ORIGIN = "http://localhost:3000"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def client(data_dir: Path) -> TestClient:
    return TestClient(create_app(data_dir=data_dir), raise_server_exceptions=False)


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


def upload(client: TestClient, content: bytes = b"video-bytes", name: str = "match.mp4") -> dict:
    response = client.put("/api/uploads", params={"filename": name}, content=content)
    assert response.status_code == 200, response.text
    return response.json()


class TestUpload:
    def test_large_chunked_upload_is_byte_identical(
        self, client: TestClient, data_dir: Path
    ) -> None:
        block = bytes(range(256)) * (MB // 256)
        digest = hashlib.sha256()
        for i in range(200):
            digest.update(block[i % 256 :] + block[: i % 256])

        def body() -> Iterator[bytes]:
            for i in range(200):
                yield block[i % 256 :] + block[: i % 256]

        response = client.put("/api/uploads", params={"filename": "big.mkv"}, content=body())

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["size_bytes"] == 200 * MB
        assert payload["filename"] == "big.mkv"
        saved = data_dir / "uploads" / payload["upload_id"] / "big.mkv"
        assert saved.stat().st_size == 200 * MB
        saved_digest = hashlib.sha256()
        with open(saved, "rb") as fh:
            while chunk := fh.read(MB):
                saved_digest.update(chunk)
        assert saved_digest.hexdigest() == digest.hexdigest()

    def test_non_video_rejected(self, client: TestClient) -> None:
        response = client.put("/api/uploads", params={"filename": "notes.txt"}, content=b"x")
        assert_error(response, 415, "unsupported_file_type")

    def test_filename_cannot_escape_the_upload_folder(
        self, client: TestClient, data_dir: Path
    ) -> None:
        payload = upload(client, name="../../evil.mp4")
        assert payload["filename"] == "evil.mp4"
        assert (data_dir / "uploads" / payload["upload_id"] / "evil.mp4").is_file()
        assert not (data_dir / "evil.mp4").exists()

    def test_empty_upload_rejected_and_cleaned_up(
        self, client: TestClient, data_dir: Path
    ) -> None:
        response = client.put("/api/uploads", params={"filename": "a.mp4"}, content=b"")
        assert_error(response, 400, "empty_upload")
        assert not any((data_dir / "uploads").iterdir())


class TestCreateJob:
    def test_from_upload(self, client: TestClient, data_dir: Path) -> None:
        uploaded = upload(client)

        response = client.post("/api/jobs", json={"upload_id": uploaded["upload_id"]})

        assert response.status_code == 201, response.text
        job_id = response.json()["job_id"]
        job = get_job(get_default_db_path(data_dir), job_id)
        assert job is not None
        assert job.status == "queued"
        assert job.source == "upload"
        assert job.filename == "match.mp4"
        assert Path(job.input_path).read_bytes() == b"video-bytes"

    def test_from_local_path(self, client: TestClient, data_dir: Path, tmp_path: Path) -> None:
        video = tmp_path / "local.mkv"
        video.write_bytes(b"x")

        response = client.post("/api/jobs", json={"local_path": str(video)})

        assert response.status_code == 201, response.text
        job = get_job(get_default_db_path(data_dir), response.json()["job_id"])
        assert job is not None
        assert job.source == "local" and job.status == "queued"

    def test_local_path_missing(self, client: TestClient, tmp_path: Path) -> None:
        response = client.post("/api/jobs", json={"local_path": str(tmp_path / "nope.mp4")})
        assert_error(response, 400, "local_file_not_found")

    def test_local_path_wrong_type(self, client: TestClient, tmp_path: Path) -> None:
        other = tmp_path / "notes.txt"
        other.write_text("x")
        response = client.post("/api/jobs", json={"local_path": str(other)})
        assert_error(response, 400, "unsupported_file_type")

    @pytest.mark.parametrize("upload_id", ["0" * 32, "../../etc"])
    def test_unknown_upload(self, client: TestClient, upload_id: str) -> None:
        assert_error(
            client.post("/api/jobs", json={"upload_id": upload_id}), 404, "upload_not_found"
        )

    @pytest.mark.parametrize("body", [{}, {"upload_id": "a", "local_path": "/b.mp4"}])
    def test_exactly_one_source_required(self, client: TestClient, body: dict) -> None:
        assert_error(client.post("/api/jobs", json=body), 400, "invalid_request")

    def test_bad_body_uses_error_format(self, client: TestClient) -> None:
        response = client.post("/api/jobs", json={"upload_id": 5})
        assert_error(response, 422, "validation_error")


class TestJobStatus:
    def test_unknown_job(self, client: TestClient) -> None:
        assert_error(client.get("/api/jobs/job-missing"), 404, "job_not_found")

    def test_status_and_list(self, client: TestClient) -> None:
        job_id = client.post(
            "/api/jobs", json={"upload_id": upload(client)["upload_id"]}
        ).json()["job_id"]

        status = client.get(f"/api/jobs/{job_id}").json()
        assert status["job_id"] == job_id
        assert status["status"] == "queued"
        assert status["stage"] is None
        assert status["progress"] == 0.0
        assert status["filename"] == "match.mp4"
        assert status["created_at"]
        assert "error" not in status

        listed = client.get("/api/jobs").json()
        assert [j["job_id"] for j in listed] == [job_id]
        assert set(listed[0]) == {"job_id", "filename", "status", "created_at", "duration_s"}

    def test_unknown_route_uses_error_format(self, client: TestClient) -> None:
        assert_error(client.get("/api/nothing"), 404, "not_found")


class TestFiles:
    @pytest.fixture
    def job_file(self, data_dir: Path) -> bytes:
        content = bytes(range(256)) * 4
        folder = data_dir / "jobs" / "job-1"
        (folder / "clips").mkdir(parents=True)
        (folder / "clips" / "a.mp4").write_bytes(content)
        (data_dir / "secret.txt").write_text("secret")
        return content

    def test_range_request(self, client: TestClient, job_file: bytes) -> None:
        response = client.get("/api/files/job-1/clips/a.mp4", headers={"Range": "bytes=0-99"})
        assert response.status_code == 206
        assert response.content == job_file[:100]
        assert response.headers["content-range"] == f"bytes 0-99/{len(job_file)}"

    def test_full_file(self, client: TestClient, job_file: bytes) -> None:
        response = client.get("/api/files/job-1/clips/a.mp4")
        assert response.status_code == 200
        assert response.content == job_file
        assert response.headers["content-type"].startswith("video/mp4")

    @pytest.mark.parametrize(
        "path",
        [
            "job-1/" + quote("../../secret.txt", safe=""),
            "job-1/clips/" + quote("../../../secret.txt", safe=""),
            quote("..", safe="") + "/secret.txt",
        ],
    )
    def test_path_escape_rejected(self, client: TestClient, job_file: bytes, path: str) -> None:
        response = client.get(f"/api/files/{path}")
        assert response.status_code in (403, 404)
        assert b"secret" not in response.content or "error" in response.json()
        assert response.text != "secret"

    def test_missing_file(self, client: TestClient, job_file: bytes) -> None:
        assert_error(client.get("/api/files/job-1/nope.mp4"), 404, "file_not_found")


class TestCors:
    def test_localhost_3000_allowed(self, client: TestClient) -> None:
        response = client.get("/api/jobs", headers={"Origin": ORIGIN})
        assert response.headers["access-control-allow-origin"] == ORIGIN

    def test_preflight_allows_put(self, client: TestClient) -> None:
        response = client.options(
            "/api/uploads",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "PUT"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN

    def test_other_origin_not_allowed(self, client: TestClient) -> None:
        response = client.get("/api/jobs", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in response.headers

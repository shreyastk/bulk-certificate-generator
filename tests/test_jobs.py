"""Creating a job and checking its status/progress."""

from app import services
from app.schemas import JobCreate
from tests.conftest import make_payload


def test_create_job_returns_202_with_job_details(client):
    response = client.post("/jobs", json=make_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["id"]
    assert body["course_name"] == "Python Basics"
    assert body["issuer"] == "Acme Academy"
    assert body["issue_date"] == "2026-10-07"
    assert body["total"] == 3


def test_issue_date_defaults_to_today(client):
    from datetime import date

    payload = make_payload()
    del payload["issue_date"]

    body = client.post("/jobs", json=payload).json()

    assert body["issue_date"] == date.today().isoformat()


def test_job_status_after_processing(client):
    job_id = client.post("/jobs", json=make_payload()).json()["id"]

    body = client.get(f"/jobs/{job_id}").json()

    assert body["status"] == "completed"
    assert body["total"] == 3
    assert body["counts"] == {"pending": 0, "generated": 3, "failed": 0, "invalid": 0}
    assert body["progress_percent"] == 100.0
    assert body["completed_at"] is not None


def test_job_progress_before_and_after_processing(client, db):
    # Create the job directly so we can look at it before any work happens.
    job = services.create_job(db, JobCreate(**make_payload()))

    before = client.get(f"/jobs/{job.id}").json()
    assert before["status"] == "pending"
    assert before["counts"]["pending"] == 3
    assert before["progress_percent"] == 0.0
    assert before["completed_at"] is None

    services.process_job(job.id)

    after = client.get(f"/jobs/{job.id}").json()
    assert after["status"] == "completed"
    assert after["counts"]["generated"] == 3
    assert after["progress_percent"] == 100.0


def test_unfinished_jobs_are_resumed(client, db):
    job = services.create_job(db, JobCreate(**make_payload()))

    services.resume_unfinished_jobs()

    assert client.get(f"/jobs/{job.id}").json()["status"] == "completed"


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404

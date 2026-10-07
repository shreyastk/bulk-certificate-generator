"""A failure on one certificate must not stop the others."""

import pytest

from app import services
from tests.conftest import make_payload


@pytest.fixture
def fail_for_vikram(monkeypatch):
    """Make PDF generation blow up for one specific recipient."""
    real_render = services.render_certificate

    def flaky_render(path, **details):
        if details["recipient_name"] == "Vikram Shetty":
            raise OSError("disk full")
        real_render(path, **details)

    monkeypatch.setattr(services, "render_certificate", flaky_render)


def test_one_failure_does_not_stop_the_rest(client, fail_for_vikram):
    job = client.post("/jobs", json=make_payload()).json()

    status = client.get(f"/jobs/{job['id']}").json()
    assert status["status"] == "completed_with_errors"
    assert status["counts"] == {"pending": 0, "generated": 2, "failed": 1, "invalid": 0}
    assert status["progress_percent"] == 100.0


def test_failed_certificate_reports_its_error(client, fail_for_vikram):
    job = client.post("/jobs", json=make_payload()).json()

    failed = client.get(f"/jobs/{job['id']}/certificates", params={"status": "failed"}).json()
    assert failed["total"] == 1
    item = failed["items"][0]
    assert item["recipient_name"] == "Vikram Shetty"
    assert item["error"] == "OSError: disk full"
    assert item["download_url"] is None


def test_failed_certificate_cannot_be_downloaded(client, fail_for_vikram):
    job = client.post("/jobs", json=make_payload()).json()
    failed = client.get(f"/jobs/{job['id']}/certificates", params={"status": "failed"}).json()

    response = client.get(f"/certificates/{failed['items'][0]['id']}/download")

    assert response.status_code == 409


def test_job_fails_when_every_certificate_fails(client, monkeypatch):
    def always_fail(path, **details):
        raise RuntimeError("template broken")

    monkeypatch.setattr(services, "render_certificate", always_fail)

    job = client.post("/jobs", json=make_payload()).json()

    status = client.get(f"/jobs/{job['id']}").json()
    assert status["status"] == "failed"
    assert status["counts"]["failed"] == 3

"""Input validation: whole-request errors and per-recipient errors."""

import pytest

from app import config
from app.validation import validate_recipient, validate_recipients
from tests.conftest import make_payload


# --- Request-level problems reject the request with 422 -----------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"course_name": ""},
        {"course_name": "   "},
        {"issuer": ""},
        {"issue_date": "not-a-date"},
        {"recipients": []},
        {"recipients": "not-a-list"},
    ],
)
def test_invalid_request_is_rejected(client, overrides):
    response = client.post("/jobs", json=make_payload(**overrides))
    assert response.status_code == 422


def test_missing_required_fields_are_rejected(client):
    assert client.post("/jobs", json={"recipients": [{"name": "A", "email": "a@b.co"}]}).status_code == 422


def test_too_many_recipients_is_rejected(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_RECIPIENTS", 2)
    response = client.post("/jobs", json=make_payload())  # 3 recipients
    assert response.status_code == 422
    assert "at most 2" in response.json()["detail"]


# --- Recipient-level problems are recorded per row, the job still runs --------

def test_invalid_recipients_do_not_block_valid_ones(client):
    recipients = [
        {"name": "Asha Rao", "email": "asha@example.com"},
        {"name": "", "email": "noname@example.com"},
        {"name": "Bad Email", "email": "not-an-email"},
        {"name": "Asha Again", "email": "ASHA@example.com"},
        {"name": "No Email"},
        {"name": "Meera Nair", "email": "meera@example.com"},
    ]
    job = client.post("/jobs", json=make_payload(recipients)).json()

    status = client.get(f"/jobs/{job['id']}").json()
    assert status["status"] == "completed_with_errors"
    assert status["counts"] == {"pending": 0, "generated": 2, "failed": 0, "invalid": 4}

    invalid = client.get(f"/jobs/{job['id']}/certificates", params={"status": "invalid"}).json()
    errors = {item["recipient_email"]: item["error"] for item in invalid["items"]}
    assert errors == {
        "noname@example.com": "name is required",
        "not-an-email": "email is not a valid email address",
        "ASHA@example.com": "duplicate email for the same course in this request",
        "": "email is required",
    }


def test_job_with_only_invalid_recipients_fails(client):
    job = client.post("/jobs", json=make_payload([{"name": "", "email": "x"}])).json()

    status = client.get(f"/jobs/{job['id']}").json()
    assert status["status"] == "failed"
    assert status["counts"]["invalid"] == 1


# --- Validation rules ---------------------------------------------------------

@pytest.mark.parametrize(
    "name, email, expected",
    [
        ("Asha Rao", "asha@example.com", None),
        ("", "asha@example.com", "name is required"),
        ("A" * 101, "asha@example.com", "name must be at most 100 characters"),
        ("Asha", "", "email is required"),
        ("Asha", "asha@example", "email is not a valid email address"),
        ("Asha", "asha example@x.com", "email is not a valid email address"),
        ("Asha", "@example.com", "email is not a valid email address"),
    ],
)
def test_validate_recipient(name, email, expected):
    assert validate_recipient(name, email) == expected


def test_validate_recipients_trims_whitespace_and_flags_duplicates():
    results = validate_recipients(
        [("  Asha   Rao ", " asha@example.com ", None), ("Asha Rao", "Asha@Example.com", None)],
        default_course="Python Basics",
    )
    assert results == [
        ("Asha Rao", "asha@example.com", "Python Basics", None),
        ("Asha Rao", "Asha@Example.com", "Python Basics", "duplicate email for the same course in this request"),
    ]

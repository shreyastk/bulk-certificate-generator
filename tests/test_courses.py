"""Per-recipient courses: each recipient may carry their own course_name."""

from app import services
from tests.conftest import make_payload


def test_each_recipient_can_have_a_different_course(client, monkeypatch):
    rendered = {}
    real_render = services.render_certificate

    def spy(path, **details):
        rendered[details["recipient_name"]] = details["course_name"]
        real_render(path, **details)

    monkeypatch.setattr(services, "render_certificate", spy)
    recipients = [
        {"name": "Asha Rao", "email": "asha@example.com", "course_name": "Django Web Development"},
        {"name": "Vikram Shetty", "email": "vikram@example.com", "course_name": "SQL Fundamentals"},
    ]
    payload = make_payload(recipients)
    del payload["course_name"]  # no job-level default needed

    job = client.post("/jobs", json=payload).json()

    assert job["course_name"] is None
    assert client.get(f"/jobs/{job['id']}").json()["status"] == "completed"
    assert rendered == {"Asha Rao": "Django Web Development", "Vikram Shetty": "SQL Fundamentals"}
    items = client.get(f"/jobs/{job['id']}/certificates").json()["items"]
    assert {i["recipient_name"]: i["course_name"] for i in items} == rendered


def test_recipient_without_course_uses_the_job_default(client):
    recipients = [
        {"name": "Asha Rao", "email": "asha@example.com", "course_name": "Django Web Development"},
        {"name": "Meera Nair", "email": "meera@example.com"},
    ]
    job = client.post("/jobs", json=make_payload(recipients)).json()

    items = client.get(f"/jobs/{job['id']}/certificates").json()["items"]
    assert {i["recipient_name"]: i["course_name"] for i in items} == {
        "Asha Rao": "Django Web Development",
        "Meera Nair": "Python Basics",
    }


def test_recipient_with_no_course_anywhere_is_invalid(client):
    recipients = [
        {"name": "Asha Rao", "email": "asha@example.com", "course_name": "Django Web Development"},
        {"name": "Meera Nair", "email": "meera@example.com"},
    ]
    payload = make_payload(recipients)
    del payload["course_name"]

    job = client.post("/jobs", json=payload).json()

    status = client.get(f"/jobs/{job['id']}").json()
    assert status["status"] == "completed_with_errors"
    assert status["counts"]["generated"] == 1
    invalid = client.get(f"/jobs/{job['id']}/certificates", params={"status": "invalid"}).json()["items"]
    assert invalid[0]["recipient_name"] == "Meera Nair"
    assert invalid[0]["error"].startswith("course_name is required")


def test_same_person_can_receive_certificates_for_two_courses(client):
    recipients = [
        {"name": "Asha Rao", "email": "asha@example.com", "course_name": "Django Web Development"},
        {"name": "Asha Rao", "email": "asha@example.com", "course_name": "SQL Fundamentals"},
        {"name": "Asha Rao", "email": "asha@example.com", "course_name": "SQL Fundamentals"},
    ]
    job = client.post("/jobs", json=make_payload(recipients)).json()

    counts = client.get(f"/jobs/{job['id']}").json()["counts"]
    assert counts["generated"] == 2
    assert counts["invalid"] == 1  # the repeated SQL Fundamentals row

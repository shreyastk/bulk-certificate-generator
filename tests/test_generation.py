"""Certificate generation: the PDF template and the files a job produces."""

from datetime import date

from app.certificate import render_certificate
from tests.conftest import make_payload


def render(path, name="Asha Rao"):
    render_certificate(
        path,
        recipient_name=name,
        course_name="Python Basics",
        issuer="Acme Academy",
        issue_date=date(2026, 10, 7),
        certificate_id="test-id",
    )


def test_render_certificate_writes_a_pdf_with_recipient_details(tmp_path):
    path = tmp_path / "nested" / "certificate.pdf"

    render(path)

    content = path.read_bytes()
    assert content.startswith(b"%PDF")
    assert b"Certificate - Asha Rao" in content  # the PDF title metadata
    assert b"Acme Academy" in content            # the PDF author metadata


def test_render_certificate_handles_a_very_long_name(tmp_path):
    path = tmp_path / "long.pdf"

    render(path, name="Extremely Long Recipient Name " * 3)

    assert path.read_bytes().startswith(b"%PDF")


def test_job_generates_one_pdf_per_recipient(client, tmp_path):
    job = client.post("/jobs", json=make_payload()).json()

    files = list((tmp_path / job["id"]).glob("*.pdf"))
    assert len(files) == 3
    assert all(f.read_bytes().startswith(b"%PDF") for f in files)

    certificates = client.get(f"/jobs/{job['id']}/certificates").json()["items"]
    assert {c["status"] for c in certificates} == {"generated"}
    assert all(c["generated_at"] for c in certificates)

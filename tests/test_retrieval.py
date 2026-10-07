"""Retrieving generated certificates: listing, single PDF, and ZIP of a job."""

import io
import zipfile

from tests.conftest import make_payload


def test_list_certificates_for_a_job(client):
    job = client.post("/jobs", json=make_payload()).json()

    body = client.get(f"/jobs/{job['id']}/certificates").json()

    assert body["total"] == 3
    assert [c["recipient_name"] for c in body["items"]] == ["Asha Rao", "Meera Nair", "Vikram Shetty"]
    for item in body["items"]:
        assert item["status"] == "generated"
        assert item["download_url"] == f"/certificates/{item['id']}/download"


def test_list_certificates_supports_pagination(client):
    job = client.post("/jobs", json=make_payload()).json()

    page = client.get(f"/jobs/{job['id']}/certificates", params={"limit": 2, "offset": 2}).json()

    assert page["total"] == 3
    assert len(page["items"]) == 1


def test_list_certificates_rejects_unknown_status(client):
    job = client.post("/jobs", json=make_payload()).json()
    assert client.get(f"/jobs/{job['id']}/certificates", params={"status": "bogus"}).status_code == 422


def test_download_single_certificate(client):
    job = client.post("/jobs", json=make_payload()).json()
    item = client.get(f"/jobs/{job['id']}/certificates").json()["items"][0]

    response = client.get(item["download_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="Asha_Rao.pdf"' in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_get_certificate_details(client):
    job = client.post("/jobs", json=make_payload()).json()
    item = client.get(f"/jobs/{job['id']}/certificates").json()["items"][0]

    body = client.get(f"/certificates/{item['id']}").json()

    assert body["recipient_email"] == "asha@example.com"
    assert body["job_id"] == job["id"]


def test_download_all_certificates_as_zip(client):
    job = client.post("/jobs", json=make_payload()).json()

    response = client.get(f"/jobs/{job['id']}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == 3
        assert all(name.endswith(".pdf") for name in names)
        assert archive.read(names[0]).startswith(b"%PDF")


def test_zip_download_with_nothing_generated_returns_409(client):
    job = client.post("/jobs", json=make_payload([{"name": "", "email": "bad"}])).json()
    assert client.get(f"/jobs/{job['id']}/download").status_code == 409


def test_unknown_certificate_returns_404(client):
    assert client.get("/certificates/does-not-exist").status_code == 404
    assert client.get("/certificates/does-not-exist/download").status_code == 404

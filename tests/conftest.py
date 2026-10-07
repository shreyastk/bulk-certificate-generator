"""Shared test setup.

The environment variables are set before anything from `app` is imported, so
tests use a throwaway database and never touch the real one.
"""

import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="certgen-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_tmp / "generated")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """API client with empty tables and its own storage folder for every test.

    Starlette's TestClient runs background tasks before returning the response,
    so by the time `client.post("/jobs")` returns, the job has been processed.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path)
    return TestClient(app)


@pytest.fixture
def db(client):
    with SessionLocal() as session:
        yield session


def make_payload(recipients=None, **overrides):
    payload = {
        "course_name": "Python Basics",
        "issuer": "Acme Academy",
        "issue_date": "2026-10-07",
        "recipients": recipients
        if recipients is not None
        else [
            {"name": "Asha Rao", "email": "asha@example.com"},
            {"name": "Vikram Shetty", "email": "vikram@example.com"},
            {"name": "Meera Nair", "email": "meera@example.com"},
        ],
    }
    payload.update(overrides)
    return payload

"""Application settings, read from environment variables with sensible defaults."""

import os
from pathlib import Path

# Any SQLAlchemy URL works here, e.g. postgresql+psycopg://user:pass@host/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./certificates.db")

# Folder where generated PDFs are written: <STORAGE_DIR>/<job_id>/<certificate_id>.pdf
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./generated"))

# Upper bound on recipients in one request, so a single call cannot exhaust the server.
MAX_RECIPIENTS = int(os.getenv("MAX_RECIPIENTS", "10000"))

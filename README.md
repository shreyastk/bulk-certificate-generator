# Bulk Certificate Generator

A backend API that accepts a list of recipients in one request, generates a PDF
certificate for each from a single predefined template, tracks progress, and
lets the client download the results.

- **Python 3.11+**, **FastAPI**
- **SQLite** through **SQLAlchemy** (any relational database works by changing one URL)
- **ReportLab** for PDF generation
- **pytest** for tests

## Project layout

```
app/
  main.py         API routes
  services.py     create a job, process it, summarise progress
  certificate.py  the certificate template (draws the PDF)
  validation.py   per-recipient validation rules
  models.py       database tables: Job and Certificate
  schemas.py      request/response shapes
  database.py     engine and session setup
  config.py       settings read from environment variables
tests/            43 tests, grouped by the area they cover
sample_request.json               one course for everyone, with some invalid rows
sample_request_multi_course.json  a different course per recipient
```

## Setup

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the application

```bash
uvicorn app.main:app --reload
```

The API is at http://127.0.0.1:8000 and interactive docs (Swagger UI) are at
http://127.0.0.1:8000/docs, where every endpoint can be tried from the browser.

The database file `certificates.db` and the `generated/` folder are created
automatically on first start.

Optional settings (environment variables):

| Variable         | Default                       | Meaning                              |
|------------------|-------------------------------|--------------------------------------|
| `DATABASE_URL`   | `sqlite:///./certificates.db` | SQLAlchemy database URL              |
| `STORAGE_DIR`    | `./generated`                 | Where the PDFs are written           |
| `MAX_RECIPIENTS` | `10000`                       | Maximum recipients in one request    |

## Run the tests

```bash
python -m pytest
```

The tests use a temporary database and temporary folders, so they never touch
real data.

| Requirement                       | Where it is tested                         |
|-----------------------------------|--------------------------------------------|
| Creating a generation job         | `tests/test_jobs.py`                       |
| Input validation                  | `tests/test_validation.py`                 |
| Certificate generation            | `tests/test_generation.py`                 |
| Job status / progress             | `tests/test_jobs.py`                       |
| Individual certificate failure    | `tests/test_failures.py`                   |
| Retrieving generated certificates | `tests/test_retrieval.py`                  |
| Per-recipient courses             | `tests/test_courses.py`                    |

## API overview

| Method | Path                               | Purpose                                         |
|--------|------------------------------------|-------------------------------------------------|
| POST   | `/jobs`                            | Submit a bulk generation request                |
| GET    | `/jobs/{job_id}`                   | Job status, counts and progress                 |
| GET    | `/jobs/{job_id}/certificates`      | Per-recipient results (filter, paginate)        |
| GET    | `/jobs/{job_id}/download`          | All generated certificates of a job as a ZIP    |
| GET    | `/certificates/{id}`               | One certificate's details                       |
| GET    | `/certificates/{id}/download`      | One certificate as a PDF                        |
| GET    | `/health`                          | Liveness check                                  |

## Submit a certificate generation request

`sample_request.json` contains three valid recipients and three deliberately
invalid ones, so you can see both outcomes.

```bash
curl -X POST http://127.0.0.1:8000/jobs -H "Content-Type: application/json" -d @sample_request.json
```

(In PowerShell use `curl.exe` instead of `curl`.)

Request body:

```json
{
  "course_name": "Backend Engineering Bootcamp",
  "issuer": "Acme Academy",
  "issue_date": "2026-10-07",
  "recipients": [
    {"name": "Asha Rao", "email": "asha.rao@example.com"},
    {"name": "Vikram Shetty", "email": "vikram.shetty@example.com"}
  ]
}
```

`issue_date` is optional and defaults to today.

### A different course per recipient

Each recipient may carry their own `course_name`. It overrides the top-level
`course_name`, which then acts as the default for recipients without one and
can be left out entirely when every recipient has their own
(see `sample_request_multi_course.json`):

```json
{
  "issuer": "Acme Academy",
  "recipients": [
    {"name": "Asha Rao", "email": "asha.rao@example.com", "course_name": "Python Programming Fundamentals"},
    {"name": "Vikram Shetty", "email": "vikram.shetty@example.com", "course_name": "Data Structures and Algorithms"},
    {"name": "Asha Rao", "email": "asha.rao@example.com", "course_name": "Advanced Python Programming"}
  ]
}
```

The same person can appear once per course. The same email twice for the same
course is flagged as a duplicate, and a recipient with no course anywhere is
marked `invalid`.

The response is `202 Accepted`
and comes back immediately, before the certificates are generated:

```json
{
  "id": "45201950-9651-4e40-8d67-a731c0eedbbd",
  "status": "pending",
  "total": 6,
  "counts": {"pending": 3, "generated": 0, "failed": 0, "invalid": 3},
  "progress_percent": 50.0,
  "...": "..."
}
```

## Check progress

```bash
curl http://127.0.0.1:8000/jobs/<job_id>
```

```json
{
  "id": "45201950-9651-4e40-8d67-a731c0eedbbd",
  "status": "completed_with_errors",
  "total": 6,
  "counts": {"pending": 0, "generated": 3, "failed": 0, "invalid": 3},
  "progress_percent": 100.0,
  "completed_at": "2026-10-07T09:14:38.624083"
}
```

Job statuses:

| Status                  | Meaning                                            |
|-------------------------|----------------------------------------------------|
| `pending`               | Accepted, not started                              |
| `processing`            | Certificates are being generated                   |
| `completed`             | Every recipient got a certificate                  |
| `completed_with_errors` | Some certificates generated, some did not          |
| `failed`                | No certificate could be generated                  |

Certificate statuses: `pending`, `generated`, `failed` (valid data, but
generation raised an error) and `invalid` (the recipient data failed
validation, so generation was never attempted).

To see exactly which recipients had problems and why:

```bash
curl "http://127.0.0.1:8000/jobs/<job_id>/certificates?status=invalid"
curl "http://127.0.0.1:8000/jobs/<job_id>/certificates?status=failed"
```

Each item carries an `error` message, for example `"name is required"` or
`"OSError: disk full"`. The list also accepts `limit` (default 100, max 1000)
and `offset`.

## Retrieve generated certificates

One certificate (the `download_url` is included in each generated item of the list):

```bash
curl -o certificate.pdf http://127.0.0.1:8000/certificates/<certificate_id>/download
```

Every generated certificate of a job in one ZIP:

```bash
curl -o certificates.zip http://127.0.0.1:8000/jobs/<job_id>/download
```

Asking for a certificate that is not `generated` returns `409 Conflict`; an
unknown id returns `404`.

## Design decisions

**Background processing instead of synchronous.** `POST /jobs` saves the job,
returns `202` with a job id, and generation runs afterwards in a worker thread
using FastAPI's built-in `BackgroundTasks`. A synchronous endpoint would hold
the HTTP connection open for the whole batch, risk client and proxy timeouts,
and give no way to report progress. I chose `BackgroundTasks` over Celery or RQ
because it needs no extra infrastructure (no Redis, no separate worker process),
which keeps the project easy to run and review. The trade-off is that work runs
inside the web process, so it does not scale across machines. `process_job` only
takes a job id and opens its own database session, so moving it to a real task
queue later means changing the one line that schedules it.

**One database row per recipient.** A `Job` has many `Certificate` rows, each
with its own status and error. This is what makes progress tracking, partial
failure reporting and retrieval simple: they are all queries on that table.

**Counts are computed, not stored.** Job counts come from a single
`GROUP BY status` query rather than counter columns on the job, so they can
never drift out of sync with the actual certificate rows.

**Two levels of validation.**
- Problems with the request as a whole (missing course name, empty recipient
  list, wrong types, too many recipients) reject it with `422`, because there is
  nothing sensible to generate.
- Problems with an individual recipient (blank name, malformed email, duplicate
  email for the same course, no course given anywhere) do not reject the request. That recipient is stored
  as `invalid` with the reason, and the rest of the batch continues. For a list
  of thousands of people, refusing everything because of one typo would be a
  poor experience.

**Course stored on each certificate.** The course a certificate is for is
resolved once, when the job is created (the recipient's own course, otherwise
the job default), and saved on the certificate row. Generation then reads one
field and never needs to know where the course came from.

**Failure isolation.** Each certificate is generated inside its own
`try/except`. An error is recorded on that row (`failed` plus the error message)
and the loop moves on. Progress is committed after every certificate, so the
status endpoint reflects real progress while the job runs.

**Safe to re-run.** `process_job` only picks up `pending` certificates, so
running it twice never regenerates or duplicates anything. On startup the app
uses this to resume jobs that were interrupted by a restart.

**Files on disk, paths in the database.** PDFs are written to
`STORAGE_DIR/<job_id>/<certificate_id>.pdf` and only the relative path is stored
in the database. Storing PDFs as database blobs would bloat the database; a
relative path means the storage folder can be moved.

**UUIDs as ids.** Job and certificate ids are random UUIDs rather than
sequential numbers, so download links cannot be guessed by counting up.

**SQLite by default.** It satisfies the relational-database requirement with
zero setup. Because all access goes through SQLAlchemy, switching to PostgreSQL
or MySQL is a matter of setting `DATABASE_URL` and installing the driver.

## Performance

Measured locally: a request with 5,000 recipients was accepted in about 0.5
seconds and all 5,000 PDFs were generated in about 16 seconds (roughly 300 per
second), with progress visible throughout.

## Known limitations and possible next steps

- **Single process.** Background work lives in the web process. With several
  server workers, the startup resume step could pick up the same job twice. A
  task queue (Celery/RQ) with a dedicated worker is the fix for production.
- **No migrations.** Tables are created with `create_all`, which does not alter
  existing tables. After changing `models.py`, delete `certificates.db` (or add
  Alembic) so the schema is rebuilt.
- **No authentication.** Anyone who knows an id can download the certificate.
- **Latin characters only.** The template uses the built-in Helvetica font,
  which does not cover scripts such as Kannada or Devanagari. Supporting them
  means bundling and registering a Unicode TTF font in `certificate.py`.
- **ZIP is built in memory.** Fine for thousands of ~2 KB PDFs; very large jobs
  would be better served by streaming the archive or pre-building it.
- **No retry endpoint.** Because processing is safe to re-run, a
  `POST /jobs/{id}/retry` that resets `failed` rows to `pending` and schedules
  `process_job` again would be a small addition.
- **Other ideas:** CSV upload as an alternative to JSON, emailing certificates
  to recipients, and a public verification endpoint keyed by certificate id.

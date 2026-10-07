"""HTTP API for the bulk certificate generator."""

import io
import re
import threading
import zipfile
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config, services
from app.database import Base, engine, get_db
from app.models import Certificate, CertificateStatus, Job
from app.schemas import CertificateList, CertificateOut, JobCreate, JobOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    # Pick up jobs that were cut short by a previous shutdown, without delaying startup.
    threading.Thread(target=services.resume_unfinished_jobs, daemon=True).start()
    yield


app = FastAPI(title="Bulk Certificate Generator", version="1.0.0", lifespan=lifespan)


def get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def to_certificate_out(certificate: Certificate) -> CertificateOut:
    out = CertificateOut.model_validate(certificate)
    if certificate.status == CertificateStatus.GENERATED:
        out.download_url = f"/certificates/{certificate.id}/download"
    return out


def safe_filename(name: str) -> str:
    """Turn a recipient name into something safe to use as a file name."""
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "certificate"


@app.get("/", include_in_schema=False)
def root():
    """Send browsers that open the bare URL to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Accept a batch of recipients and start generating in the background.

    Responds immediately with 202 and a job id; poll GET /jobs/{id} for progress.
    """
    if len(payload.recipients) > config.MAX_RECIPIENTS:
        raise HTTPException(
            422,
            f"Too many recipients: at most {config.MAX_RECIPIENTS} per request",
        )
    job = services.create_job(db, payload)
    background_tasks.add_task(services.process_job, job.id)
    return services.job_summary(db, job)


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Job status, per-status counts and progress percentage."""
    return services.job_summary(db, get_job_or_404(db, job_id))


@app.get("/jobs/{job_id}/certificates", response_model=CertificateList)
def list_certificates(
    job_id: str,
    status_filter: str | None = Query(
        default=None, alias="status", pattern="^(pending|generated|failed|invalid)$"
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Per-recipient results, including the error for failed or invalid ones."""
    get_job_or_404(db, job_id)
    conditions = [Certificate.job_id == job_id]
    if status_filter:
        conditions.append(Certificate.status == status_filter)

    total = db.scalar(select(func.count()).select_from(Certificate).where(*conditions))
    certificates = db.scalars(
        select(Certificate)
        .where(*conditions)
        .order_by(Certificate.recipient_name, Certificate.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return CertificateList(
        total=total,
        limit=limit,
        offset=offset,
        items=[to_certificate_out(c) for c in certificates],
    )


@app.get("/certificates/{certificate_id}", response_model=CertificateOut)
def get_certificate(certificate_id: str, db: Session = Depends(get_db)):
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    return to_certificate_out(certificate)


@app.get("/certificates/{certificate_id}/download")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    """Download one generated certificate as a PDF."""
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    if certificate.status != CertificateStatus.GENERATED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Certificate is not available (status: {certificate.status})",
        )
    path = config.STORAGE_DIR / certificate.file_path
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate file is missing from storage")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{safe_filename(certificate.recipient_name)}.pdf",
    )


@app.get("/jobs/{job_id}/download")
def download_job_zip(job_id: str, db: Session = Depends(get_db)):
    """Download every generated certificate of a job as one ZIP file."""
    get_job_or_404(db, job_id)
    certificates = db.scalars(
        select(Certificate).where(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.GENERATED,
        )
    ).all()
    if not certificates:
        raise HTTPException(status.HTTP_409_CONFLICT, "No certificates have been generated for this job")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for certificate in certificates:
            path = config.STORAGE_DIR / certificate.file_path
            if path.is_file():
                # The id suffix keeps names unique when two recipients share a name.
                name = f"{safe_filename(certificate.recipient_name)}_{certificate.id[:8]}.pdf"
                archive.write(path, arcname=name)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates_{job_id}.zip"'},
    )

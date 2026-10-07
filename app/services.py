"""Business logic: creating jobs, generating certificates, summarising progress."""

import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.certificate import render_certificate
from app.database import SessionLocal
from app.models import Certificate, CertificateStatus, Job, JobStatus, utcnow
from app.schemas import JobCreate, JobOut, StatusCounts
from app.validation import validate_recipients

logger = logging.getLogger(__name__)


def create_job(db: Session, payload: JobCreate) -> Job:
    """Store the job and one certificate row per recipient.

    Valid recipients start as "pending"; invalid ones are stored as "invalid"
    with the reason, so the client can see exactly which rows were rejected.
    """
    job = Job(
        course_name=payload.course_name,
        issuer=payload.issuer,
        issue_date=payload.issue_date or date.today(),
    )
    checked = validate_recipients(
        [(r.name, r.email, r.course_name) for r in payload.recipients],
        default_course=payload.course_name,
    )
    for name, email, course, error in checked:
        job.certificates.append(
            Certificate(
                recipient_name=name[:255],
                recipient_email=email[:320],
                course_name=course[:150],
                status=CertificateStatus.INVALID if error else CertificateStatus.PENDING,
                error=error,
            )
        )
    db.add(job)
    db.commit()
    return job


def process_job(job_id: str) -> None:
    """Generate every pending certificate of a job. Runs in a background thread.

    It opens its own database session because the request that created the job
    has already finished. It only touches "pending" certificates, so running it
    again on the same job (for example after a restart) is safe.
    """
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.PROCESSING
        db.commit()

        pending = db.scalars(
            select(Certificate).where(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.PENDING,
            )
        ).all()

        for certificate in pending:
            # Each certificate has its own try/except: one failure is recorded
            # on that row and the loop moves on to the next recipient.
            try:
                relative_path = f"{job.id}/{certificate.id}.pdf"
                render_certificate(
                    config.STORAGE_DIR / relative_path,
                    recipient_name=certificate.recipient_name,
                    course_name=certificate.course_name,
                    issuer=job.issuer,
                    issue_date=job.issue_date,
                    certificate_id=certificate.id,
                )
                certificate.file_path = relative_path
                certificate.status = CertificateStatus.GENERATED
                certificate.generated_at = utcnow()
            except Exception as exc:
                logger.exception("Certificate %s failed", certificate.id)
                certificate.status = CertificateStatus.FAILED
                certificate.error = f"{type(exc).__name__}: {exc}"
            # Commit after each one so progress is visible while the job runs.
            db.commit()

        counts = count_by_status(db, job_id)
        job.status = final_job_status(counts)
        job.completed_at = utcnow()
        db.commit()


def final_job_status(counts: StatusCounts) -> str:
    problems = counts.failed + counts.invalid
    if counts.generated and not problems:
        return JobStatus.COMPLETED
    if counts.generated:
        return JobStatus.COMPLETED_WITH_ERRORS
    return JobStatus.FAILED


def count_by_status(db: Session, job_id: str) -> StatusCounts:
    """Count a job's certificates per status with a single GROUP BY query."""
    rows = db.execute(
        select(Certificate.status, func.count())
        .where(Certificate.job_id == job_id)
        .group_by(Certificate.status)
    ).all()
    return StatusCounts(**{status: count for status, count in rows})


def job_summary(db: Session, job: Job) -> JobOut:
    counts = count_by_status(db, job.id)
    total = counts.pending + counts.generated + counts.failed + counts.invalid
    done = total - counts.pending
    return JobOut(
        id=job.id,
        status=job.status,
        course_name=job.course_name,
        issuer=job.issuer,
        issue_date=job.issue_date,
        total=total,
        counts=counts,
        progress_percent=round(100 * done / total, 1) if total else 100.0,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def resume_unfinished_jobs() -> None:
    """Called at startup: continue jobs that were interrupted by a restart."""
    with SessionLocal() as db:
        job_ids = db.scalars(
            select(Job.id).where(Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
        ).all()
    for job_id in job_ids:
        logger.info("Resuming unfinished job %s", job_id)
        process_job(job_id)

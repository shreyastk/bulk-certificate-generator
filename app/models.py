"""Database tables: one Job has many Certificates (one per recipient)."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobStatus:
    PENDING = "pending"                              # accepted, not started yet
    PROCESSING = "processing"                        # certificates are being generated
    COMPLETED = "completed"                          # every recipient got a certificate
    COMPLETED_WITH_ERRORS = "completed_with_errors"  # some succeeded, some did not
    FAILED = "failed"                                # no certificate could be generated


class CertificateStatus:
    PENDING = "pending"      # waiting to be generated
    GENERATED = "generated"  # PDF is on disk and can be downloaded
    FAILED = "failed"        # data was valid but generation raised an error
    INVALID = "invalid"      # recipient data failed validation; never attempted


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    # Stored without tzinfo because SQLite drops it anyway; all timestamps are UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Default course for the job; None when every recipient brings their own.
    course_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    issuer: Mapped[str] = mapped_column(String(150))
    issue_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    certificates: Mapped[list["Certificate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    recipient_name: Mapped[str] = mapped_column(String(255))
    recipient_email: Mapped[str] = mapped_column(String(320))
    # The course printed on this certificate: the recipient's own, or the job default.
    course_name: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), default=CertificateStatus.PENDING, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Path of the PDF relative to STORAGE_DIR, set once the file exists.
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped[Job] = relationship(back_populates="certificates")

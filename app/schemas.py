"""Request and response shapes for the API."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class RecipientIn(BaseModel):
    # Deliberately loose: a blank name or malformed email must not reject the whole
    # request. Each recipient is checked individually in app/validation.py and bad
    # ones are recorded as "invalid" while the rest of the job carries on.
    name: str = ""
    email: str = ""
    # Optional: this recipient's own course. Falls back to the job's course_name.
    course_name: str | None = None


class JobCreate(BaseModel):
    # Default course for recipients that do not specify their own. May be left
    # out when every recipient carries a course_name.
    course_name: RequiredText | None = None
    issuer: RequiredText
    issue_date: date | None = Field(default=None, description="Defaults to today if omitted")
    recipients: list[RecipientIn] = Field(min_length=1)


class StatusCounts(BaseModel):
    pending: int = 0
    generated: int = 0
    failed: int = 0
    invalid: int = 0


class JobOut(BaseModel):
    id: str
    status: str
    course_name: str | None
    issuer: str
    issue_date: date
    total: int
    counts: StatusCounts
    progress_percent: float
    created_at: datetime
    completed_at: datetime | None


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    course_name: str
    status: str
    error: str | None
    generated_at: datetime | None
    download_url: str | None = None


class CertificateList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CertificateOut]

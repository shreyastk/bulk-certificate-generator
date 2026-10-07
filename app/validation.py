"""Per-recipient validation.

Returns an error message for each bad recipient instead of raising, so one bad
row never blocks the rest of the batch.
"""

import re

# Intentionally simple: something@something.tld with no spaces.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254
MAX_COURSE_LENGTH = 150


def validate_recipient(name: str, email: str) -> str | None:
    """Return None if the recipient is valid, otherwise a human-readable reason."""
    if not name:
        return "name is required"
    if len(name) > MAX_NAME_LENGTH:
        return f"name must be at most {MAX_NAME_LENGTH} characters"
    if not email:
        return "email is required"
    if len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email):
        return "email is not a valid email address"
    return None


def validate_recipients(
    recipients: list[tuple[str, str, str | None]], default_course: str | None = None
) -> list[tuple[str, str, str, str | None]]:
    """Clean and check every (name, email, course) triple.

    A recipient without a course of their own gets `default_course`. Returns
    (name, email, course, error) for each input, in the same order. The same
    email twice for the same course is flagged so nobody gets a duplicate
    certificate; the same person may still appear once per course.
    """
    results = []
    seen = set()
    for raw_name, raw_email, raw_course in recipients:
        name = " ".join(raw_name.split())  # trim and collapse inner whitespace
        email = raw_email.strip()
        course = " ".join((raw_course or "").split()) or (default_course or "")

        error = validate_recipient(name, email)
        if error is None and not course:
            error = "course_name is required (none given for this recipient or the request)"
        if error is None and len(course) > MAX_COURSE_LENGTH:
            error = f"course_name must be at most {MAX_COURSE_LENGTH} characters"
        if error is None:
            key = (email.lower(), course.lower())
            if key in seen:
                error = "duplicate email for the same course in this request"
            else:
                seen.add(key)
        results.append((name, email, course, error))
    return results

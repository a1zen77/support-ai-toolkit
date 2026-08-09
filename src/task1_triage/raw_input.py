"""
Handles raw, unstructured ticket text (no subject/body already split out).
The brief requires triage to "accept a raw ticket as input (text or JSON
with subject + body)" - this module covers the free-text path, heuristically
splitting it into subject+body so the rest of the pipeline doesn't need to
know the difference.
"""

from __future__ import annotations

import re

from src.common.schemas import TicketInput

_SUBJECT_LABEL_RE = re.compile(r"(?i)^subject:\s*(.+)$")
_BODY_LABEL_RE = re.compile(r"(?i)^body:\s*")
_FIRST_SENTENCE_RE = re.compile(r"^(.{10,120}?[.!?])(\s|$)")

MAX_DERIVED_SUBJECT_LEN = 80


def parse_raw_ticket_text(text: str) -> TicketInput:
    """
    Heuristically splits free-text into (subject, body):
      1. Explicit "Subject: ..." / "Body: ..." labels, if present.
      2. Otherwise, a short first line is treated as the subject, remaining
         lines as the body.
      3. Otherwise (single block of text, no clear first line), derive a
         short subject from the first sentence or first ~80 chars, and use
         the full text as the body regardless, so no content is lost.
    """
    text = text.strip()
    if not text:
        raise ValueError("raw ticket text is empty")

    lines = text.splitlines()

    # Case 1: explicit "Subject:" label on the first line
    m = _SUBJECT_LABEL_RE.match(lines[0])
    if m:
        subject = m.group(1).strip()
        remainder = "\n".join(lines[1:]).strip()
        remainder = _BODY_LABEL_RE.sub("", remainder).strip()
        return TicketInput(subject=subject, body=remainder or subject)

    # Case 2: short first line + more lines -> treat as subject/body split
    if len(lines) > 1 and len(lines[0]) <= 150:
        subject = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        return TicketInput(subject=subject, body=body or subject)

    # Case 3: no clear structure - derive a short subject, keep full text as body
    m = _FIRST_SENTENCE_RE.match(text)
    if m:
        subject = m.group(1).strip()
    else:
        subject = text[:MAX_DERIVED_SUBJECT_LEN].strip()
        if len(text) > MAX_DERIVED_SUBJECT_LEN:
            subject += "..."

    return TicketInput(subject=subject, body=text)


if __name__ == "__main__":
    # Quick manual check: `python -m src.task1_triage.raw_input`
    examples = [
        "Subject: Cannot log in\n\nBody: I keep getting AUTH_TOKEN_EXPIRED when I try to sign in via SSO.",
        "Sync keeps failing\nEvery time I upload a batch of files, CloudSync throws a timeout error and nothing syncs.",
        "my dashboard has been blank for two days now and nobody on my team can see any reports which is a huge problem for us",
    ]
    for ex in examples:
        parsed = parse_raw_ticket_text(ex)
        print(f"RAW: {ex[:60]}...")
        print(f"  subject: {parsed.subject!r}")
        print(f"  body:    {parsed.body!r}")
        print()
"""EML parser - turns raw email bytes/text into a structured Email object.

Uses Python's stdlib `email` module so the kit has no dependencies. Works
with both single .eml files and concatenated mbox dumps (Gmail / Outlook
exports). For real production use you'd typically wire this to an IMAP or
Microsoft Graph poller upstream - the parsed shape is the same.
"""

from __future__ import annotations

import email
import email.policy
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass
class Email:
    """Structured email after parsing."""
    message_id: str
    sender_name: str
    sender_email: str
    to: list[str]
    subject: str
    body_text: str
    received_at: str  # ISO-8601, best-effort
    raw_headers: dict[str, str] = field(default_factory=dict)

    def preview(self, n: int = 200) -> str:
        snippet = self.body_text.strip().replace("\n", " ")
        return snippet[:n] + ("..." if len(snippet) > n else "")

    @property
    def sender_domain(self) -> str:
        if "@" not in self.sender_email:
            return ""
        return self.sender_email.split("@", 1)[1].lower()


def parse_eml_bytes(raw: bytes | str) -> Email:
    """Parse a single .eml message into an Email."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    return _from_message(msg)


def parse_eml_file(path: Path | str) -> Email:
    p = Path(path)
    return parse_eml_bytes(p.read_bytes())


def parse_mbox(path: Path | str) -> list[Email]:
    """Parse an mbox file into a list of Emails (one per message)."""
    return list(_iter_mbox(Path(path)))


def _iter_mbox(path: Path) -> Iterator[Email]:
    """Split an mbox file on 'From ' separator lines and parse each chunk.

    Avoids the stdlib `mailbox` module (which writes a `.mbox.lock` file
    next to the source) so the kit stays purely read-only against fixtures.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    # Split on lines that start with "From " - the mbox separator.
    chunks = re.split(r"(?m)^From \S+.*$", text)
    # First chunk is whatever was before the first "From " line (usually empty).
    for chunk in chunks[1:]:
        chunk = chunk.strip()
        if not chunk:
            continue
        yield parse_eml_bytes(chunk.encode("utf-8"))


def _from_message(msg: email.message.EmailMessage) -> Email:
    sender_raw = msg.get("From", "")
    sender_name, sender_email = _parse_address(sender_raw)
    to = [a.strip() for a in (msg.get("To", "") or "").split(",") if a.strip()]
    return Email(
        message_id=msg.get("Message-ID", "").strip("<>"),
        sender_name=sender_name,
        sender_email=sender_email,
        to=to,
        subject=msg.get("Subject", "(no subject)"),
        body_text=_body_text(msg),
        received_at=_normalise_date(msg.get("Date", "")),
        raw_headers={k: v for k, v in msg.items()},
    )


def _parse_address(addr: str) -> tuple[str, str]:
    """Crude name/email split. 'Alice <alice@x.com>' -> ('Alice', 'alice@x.com')."""
    m = re.match(r"\s*(.+?)\s*<\s*(.+?)\s*>\s*$", addr)
    if m:
        return m.group(1).strip().strip('"'), m.group(2).strip().lower()
    addr = addr.strip()
    if "@" in addr:
        return "", addr.lower()
    return addr, ""


def _body_text(msg: email.message.EmailMessage) -> str:
    """Pull the plain-text body. Falls back to walking parts if multipart."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return msg.get_payload() or ""


def _normalise_date(date_str: str) -> str:
    """Best-effort: parse RFC-2822 date into ISO-8601. Returns raw string on failure."""
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.isoformat()
    except (TypeError, ValueError):
        return date_str.strip()

"""Tests for the EML parser."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from email_triage.parser import parse_eml_file, parse_eml_bytes  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parses_sender_name_and_email():
    e = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    assert e.sender_name == "Maya Chen"
    assert e.sender_email == "maya.chen@acme-prospects.com"


def test_parses_subject():
    e = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    assert "Pricing" in e.subject


def test_parses_body_text():
    e = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    assert "annual contract" in e.body_text
    assert "Maya Chen" in e.body_text


def test_extracts_message_id_without_brackets():
    e = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    assert e.message_id == "CAJk_demo-001@mail.example.com"


def test_sender_domain_extracted():
    e = parse_eml_file(FIXTURES / "06-internal.eml")
    assert e.sender_domain == "example.com"


def test_received_at_is_iso_format_when_parseable():
    e = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    # RFC-2822 date "Fri, 27 Jun 2026 09:14:00 -0700" → ISO with tz
    assert "2026-06-27" in e.received_at


def test_preview_truncates_with_ellipsis():
    e = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    preview = e.preview(50)
    assert len(preview) <= 53  # 50 + "..."
    assert preview.endswith("...")


def test_handles_email_with_no_sender_name():
    raw = (
        "From: support@example.com\r\n"
        "To: user@example.com\r\n"
        "Subject: Hi\r\n"
        "Message-ID: <test-1@example.com>\r\n"
        "Date: Fri, 27 Jun 2026 09:00:00 -0700\r\n"
        "\r\n"
        "Hello there.\r\n"
    )
    e = parse_eml_bytes(raw)
    assert e.sender_name == ""
    assert e.sender_email == "support@example.com"


def test_handles_missing_date_gracefully():
    raw = (
        "From: foo@example.com\r\n"
        "To: bar@example.com\r\n"
        "Subject: nodate\r\n"
        "\r\n"
        "Body.\r\n"
    )
    e = parse_eml_bytes(raw)
    assert e.received_at in ("", None) or isinstance(e.received_at, str)

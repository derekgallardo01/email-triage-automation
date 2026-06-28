"""Tests for the reply drafter."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from email_triage.drafter import Drafter  # noqa: E402
from email_triage.parser import Email, parse_eml_file  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_drafter_returns_none_for_class_with_no_template(tmp_path):
    drafter = Drafter(prompts_dir=tmp_path)
    email_obj = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    result = drafter.draft(email_obj, "sales_lead")
    assert result is None


def test_drafter_substitutes_sender_first_name():
    drafter = Drafter()
    email_obj = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    result = drafter.draft(email_obj, "sales_lead")
    assert result is not None
    assert "Maya" in result.body
    assert "Maya Chen" not in result.body.split("\n")[0]  # first line is "Hi Maya," not "Hi Maya Chen,"


def test_drafter_subject_has_re_prefix():
    drafter = Drafter()
    email_obj = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    result = drafter.draft(email_obj, "sales_lead")
    assert result.subject.startswith("Re: ")


def test_drafter_substitutes_original_subject_in_body():
    drafter = Drafter()
    email_obj = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    result = drafter.draft(email_obj, "sales_lead")
    assert "Pricing" in result.body  # template references {subject}


def test_drafter_substitutes_body_excerpt():
    drafter = Drafter()
    email_obj = parse_eml_file(FIXTURES / "02-support-request.eml")
    result = drafter.draft(email_obj, "support_request")
    assert "Safari" in result.body  # the support template includes {body_excerpt}


def test_drafter_handles_email_with_no_sender_name():
    drafter = Drafter()
    email_obj = Email(message_id="x", sender_name="", sender_email="x@x.com",
                       to=[], subject="trial?", body_text="want a demo",
                       received_at="")
    result = drafter.draft(email_obj, "sales_lead")
    # Should fall back to a default greeting (template formatter must not crash)
    assert result is not None
    assert result.error is None


def test_drafter_in_reply_to_message_id_matches_source():
    drafter = Drafter()
    email_obj = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    result = drafter.draft(email_obj, "sales_lead")
    assert result.in_reply_to_message_id == email_obj.message_id


def test_drafter_default_backend_is_substitution():
    saved = os.environ.pop("EMAIL_TRIAGE_LLM", None)
    try:
        drafter = Drafter()
        assert drafter.backend == "substitution"
    finally:
        if saved is not None:
            os.environ["EMAIL_TRIAGE_LLM"] = saved


def test_substitution_backend_returns_deterministic_output():
    """Two runs over the same email should produce identical drafts."""
    drafter = Drafter()
    email_obj = parse_eml_file(FIXTURES / "01-sales-lead.eml")
    a = drafter.draft(email_obj, "sales_lead")
    b = drafter.draft(email_obj, "sales_lead")
    assert a.body == b.body

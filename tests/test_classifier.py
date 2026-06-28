"""Tests for the email classifier + router."""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from email_triage.catalog import Catalog, EmailClass, default_catalog  # noqa: E402
from email_triage.classifier import Classifier, route  # noqa: E402
from email_triage.parser import parse_eml_file  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _classify(name: str, internal_domains=None):
    clf = Classifier(internal_domains=internal_domains or [])
    email_obj = parse_eml_file(FIXTURES / name)
    return clf, email_obj, clf.classify(email_obj)


# ---------- Catalog validation ----------------------------------------------

def test_default_catalog_validates_clean():
    assert default_catalog().validate() == []


def test_catalog_catches_duplicate_names():
    c = Catalog(classes=[
        EmailClass("a", "q1", 24, ["x"], False),
        EmailClass("a", "q2", 24, ["y"], False),
    ])
    assert any("Duplicate" in p for p in c.validate())


def test_catalog_catches_empty_keywords():
    c = Catalog(classes=[EmailClass("a", "q", 24, [], False)])
    assert any("zero keywords" in p for p in c.validate())


# ---------- Classification accuracy -----------------------------------------

def test_sales_lead_fixture_classifies_correctly():
    _, _, r = _classify("01-sales-lead.eml")
    assert r.label == "sales_lead"
    assert r.confidence > 0.7


def test_support_fixture_classifies_correctly():
    _, _, r = _classify("02-support-request.eml")
    assert r.label == "support_request"


def test_billing_fixture_classifies_correctly():
    _, _, r = _classify("03-billing-question.eml")
    assert r.label == "billing_question"


def test_feature_request_fixture_classifies_correctly():
    _, _, r = _classify("04-feature-request.eml")
    assert r.label == "feature_request"


def test_newsletter_fixture_classifies_correctly():
    _, _, r = _classify("05-newsletter.eml")
    assert r.label == "newsletter_or_marketing"


def test_internal_fixture_classifies_correctly_via_domain():
    """Internal-domain override should kick in for senders on example.com."""
    _, _, r = _classify("06-internal.eml", internal_domains=["example.com"])
    assert r.label == "internal"
    assert r.confidence == 1.0
    assert any("sender_domain" in kw for kw in r.matched_keywords)


def test_ambiguous_fixture_falls_through_to_unknown():
    _, _, r = _classify("07-ambiguous.eml")
    assert r.label == "unknown"
    assert r.review_required is True


# ---------- Subject vs body weighting ---------------------------------------

def test_subject_keyword_weighs_more_than_body_keyword():
    """A keyword in the subject should beat one in the body."""
    from email_triage.parser import Email

    # Build two synthetic emails: one with 'pricing' in subject, one in body.
    e_subject = Email(message_id="1", sender_name="X", sender_email="x@x.com",
                      to=[], subject="pricing question", body_text="hello",
                      received_at="")
    e_body = Email(message_id="2", sender_name="X", sender_email="x@x.com",
                   to=[], subject="hello", body_text="pricing question",
                   received_at="")
    clf = Classifier()
    r_subj = clf.classify(e_subject)
    r_body = clf.classify(e_body)
    # Both should pick sales_lead; subject should give higher confidence.
    assert r_subj.label == "sales_lead"
    assert r_body.label == "sales_lead"
    assert r_subj.confidence >= r_body.confidence


# ---------- Router behaviour ------------------------------------------------

def test_router_routes_sales_lead_to_sales_pipeline_with_drafts_reply():
    clf, _, r = _classify("01-sales-lead.eml")
    d = route(r, clf.catalog)
    assert d.queue == "sales_pipeline"
    assert d.drafts_reply is True
    assert d.review_required is False


def test_router_sends_billing_to_billing_queue_no_draft():
    clf, _, r = _classify("03-billing-question.eml")
    d = route(r, clf.catalog)
    assert d.queue == "billing_team"
    assert d.drafts_reply is False


def test_router_sends_unknown_to_human_review():
    clf, _, r = _classify("07-ambiguous.eml")
    d = route(r, clf.catalog)
    assert d.queue == "human_review"
    assert d.handoff_reason == "no matching class"


def test_invalid_catalog_raises_at_init():
    bad = Catalog(classes=[EmailClass("a", "q", -1, [], False)])
    with pytest.raises(ValueError):
        Classifier(catalog=bad)

"""Email class catalog - what categories exist, how they route.

Each class declares:
  - name: the label the classifier emits
  - queue: downstream destination
  - sla_hours: response SLA
  - keywords: signals the rules classifier looks for (in subject + body)
  - drafts_reply: whether the drafter should auto-draft a reply for this class
  - description: used in LLM prompts and the `list-classes` CLI output

A class with `drafts_reply=True` must have a corresponding template file in
prompts/<name>.txt (the drafter reads from there).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmailClass:
    name: str
    queue: str
    sla_hours: int
    keywords: list[str]
    drafts_reply: bool
    description: str = ""


@dataclass
class Catalog:
    classes: list[EmailClass]

    def by_name(self, name: str) -> EmailClass | None:
        return next((c for c in self.classes if c.name == name), None)

    def names(self) -> list[str]:
        return [c.name for c in self.classes]

    def validate(self) -> list[str]:
        problems: list[str] = []
        seen = set()
        for c in self.classes:
            if c.name in seen:
                problems.append(f"Duplicate class name: {c.name}")
            seen.add(c.name)
            if not c.keywords:
                problems.append(f"Class '{c.name}' has zero keywords.")
            if c.sla_hours <= 0:
                problems.append(f"Class '{c.name}' has non-positive sla_hours.")
        if not self.classes:
            problems.append("Catalog has zero classes.")
        return problems


def default_catalog() -> Catalog:
    """A worked catalog for a small B2B SaaS support mailbox."""
    return Catalog(classes=[
        EmailClass(
            name="sales_lead",
            queue="sales_pipeline",
            sla_hours=4,
            keywords=["pricing", "quote", "demo", "trial", "interested",
                      "evaluating", "purchase", "buy", "license cost",
                      "annual contract"],
            drafts_reply=True,
            description="Inbound sales enquiry - pricing, demo request, trial request.",
        ),
        EmailClass(
            name="support_request",
            queue="support_l1",
            sla_hours=8,
            keywords=["bug", "error", "broken", "not working", "doesn't work",
                      "issue", "problem", "help", "stuck", "can't",
                      "stopped working"],
            drafts_reply=True,
            description="Customer asking for technical help.",
        ),
        EmailClass(
            name="billing_question",
            queue="billing_team",
            sla_hours=12,
            keywords=["invoice", "billing", "charge", "payment",
                      "refund", "subscription", "renewal", "credit card",
                      "receipt"],
            drafts_reply=False,
            description="Billing or invoicing question. Sent to billing team; not auto-replied.",
        ),
        EmailClass(
            name="feature_request",
            queue="product_backlog",
            sla_hours=120,
            keywords=["feature request", "would like", "could you add",
                      "wishlist", "any chance", "would be great if",
                      "missing functionality"],
            drafts_reply=True,
            description="Product feedback or feature request.",
        ),
        EmailClass(
            name="newsletter_or_marketing",
            queue="archive_marketing",
            sla_hours=999999,
            keywords=["unsubscribe", "weekly digest", "newsletter",
                      "you are receiving this", "marketing preferences",
                      "limited time offer"],
            drafts_reply=False,
            description="Inbound marketing / newsletter; archived.",
        ),
        EmailClass(
            name="internal",
            queue="internal",
            sla_hours=24,
            keywords=["fyi", "team@", "all-hands", "company-wide", "internal"],
            drafts_reply=False,
            description="Internal message from teammates; sent to the internal queue.",
        ),
    ])

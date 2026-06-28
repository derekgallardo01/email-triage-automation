"""Classifier + router for emails.

Same pattern as document-classifier-kit but specialized for emails:
classify on subject + body (with subject weighted higher), confidence-
threshold drives human-review routing, internal-domain heuristic
overrides the keyword classifier when the sender matches.

The router additionally checks whether the matched class has
`drafts_reply=True`; if yes, the drafter pipeline runs after classification.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .catalog import Catalog, EmailClass, default_catalog
from .parser import Email


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    candidates: list[tuple[str, float]]
    matched_keywords: list[str]
    review_required: bool


@dataclass
class RoutingDecision:
    queue: str
    sla_hours: int
    label: str
    confidence: float
    drafts_reply: bool
    review_required: bool
    handoff_reason: str | None


class Classifier:
    """Keyword-and-weight email classifier with confidence routing."""

    def __init__(
        self,
        catalog: Catalog | None = None,
        review_threshold: float = 0.4,
        internal_domains: list[str] | None = None,
    ):
        self.catalog = catalog or default_catalog()
        self.review_threshold = review_threshold
        self.internal_domains = internal_domains or []
        problems = self.catalog.validate()
        if problems:
            raise ValueError(f"Invalid catalog: {problems}")

    def classify(self, email: Email) -> ClassificationResult:
        """Score every class against the email; route the highest scorer."""
        # Internal-domain override: if the sender is on our internal domain
        # list, route to 'internal' regardless of keyword score.
        if self.internal_domains and email.sender_domain in self.internal_domains:
            internal_class = next((c for c in self.catalog.classes if c.name == "internal"), None)
            if internal_class:
                return ClassificationResult(
                    label="internal", confidence=1.0,
                    candidates=[("internal", 1.0)],
                    matched_keywords=[f"sender_domain={email.sender_domain}"],
                    review_required=False,
                )

        # Subject signals weigh 2x body signals (subject is denser).
        subject = email.subject.lower()
        body = email.body_text.lower()

        scores: dict[str, float] = {}
        matched: dict[str, list[str]] = {c.name: [] for c in self.catalog.classes}

        for c in self.catalog.classes:
            s = 0.0
            for kw in c.keywords:
                kw_lower = kw.lower()
                subj_count = subject.count(kw_lower)
                body_count = body.count(kw_lower)
                if subj_count + body_count > 0:
                    # Length-weight + subject 2x multiplier.
                    weight = 1.0 + 0.1 * len(kw_lower)
                    s += (subj_count * 2 + body_count) * weight
                    matched[c.name].append(kw)
            scores[c.name] = s

        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        if not ranked or ranked[0][1] == 0.0:
            return ClassificationResult(
                label="unknown", confidence=0.0, candidates=ranked[:3],
                matched_keywords=[], review_required=True,
            )

        top, top_score = ranked[0]
        runner = ranked[1][1] if len(ranked) > 1 else 0.0

        margin = top_score / (top_score + runner) if (top_score + runner) > 0 else 1.0
        strength = min(1.0, top_score / 10.0)
        confidence = round(margin * strength, 3)

        return ClassificationResult(
            label=top,
            confidence=confidence,
            candidates=ranked[:3],
            matched_keywords=matched[top],
            review_required=confidence < self.review_threshold,
        )


def route(result: ClassificationResult, catalog: Catalog,
          review_queue: str = "human_review") -> RoutingDecision:
    if result.label == "unknown":
        return RoutingDecision(
            queue=review_queue, sla_hours=24, label="unknown",
            confidence=result.confidence, drafts_reply=False,
            review_required=True, handoff_reason="no matching class",
        )
    if result.review_required:
        return RoutingDecision(
            queue=review_queue, sla_hours=24, label=result.label,
            confidence=result.confidence, drafts_reply=False,
            review_required=True,
            handoff_reason=f"confidence below threshold ({result.confidence:.2f})",
        )
    cls = catalog.by_name(result.label)
    if cls is None:
        return RoutingDecision(
            queue=review_queue, sla_hours=24, label=result.label,
            confidence=result.confidence, drafts_reply=False,
            review_required=True,
            handoff_reason=f"class '{result.label}' not in catalog",
        )
    return RoutingDecision(
        queue=cls.queue, sla_hours=cls.sla_hours, label=result.label,
        confidence=result.confidence, drafts_reply=cls.drafts_reply,
        review_required=False, handoff_reason=None,
    )

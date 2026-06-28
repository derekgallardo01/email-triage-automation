"""CLI - end-to-end triage on individual EMLs or a fixtures sweep.

Usage:
    email-triage triage <path-to-eml>           # one email through full pipeline
    email-triage triage <path-to-eml> --json    # machine-readable output
    email-triage demo                           # all bundled fixtures
    email-triage list-classes                   # show the 6 classes + queues
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .catalog import default_catalog
from .classifier import Classifier, route
from .drafter import Drafter
from .parser import Email, parse_eml_file


def cmd_list_classes(_args) -> int:
    cat = default_catalog()
    print(f"Catalog has {len(cat.classes)} classes:\n")
    for c in cat.classes:
        drafts = "DRAFTS REPLY" if c.drafts_reply else ""
        print(f"  {c.name:25s} -> queue '{c.queue}' (SLA {c.sla_hours}h)  {drafts}")
        print(f"    {c.description}")
        print(f"    keywords: {c.keywords}\n")
    return 0


def _triage_one(path: Path, classifier: Classifier, drafter: Drafter) -> dict:
    email_obj = parse_eml_file(path)
    cls_result = classifier.classify(email_obj)
    decision = route(cls_result, classifier.catalog)
    draft = None
    if decision.drafts_reply:
        draft_result = drafter.draft(email_obj, decision.label)
        if draft_result and not draft_result.error:
            draft = asdict(draft_result)

    return {
        "file": path.name,
        "email": {
            "message_id": email_obj.message_id,
            "from": f"{email_obj.sender_name} <{email_obj.sender_email}>",
            "subject": email_obj.subject,
            "preview": email_obj.preview(120),
        },
        "classification": {
            "label": cls_result.label,
            "confidence": cls_result.confidence,
            "candidates": cls_result.candidates,
            "matched_keywords": cls_result.matched_keywords,
        },
        "routing": asdict(decision),
        "draft": draft,
    }


def cmd_triage(args) -> int:
    classifier = Classifier()
    drafter = Drafter()
    result = _triage_one(Path(args.path), classifier, drafter)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"\n  {result['file']}")
    print(f"    from:       {result['email']['from']}")
    print(f"    subject:    {result['email']['subject']}")
    print(f"    preview:    {result['email']['preview']}")
    c = result["classification"]
    d = result["routing"]
    print(f"    label:      {c['label']}  (conf {c['confidence']:.2f})")
    print(f"    -> queue:   {d['queue']}  (SLA {d['sla_hours']}h)")
    if d["review_required"]:
        print(f"    review:     {d['handoff_reason']}")
    if result["draft"]:
        body_lines = result["draft"]["body"].splitlines()
        preview = "\n      ".join(body_lines[:5])
        print(f"    drafted reply ({result['draft']['backend']}, conf {result['draft']['confidence']:.2f}):")
        print(f"      Subject: {result['draft']['subject']}")
        print(f"      {preview}")
        if len(body_lines) > 5:
            print(f"      ... ({len(body_lines) - 5} more lines)")
    return 0


def cmd_demo(args) -> int:
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    classifier = Classifier(internal_domains=["example.com"])
    drafter = Drafter()
    results = []
    for fixture in sorted(fixtures.glob("*.eml")):
        results.append(_triage_one(fixture, classifier, drafter))

    if args.json:
        print(json.dumps({"backend_classifier": "rules",
                          "backend_drafter": drafter.backend,
                          "runs": results}, indent=2))
        return 0

    for r in results:
        mark = "[REVIEW]" if r["routing"]["review_required"] else "[ROUTE]"
        draft_mark = "+DRAFT" if r["draft"] else ""
        print(f"  {mark} {r['file']:28s} -> {r['classification']['label']:22s} "
              f"({r['classification']['confidence']:.2f}) -> {r['routing']['queue']} {draft_mark}")

    review_count = sum(1 for r in results if r["routing"]["review_required"])
    draft_count = sum(1 for r in results if r["draft"])
    print(f"\n  Classifier backend: rules.  Drafter backend: {drafter.backend}.")
    print(f"  {len(results) - review_count}/{len(results)} routed confidently; "
          f"{review_count} sent to human_review; "
          f"{draft_count} replies drafted.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Email triage automation CLI.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-classes")

    p_tri = sub.add_parser("triage")
    p_tri.add_argument("path")
    p_tri.add_argument("--json", action="store_true")

    p_demo = sub.add_parser("demo")
    p_demo.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    handlers = {"list-classes": cmd_list_classes,
                "triage": cmd_triage, "demo": cmd_demo}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

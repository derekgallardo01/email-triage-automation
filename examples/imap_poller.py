"""Poll an IMAP mailbox; triage every unread message; save drafts.

This is the production deployment shape: cron job (or systemd timer) runs
this script every N minutes. It:

  1. Connects to IMAP (Gmail / Outlook / any IMAP server)
  2. Fetches unread messages
  3. Parses each via the kit's parser
  4. Classifies + routes via the kit's classifier
  5. For classes with drafts_reply=True, generates a draft reply
  6. Saves the draft to the IMAP server's Drafts folder
  7. Labels/flags the original message with the routing decision
  8. (Optional) Sends a Slack summary of what was processed

By default it runs in DRY-RUN mode against the BUNDLED EML fixtures
(no IMAP credentials needed). Set IMAP_HOST + IMAP_USER + IMAP_PASSWORD
to poll a real inbox.

Usage:
    python examples/imap_poller.py                                    # dry-run against fixtures
    IMAP_HOST=imap.gmail.com IMAP_USER=... IMAP_PASSWORD=... python examples/imap_poller.py
"""

from __future__ import annotations

import argparse
import imaplib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_triage.catalog import default_catalog  # noqa: E402
from email_triage.classifier import Classifier, route  # noqa: E402
from email_triage.drafter import Drafter  # noqa: E402
from email_triage.parser import Email, parse_eml_bytes, parse_eml_file  # noqa: E402


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def triage_email(email_obj: Email, classifier: Classifier, drafter: Drafter) -> dict:
    """Run one email through the full pipeline; return the decision dict."""
    cls_result = classifier.classify(email_obj)
    decision = route(cls_result, classifier.catalog)

    draft = None
    if decision.drafts_reply:
        drafted = drafter.draft(email_obj, decision.label)
        if drafted and not drafted.error:
            draft = drafted

    return {
        "message_id": email_obj.message_id,
        "from": email_obj.sender_email,
        "subject": email_obj.subject,
        "classification": cls_result,
        "decision": decision,
        "draft": draft,
    }


def poll_dry_run() -> list[dict]:
    """Run triage against the bundled .eml fixtures; no IMAP needed."""
    classifier = Classifier(internal_domains=["example.com"])
    drafter = Drafter()
    results = []
    for fixture in sorted(FIXTURES_DIR.glob("*.eml")):
        email_obj = parse_eml_file(fixture)
        results.append(triage_email(email_obj, classifier, drafter))
    return results


def poll_imap(host: str, user: str, password: str, mailbox: str = "INBOX",
              max_messages: int = 50, internal_domains: list[str] | None = None) -> list[dict]:
    """Poll a real IMAP mailbox; triage every unread message; save drafts."""
    classifier = Classifier(internal_domains=internal_domains or [])
    drafter = Drafter()
    results = []

    with imaplib.IMAP4_SSL(host) as imap:
        imap.login(user, password)
        imap.select(mailbox)

        # Fetch unread messages
        status, msg_ids = imap.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError(f"IMAP search failed: {status}")

        ids = msg_ids[0].split()[:max_messages]
        print(f"Found {len(ids)} unread message(s) in {mailbox}")

        for msg_id in ids:
            # Fetch raw MIME
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK":
                print(f"  ! Failed to fetch message {msg_id.decode()}: {status}", file=sys.stderr)
                continue
            raw_bytes = msg_data[0][1]
            email_obj = parse_eml_bytes(raw_bytes)

            result = triage_email(email_obj, classifier, drafter)

            # Save draft reply to IMAP's Drafts folder
            if result["draft"]:
                draft_mime = build_draft_mime(result["draft"], to=email_obj.sender_email)
                imap.append("Drafts", "\\Draft", None, draft_mime.encode("utf-8"))
                print(f"  + Draft saved for {email_obj.subject!r}")

            # Tag the original message with the routing decision
            decision = result["decision"]
            label = f"triage/{decision.queue}"
            # Gmail uses X-GM-LABELS; standard IMAP uses keywords
            try:
                imap.store(msg_id, "+X-GM-LABELS", label)
            except Exception:
                imap.store(msg_id, "+FLAGS", f"({label})")

            results.append(result)

        imap.logout()

    return results


def build_draft_mime(draft, to: str) -> str:
    """Construct a minimal RFC-822 MIME draft from a DraftedReply."""
    return (
        f"To: {to}\r\n"
        f"Subject: {draft.subject}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{draft.body}\r\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMAP poller -> email triage pipeline.")
    parser.add_argument("--host", default=os.environ.get("IMAP_HOST"),
                        help="IMAP host (or IMAP_HOST env). Empty = dry-run.")
    parser.add_argument("--user", default=os.environ.get("IMAP_USER"),
                        help="IMAP username (or IMAP_USER env).")
    parser.add_argument("--password", default=os.environ.get("IMAP_PASSWORD"),
                        help="IMAP password / app password (or IMAP_PASSWORD env).")
    parser.add_argument("--mailbox", default="INBOX")
    parser.add_argument("--max-messages", type=int, default=50)
    parser.add_argument("--internal-domains", default="",
                        help="Comma-separated list of domains to treat as internal.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not (args.host and args.user and args.password):
        print("Dry-run mode (no IMAP credentials set); polling bundled fixtures.\n")
        results = poll_dry_run()
    else:
        internal_domains = [d.strip() for d in args.internal_domains.split(",") if d.strip()]
        results = poll_imap(args.host, args.user, args.password, args.mailbox,
                            args.max_messages, internal_domains)

    if args.json:
        # asdict every dataclass field; the result dict has mixed shapes
        out = []
        for r in results:
            out.append({
                "message_id": r["message_id"],
                "from": r["from"],
                "subject": r["subject"],
                "label": r["classification"].label,
                "confidence": r["classification"].confidence,
                "queue": r["decision"].queue,
                "review_required": r["decision"].review_required,
                "drafted": r["draft"] is not None,
            })
        print(json.dumps(out, indent=2))
    else:
        print(f"\nTriaged {len(results)} message(s):\n")
        for r in results:
            decision = r["decision"]
            mark = "[REVIEW]" if decision.review_required else "[ROUTE] "
            draft_mark = " +DRAFT" if r["draft"] else ""
            print(f"  {mark} {r['subject'][:60]:60s} -> "
                  f"{decision.label:20s} -> {decision.queue}{draft_mark}")

        review_count = sum(1 for r in results if r["decision"].review_required)
        draft_count = sum(1 for r in results if r["draft"])
        print(f"\n  {len(results) - review_count}/{len(results)} routed confidently; "
              f"{review_count} sent to human_review; {draft_count} drafts saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

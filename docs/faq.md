# FAQ

## How is this different from Front / Help Scout / Gmail filters?

Those are **products** that handle email + collaboration end-to-end.
They give you a UI, multi-user routing, SLA tracking, and a paid
subscription.

This kit is **the logic underneath**. The part that says "this is a
sales lead, route it to the pipeline, draft this reply." You'd
typically use this kit as the brain behind a webhook or a scheduled
poller — feeding routing decisions into whatever queueing /
collaboration tool you already use (Slack, Asana, Linear, Salesforce,
HubSpot, custom Postgres + UI).

## Why not just use one big LLM prompt?

Cost, latency, and determinism. A 50k-email/month inbox is:

- ~$15-50/month at Haiku rates if every email goes through an LLM
- ~$300-1500/month at Opus rates
- 1-3s latency per email vs ~10ms for the rules backend
- Non-deterministic — you can't gate CI on exact label assertions

The hybrid pattern is what most production deployments end up running:
rules backend handles the obvious 70-80% (instant, free); LLM handles
the long tail (slower, expensive, but only for the cases that need
it). The kit defaults to the all-rules path because it's the right
starting point.

## How is this different from `document-classifier-kit`?

`document-classifier-kit` is the **classifier pattern in isolation**.
Same scoring formula, similar catalog shape.

This kit is `document-classifier-kit` + **email-specific parser** +
**reply drafter** + **two eval suites instead of one**. Pulls the
pattern into an end-to-end vertical app for the email use case.

If you're triaging non-email documents (PDFs, forms, web submissions),
use document-classifier-kit directly. If you're triaging an inbox, use
this.

## What about attachments?

Out of scope. The parser only reads text/plain bodies. For attachment
handling:

1. Extend `parser.py::_body_text` to also enumerate attachments.
2. Pipe attachment bytes to whichever parser fits (PDF →
   `pdf-extraction-kit`, image → OCR, doc → docx parser).
3. Optionally append a summary of attachments to the body before
   classification.

## Can it auto-send the drafted replies?

The kit produces the draft; you control the send. Typical pattern:

```python
if draft.confidence >= 0.85 and decision.confidence >= 0.95:
    smtp_send(...)             # high confidence both ways - auto-send
elif draft.confidence >= 0.7:
    save_as_gmail_draft(...)   # save as draft, human approves
else:
    review_queue.enqueue(...)  # full human review
```

The two confidence numbers (classification + draft) let you build a
graduated rollout. Start with everything going to review; once you
trust the classifier, auto-save drafts; once you trust both, auto-send
the highest-confidence cases.

## Does the classifier handle Reply / Re: chains?

Today it treats each message independently — `Re: ...` subjects pass
through but the kit doesn't track the conversation thread. For
thread-aware classification:

1. Fetch all prior messages on the thread.
2. Concatenate the bodies (or summarize them) before classification.
3. The classifier's keyword scoring still works — context just gets
   longer.

For real production, the thread context usually matters more than
single-message classification. Wire your thread fetcher upstream of
`parse_eml_bytes()`.

## Why is `internal` a class instead of a special case?

The internal-domain override could fire BEFORE classification (special
case in the router) or AFTER (the override is in `Classifier.classify`
returning early). The kit does the latter so:

- The catalog stays the source of truth for all routing destinations
- Tests can verify the override directly without mocking the router
- You can disable the override (`internal_domains=[]`) and the
  classifier still works on internal emails — they just get
  keyword-classified

For most engagements you want the override on. It's a one-line
constructor arg.

## How do I localize the reply templates?

Per-locale prompt directories:

```
prompts/
    en/
        sales_lead.txt
        support_request.txt
    es/
        sales_lead.txt
        support_request.txt
    de/
        ...
```

Detect locale from the inbound email (sender's domain TLD, or
`Accept-Language` if you have it from a web form). Construct the
drafter with the right prompts_dir:

```python
locale = detect_locale(email)
drafter = Drafter(prompts_dir=f"prompts/{locale}")
```

That's it. The drafter doesn't care about locales; it just reads
templates from a directory.

## Does the substitution backend handle multi-line subjects?

`{subject}` is substituted as a literal string. If the subject has
newlines (RFC 2047 folded headers usually don't, but some clients
produce them), the template `Subject: Re: {subject}` would produce a
malformed reply subject.

Two defenses:

1. The parser already normalizes via `email.policy.default` which
   handles folded headers.
2. You can sanitize in the template: `Subject: Re: {subject_clean}`
   where you pre-process to strip newlines.

For the bundled templates, multi-line subjects haven't come up.

## What's a good first class to start with?

The one with the **highest volume + clearest signal**. For most SMB
inboxes, that's either:

- **`spam_or_promo`** — high volume, obvious keywords, low cost of
  misclassification (worst case: a real email gets archived; user
  notices in their archived folder).
- **`internal`** — easy via domain check, high volume in larger orgs.

Start with one of those, get the eval gate passing, then add the
classes where misclassification is more expensive (`customer_complaint`,
`sales_lead`).

## How big does the eval suite need to be?

For "I'd trust this in production": minimum 5-10 cases per class,
ideally 20-50. The bundled 1-per-class is for **demonstration** of
the pattern, not production confidence.

The cheap way to grow it: every time the classifier misroutes in
production, drop that email into `fixtures/` and add a case to
`evals/classification.json`. After a few months you've got a
realistic, adversarial eval suite for free.

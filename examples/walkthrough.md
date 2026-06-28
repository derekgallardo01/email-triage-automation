# Walkthrough

End-to-end tour of `email-triage demo`.

## Step 1: Parse

```python
from email_triage.parser import parse_eml_file
email_obj = parse_eml_file("fixtures/01-sales-lead.eml")
```

`email_obj` is an `Email`:

```python
Email(
    message_id="CAJk_demo-001@mail.example.com",
    sender_name="Maya Chen",
    sender_email="maya.chen@acme-prospects.com",
    to=["hello@example.com"],
    subject="Pricing for 50-seat annual contract?",
    body_text="Hi team,\n\nWe're evaluating a few options...",
    received_at="2026-06-27T09:14:00-07:00",
    raw_headers={...},
)
```

## Step 2: Classify

```python
from email_triage.classifier import Classifier
clf = Classifier(internal_domains=["example.com"])
result = clf.classify(email_obj)
```

`result` is a `ClassificationResult`:

```python
ClassificationResult(
    label="sales_lead",
    confidence=1.0,
    candidates=[("sales_lead", 8.2), ("billing_question", 1.1), ...],
    matched_keywords=["pricing", "annual contract", "trial", "demo"],
    review_required=False,
)
```

The classifier:
- Scored every class by `(subject_count * 2 + body_count) * (1.0 + 0.1 * len(kw))`
- Picked the top class
- Computed confidence from margin × strength
- Recorded which keywords matched

## Step 3: Route

```python
from email_triage.classifier import route
decision = route(result, clf.catalog)
```

`decision` is a `RoutingDecision`:

```python
RoutingDecision(
    queue="sales_pipeline",
    sla_hours=4,
    label="sales_lead",
    confidence=1.0,
    drafts_reply=True,
    review_required=False,
    handoff_reason=None,
)
```

Because `drafts_reply=True`, the drafter pipeline runs next.

## Step 4: Draft (if applicable)

```python
from email_triage.drafter import Drafter
drafter = Drafter()
draft = drafter.draft(email_obj, decision.label)
```

`draft` is a `DraftedReply`:

```python
DraftedReply(
    in_reply_to_message_id="CAJk_demo-001@mail.example.com",
    subject="Re: Pricing for 50-seat annual contract?",
    body="""Hi Maya,

Thanks for reaching out about Pricing for 50-seat annual contract?.
I'd love to set up a 30-minute call to walk you through how the product
would fit your specific use case - much more efficient than a written
reply for this.

A few good slots this week: Tuesday 10am, Wednesday 2pm, or Friday 11am
(all Pacific). Reply with whichever works and I'll send a calendar
invite with a Zoom link.

If you'd rather start with self-serve, our pricing and trial are at
https://example.com/pricing.

Looking forward to it,
[Your name]""",
    backend="substitution",
    confidence=0.7,
)
```

The substitution backend literally filled in the `{sender_name}`,
`{subject}`, and `{body_excerpt}` placeholders from
`prompts/sales_lead.txt`. Deterministic + zero LLM cost.

## Step 5: Decide what to do with the draft

```python
import smtplib  # or your transport of choice

if draft.confidence >= 0.85 and decision.confidence >= 0.95:
    # Both high — auto-send
    smtplib.SMTP(...).send_message(make_msg(email_obj.sender_email,
                                            draft.subject, draft.body))
elif draft.confidence >= 0.7:
    # Save as Gmail draft for human approval
    gmail.users().drafts().create(...)
else:
    # Full human review
    review_queue.enqueue({"email": email_obj, "result": result,
                          "decision": decision, "draft": draft})
```

The kit gives you the **draft + the two confidence numbers**. Your
deployment decides the auto-send / save-as-draft / review thresholds.

## Step 6: The whole loop, every email

For an inbox of 1,000 emails:

```python
clf = Classifier(internal_domains=["yourcompany.com"])
drafter = Drafter()

for email_obj in inbox_poller():  # IMAP / Gmail / Graph
    result = clf.classify(email_obj)
    decision = route(result, clf.catalog)

    if decision.drafts_reply:
        draft = drafter.draft(email_obj, decision.label)
    else:
        draft = None

    your_dispatcher(email_obj, result, decision, draft)
```

Performance: ~10ms per email on the rules + substitution backends.
1,000 emails = 10 seconds. The slowest part is the inbox poller, not
the kit.

## When the classifier misroutes

Run the email through `email-triage triage`:

```
$ email-triage triage path/to/misrouted.eml
  from:       Some Customer <them@customer.com>
  subject:    Cancel my subscription
  preview:    Hi, I'd like to cancel my subscription...
  label:      general                              <-- wrong
  -> queue:   human_review  (SLA 24h)
```

Two fixes:

1. Add `"cancel my subscription"` to the right class's keywords
   (or create a new `cancellation` class).
2. Drop the email into `fixtures/cancellation-001.eml` and add a case
   to `evals/classification.json`. The regression now can't come back.

## When the drafter response is off

Edit `prompts/<class>.txt`. The template is just a text file with
three placeholders (`{sender_name}`, `{subject}`, `{body_excerpt}`).
Add a draft case for the change to `evals/drafts.json` to lock in the
new contract.

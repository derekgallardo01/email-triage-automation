# Architecture

Four components with explicit boundaries:

1. **Parser** — `email.parser` stdlib. Inbound MIME bytes / EML file →
   `Email` dataclass.
2. **Catalog** — declarative class definitions (label, queue, SLA,
   keywords, drafts_reply flag).
3. **Classifier + router** — keyword-weighted scoring + confidence
   gating + queue picking. Same pattern as
   [document-classifier-kit](https://github.com/derekgallardo01/document-classifier-kit),
   specialized for emails (subject weighs 2x body, internal-domain
   override).
4. **Drafter** — per-class reply templates, deterministic substitution
   by default, LLM-backed when wired.

The CLI is the glue. Each component is independently testable.

## End-to-end flow

```
Raw bytes / .eml file
    -> parser.parse_eml_bytes() or parse_eml_file() or parse_mbox()
        -> Email{message_id, sender, subject, body, headers}
        -> classifier.classify(email)
            -> ClassificationResult{label, confidence, candidates, matched_keywords, review_required}
        -> route(result, catalog)
            -> RoutingDecision{queue, sla_hours, drafts_reply, review_required, handoff_reason}
        -> if drafts_reply: drafter.draft(email, decision.label)
            -> DraftedReply{subject, body, backend, confidence}
    -> hand off to your queue / outbound layer
```

## Why subject weighs 2x body

In real inboxes, subjects are denser and more deliberate. "URGENT:
billing dispute" in the subject is a much stronger signal than the
same words buried in paragraph 4 of a customer complaint.

The weight is a multiplier in `Classifier.classify()`:

```python
weight = 1.0 + 0.1 * len(kw_lower)
s += (subj_count * 2 + body_count) * weight
```

Subject keyword "billing" in a subject "billing dispute" outweighs the
same keyword appearing once in a long body. This is the trick that
makes the rules backend competitive with a small LLM classifier on
typical inboxes.

## Internal-domain override

Emails from your own domain are almost always internal — FYIs, team
broadcasts, calendar updates. The classifier shouldn't keyword-classify
them; they should always go to the `internal` queue.

```python
if email.sender_domain in self.internal_domains:
    return ClassificationResult(label="internal", confidence=1.0, ...)
```

The override is opt-in (`Classifier(internal_domains=["yourcompany.com"])`).
Skip it if your domain has both external and internal traffic on the
same address.

## The drafter's seam

```python
def draft(self, email, class_name):
    template = self.prompts_dir / f"{class_name}.txt"
    if self.backend == "claude":
        body = self._draft_claude(email, class_name, template.read_text())
    else:
        body = self._draft_substitution(email, template.read_text())
    return DraftedReply(..., backend=..., confidence=...)
```

Both backends produce a `DraftedReply` with subject + body. Downstream
code (your outbound queue, your reviewer UI) doesn't know which path
generated the draft.

### Why substitution as the default?

- **Deterministic.** Same email + same template → same draft, always.
  Lets the eval suite assert exact phrases.
- **Zero cost.** No LLM call per email.
- **Production-realistic.** Many real teams ship with templated replies
  for the obvious cases (sales lead, support ack) and only escalate
  to LLM drafts for harder ones. The hybrid pattern is documented in
  [customization.md](customization.md).

### When the LLM drafter is worth it

- The template can't capture the right contextual response (legal
  questions, multi-thread conversations, customers with history).
- You want one universal template + LLM personalization (smaller
  prompts/templates dir to maintain).
- You're routing low-confidence drafts to human review anyway, so
  occasional LLM weirdness is caught downstream.

## The catalog as a config file

The `default_catalog()` is in Python because the kit ships with one
example. For real engagements you'd often want it as YAML or JSON so
non-engineers can edit:

```yaml
# catalog.yaml
classes:
  - name: sales_lead
    queue: sales_pipeline
    sla_hours: 4
    keywords: [pricing, quote, demo, trial, interested]
    drafts_reply: true
    description: Inbound sales enquiry
```

Loading it is ~10 lines (parse YAML, instantiate `EmailClass` per
entry, wrap in `Catalog`). Skipped in the default kit to keep the
dependency list at zero.

## Confidence scoring (carry-over from document-classifier-kit)

```
score(class) = sum over class.keywords of:
    (subject_count * 2 + body_count) * (1.0 + 0.1 * len(keyword))

margin = top_score / (top_score + runner_up_score)
strength = min(1.0, top_score / 10.0)
confidence = margin * strength
```

Same shape as document-classifier-kit. Read its
[architecture.md](https://github.com/derekgallardo01/document-classifier-kit/blob/main/docs/architecture.md)
for the longer rationale on why this formula.

## Review-routing reasons (three)

| Path | When | Reason emitted |
|---|---|---|
| no matching class | `result.label == "unknown"` | `"no matching class"` |
| below threshold | `confidence < review_threshold` | `"confidence below threshold (0.XX)"` |
| stale catalog | predicted class no longer in catalog | `"class 'X' not in catalog"` |

The `handoff_reason` is what shows up in the human reviewer's UI.
Specific reasons cut review time vs vague "low confidence" labels.

## What's deliberately NOT in the kit

- **IMAP / Microsoft Graph / Gmail polling** — that's the integration
  layer at the parser boundary. The kit assumes you've already pulled
  the MIME bytes.
- **Outbound SMTP / API send** — the kit produces a `DraftedReply`;
  your transport sends it.
- **Threading / conversation context** — `Email` carries `message_id`
  but the kit treats each message independently. For thread-aware
  responses, fetch the prior messages and prepend to the body before
  classification.
- **Attachment handling** — the parser only pulls text/plain bodies.
  Real production deployments often want to extract PDF attachments
  and run them through `pdf-extraction-kit`.

## Three-component split rationale

Why these specific component boundaries and not, say, one big
`Triage.process(email)` method?

- **Parser** stays separate because it's the integration boundary —
  every deployment swaps it for IMAP / Graph / Gmail / etc. Keeping
  it standalone means the rest doesn't change.
- **Classifier + router** stay coupled (router is just a function,
  not a class) because routing logic is small and always depends on
  the classification.
- **Drafter** stays separate because it has its own seam (LLM swap)
  and its own eval suite (draft quality). Coupling it would force
  every classifier change to re-run the draft evals.

The CLI's `_triage_one()` shows the whole flow in 15 lines — that's
the integration layer, kept thin so callers can subset (e.g., classify
without drafting, or draft without classifying given a known class).

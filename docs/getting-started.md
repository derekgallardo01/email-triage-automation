# Getting started

Five minutes to a working inbox triage pipeline on your machine.

## Install

```bash
git clone https://github.com/derekgallardo01/email-triage-automation.git
cd email-triage-automation
pip install -e .
```

Stdlib-only on the default path. `pip install -e ".[llm]"` adds the
optional `anthropic` dependency for the LLM drafter backend.

## Run the demo

```bash
email-triage demo
```

Seven bundled fixtures, classified + routed + (where appropriate)
replied to. Output shows the route + queue + SLA + a `+DRAFT` marker
if a draft reply was generated.

## Triage a single email

```bash
email-triage triage fixtures/01-sales-lead.eml
```

Full breakdown: parsed sender + subject, classified label + confidence,
top candidates, routing decision, and the drafted reply (if any).
Append `--json` for machine-readable output.

## List the catalog

```bash
email-triage list-classes
```

Shows each class, its target queue, SLA, and whether the drafter is
enabled for it.

## Run the tests

```bash
python -m pytest -q
```

33 tests across the parser, classifier, router, and drafter.

## Run the evals

```bash
python evals/run.py
```

Runs two suites:
1. **Classification eval** — 7 fixtures with gold labels, computes
   per-class precision / recall / F1.
2. **Draft eval** — 3 fixtures where the drafter should run, asserts
   required phrases (`contains_all` rubric).

CI gates on both at 100%.

## Triage your own email

Drop a `.eml` file (Gmail's "Show original" → "Download original" gives
you one):

```bash
email-triage triage path/to/your-email.eml
```

If it lands in the wrong class:

1. **Look at the matched_keywords** in the output. If the wrong
   keyword fired, remove it from the wrong class or add stronger ones
   to the right class.
2. **Lower the review_threshold** — `Classifier(review_threshold=0.6)`
   sends more borderline cases to human review instead of the wrong
   queue.

## Wire to your real inbox

Replace `parse_eml_file()` with whichever poller you have:

```python
# Microsoft Graph example
from email_triage.parser import parse_eml_bytes
from email_triage.classifier import Classifier, route
from email_triage.drafter import Drafter

clf = Classifier(internal_domains=["yourcompany.com"])
drafter = Drafter()

for msg in graph_client.me.messages.get(top=50):
    raw_mime = base64.b64decode(msg.body_preview)  # adjust per Graph API call
    email_obj = parse_eml_bytes(raw_mime)
    result = clf.classify(email_obj)
    decision = route(result, clf.catalog)
    draft = drafter.draft(email_obj, decision.label) if decision.drafts_reply else None
    # ... send to your queue / outbound
```

The parser shape is the only integration point. Everything else
(classifier, router, drafter, eval harness) works unchanged.

## Wire the Claude drafter

1. `pip install -e ".[llm]"`
2. `export ANTHROPIC_API_KEY=sk-...`
3. `export EMAIL_TRIAGE_LLM=claude`
4. Implement `_draft_claude` in
   [src/email_triage/drafter.py](../src/email_triage/drafter.py)
   per the docstring sketch (~10 lines of Anthropic SDK glue).

Tests pin the backend to `substitution` so they keep passing.

## Next steps

- [Architecture](architecture.md) — parser/classifier/drafter design
- [Customization](customization.md) — add classes, templates, backends
- [Evaluation](evaluation.md) — both eval suites + how to extend them

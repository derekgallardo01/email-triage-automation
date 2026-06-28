# Evaluation

Two eval suites gate CI:

1. **Classification eval** — per-fixture label assertions + per-class
   precision/recall/F1.
2. **Draft quality eval** — per-fixture draft assertions (contains_all
   rubric over required phrases).

The two suites move on different cadences. Tweaking the classifier
runs the classification suite; editing reply templates runs the draft
suite. Both run on every push.

## Running

```bash
python evals/run.py
```

Output:

```
=== Classification eval (7 cases, internal_domains=['example.com']) ===

  PASS  sales-lead                expected=sales_lead               actual=sales_lead               conf=1.00
  PASS  support                   expected=support_request          actual=support_request          conf=0.80
  PASS  billing                   expected=billing_question         actual=billing_question         conf=1.00
  ...

  class                         precision   recall     F1  support
  billing_question                   1.00     1.00   1.00        1
  feature_request                    1.00     1.00   1.00        1
  internal                           1.00     1.00   1.00        1
  newsletter_or_marketing            1.00     1.00   1.00        1
  sales_lead                         1.00     1.00   1.00        1
  support_request                    1.00     1.00   1.00        1
  unknown                            1.00     1.00   1.00        1

  Accuracy: 7/7 (100%)

=== Draft eval (3 cases) ===

  PASS  sales-lead-greets-and-offers-call
  PASS  support-asks-clarifying-questions
  PASS  feature-request-acknowledges-and-asks-priority

Overall: classification OK, drafts OK
```

Non-zero exit code if either suite has failures.

## Adding a classification case

Edit `evals/classification.json`:

```json
{"id": "your-new-case",
 "fixture": "your-new-fixture.eml",
 "expected": "sales_lead"}
```

Drop the EML into `fixtures/`. Re-run.

## Adding a draft case

Edit `evals/drafts.json`:

```json
{
  "id": "your-new-draft-case",
  "fixture": "your-new-fixture.eml",
  "class": "sales_lead",
  "rubric": {"contains_all": ["Maya", "30-minute call", "your specific phrase"]}
}
```

The `rubric` uses the same `contains_all` shape as `prompt-registry-kit`.
For other rubric types (`exact_match`, `matches_regex`, etc.) you'd
need to extend the eval harness — currently only `contains_all` is
wired.

## Why two separate suites?

Classification accuracy and draft quality are independent properties:

- A change to a class's keywords can break classification without
  touching any templates.
- A change to a reply template can break draft quality without
  touching the classifier.

If both lived in one suite, every change would re-run every assertion
and the failure attribution would be murky. Two suites = two clean
signals.

## Per-class metrics for classification

The classification harness reports precision / recall / F1 per class.
For different classes you care about different metrics:

- **`customer_complaint` (or sales_lead)** — recall first (missing
  one is expensive).
- **`spam_or_promo`** — precision first (false positive = real email
  in spam folder).
- **`billing_question`** — balanced (errors in either direction cost
  customer time).

For your engagement, set per-class thresholds in a config and extend
the harness to fail when any metric is below its threshold. ~20 lines
of additional code.

## Why exact-phrase asserts in the draft eval?

The bundled draft rubric asserts specific phrases like `"30-minute call"`
in the sales reply. That seems brittle, but it's deliberate: it
catches the most common regression — someone edits the template and
accidentally removes the call-to-action.

For LLM-backed drafts the rubric should be looser (the LLM may
paraphrase). Switch to `contains_any` with paraphrase alternatives,
or use embedding similarity (~50 lines to add as a custom rubric type).

## Running the suite against the LLM drafter

Once `_draft_claude` is wired:

```bash
pip install -e ".[llm]"
export ANTHROPIC_API_KEY=sk-...
EMAIL_TRIAGE_LLM=claude python evals/run.py
```

Expect a few flips on the draft suite — the LLM may phrase things
differently. Either:

- Tighten the prompt to force specific phrasing
- Loosen the rubric to accept paraphrases
- Switch the rubric to embedding similarity (semantic) rather than
  exact-phrase matching

Use the flips as the conversation with stakeholders about "what does
this template actually need to do."

## Why include an ambiguous fixture?

`07-ambiguous.eml` is in the fixtures + classification eval
deliberately. Without it, the suite could pass while the
human-review path was broken. The ambiguous case is the test that
`label == "unknown"` works end-to-end and routes correctly.

## Performance

The bundled suite runs in ~50ms on the rules + substitution backends.
Adding 200+ fixtures keeps it under a second. The LLM-backed draft
suite will be slower (~1-3s per draft case); add `pytest -k "not llm"`
markers if you want to skip them in fast iteration loops.

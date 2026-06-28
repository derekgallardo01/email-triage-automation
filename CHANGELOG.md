# Changelog

Notable changes to the email triage automation kit. Dates are when the
change landed on `main`.

## 2026-06-28 — Initial public release (v1.0.0)
- `parser.py` — stdlib-only EML/mbox parser using `email.parser`;
  returns `Email` dataclass with `sender_name`, `sender_email`,
  `subject`, `body_text`, `received_at`, `sender_domain`
- `catalog.py` — declarative `Catalog` of `EmailClass` entries; each
  declares queue + SLA + keywords + `drafts_reply` flag; validates at
  load
- `classifier.py` — keyword + length-weighted scoring with subject
  weighing 2x body; internal-domain override; three review-routing
  reasons emitted
- `drafter.py` — per-class reply templates with deterministic
  substitution backend and documented Claude swap point;
  `DraftedReply` with subject + body + confidence + backend
- `cli.py` — `email-triage triage / demo / list-classes` with `--json`
  machine-readable output
- 6-class bundled catalog (sales_lead, support_request,
  billing_question, feature_request, newsletter_or_marketing, internal)
  + `unknown` fallback
- 7 bundled EML fixtures (1 per class + 1 ambiguous) + 3 reply
  templates
- 33 pytest tests (parser + catalog + classifier + router + drafter)
- Two-suite eval harness: 7 classification cases (per-class
  precision/recall/F1) + 3 draft-quality cases (contains_all rubric)
- CI gates on 100% accuracy on classification + every draft case
  passing
- CI on Python 3.10/3.11/3.12
- `pyproject.toml` with `[llm]` optional extra for `anthropic`
- Docs trio: `getting-started`, `architecture`, `customization`,
  `evaluation`, `diagrams`, `faq`
- OSS niceties: `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`,
  `CITATION.cff`, `.editorconfig`, `.devcontainer/devcontainer.json`,
  `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/dependabot.yml`
- `Dockerfile`, `pages.yml` (live demo with per-email cards showing
  classification + routing + drafted reply), `screenshots.yml`,
  `portfolio.yml` — workflows include `git pull --rebase` before push
  to dodge the parallel-commit race
- README badges: CI + License (MIT) + Python (3.10+) + Open in
  Codespaces
- Theme: pink (inbox / communication)

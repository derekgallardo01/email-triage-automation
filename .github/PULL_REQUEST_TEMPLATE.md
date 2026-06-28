<!-- Thanks for the PR. Keep it short — most reviewers read the description more carefully than the diff. -->

## What this changes

<!-- 1-3 sentences. What does this do that wasn't being done before? -->

## Why

<!-- Why does it land in this repo? Link to the issue / real-world failure that triggered it if there is one. -->

## How to verify

```bash
python -m pytest -q
python evals/run.py         # or validate.py for the template kits
```

## Checklist

- [ ] Tests + eval/validate still pass on a fresh clone
- [ ] No new dependencies (or new dep is behind a clear seam, like the `LLM_PROVIDER` pattern)
- [ ] An eval/test case is added for the new behaviour (or for the bug that was fixed)
- [ ] `CHANGELOG.md` updated under an `## Unreleased` section
- [ ] Documentation updated where it matters (`README.md` / `docs/`)

<!-- See CONTRIBUTING.md for what tends to land and what doesn't. -->

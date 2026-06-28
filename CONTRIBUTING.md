# Contributing

Thanks for the interest in this kit. It's intentionally small — a focused
capability demo, not a full product — so contributions that fit that
shape are the easiest to land.

## Before opening an issue or PR

- **Check `CHANGELOG.md`** to see what's already been added.
- **Run the existing tests and evals** to confirm your environment works:

  ```bash
  python -m pytest -q
  python evals/run.py            # for the runnable kits — gates CI
  python validate.py             # for the template kits — checks examples
  ```

  If either reports anything other than 100% pass on a fresh clone of
  `main`, that's an issue worth raising first.

## Good first contributions

- **A new worked example** in `examples/` (templates) or a new sample
  dataset / scenario set (runnables). Threading with the existing
  fictional clients (Greenfield Logistics, Meridian Advisory,
  Whitford Legal, Acme Manufacturing, Northwind Clinical) is welcome
  but not required.
- **An eval case that caught a real-world failure** — the eval set is
  the regression net, so a case that would have prevented a past bug
  is more valuable than another happy-path case.
- **A docs improvement** that clarifies a place where the existing
  README / `docs/` was unclear when you read it.

## What lands easily

- One PR per change, with a clear title and description.
- Tests + evals stay 100% green.
- Stdlib-only where possible (these kits run without `pip install`).
- Code style matches the existing surface: minimal comments, no
  superfluous abstractions, no premature configurability.

## What probably won't land

- Renames, sweeping refactors, or stylistic changes without a tied
  bug or feature.
- New dependencies, unless they're justified (and even then, prefer
  an optional adapter behind a clear seam, like the `LLM_PROVIDER`
  pattern in the AI kits).
- Mocking-out the eval harness "to fix CI" instead of addressing the
  underlying behaviour change.

## Reporting a security issue

Please don't open a public issue for anything sensitive. Email
`derekgallardo01@gmail.com` instead. I'll respond within 48 hours.

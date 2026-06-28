"""Eval harness - runs BOTH the classification eval and the draft eval.

Classification eval:
  - For each fixture, compare classifier output vs expected label.
  - Compute per-class precision/recall/F1 + overall accuracy.

Draft eval:
  - For each (fixture, class) pair, run the drafter and assert the rubric
    (contains_all keywords).

CI gates on:
  - Classification accuracy == 100% on the bundled fixtures
  - Every draft case passes
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from email_triage.classifier import Classifier  # noqa: E402
from email_triage.drafter import Drafter  # noqa: E402
from email_triage.parser import parse_eml_file  # noqa: E402


FIXTURES = ROOT / "fixtures"


def load(name: str) -> list[dict]:
    with open(Path(__file__).parent / name) as f:
        return json.load(f)["cases"]


def run_classification() -> bool:
    """Returns True if all cases passed."""
    cases = load("classification.json")
    clf = Classifier(internal_domains=["example.com"])
    print(f"\n=== Classification eval ({len(cases)} cases, internal_domains=['example.com']) ===\n")

    results = []
    for case in cases:
        email_obj = parse_eml_file(FIXTURES / case["fixture"])
        r = clf.classify(email_obj)
        passed = r.label == case["expected"]
        results.append({"case": case, "actual": r.label,
                        "confidence": r.confidence, "passed": passed})
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {case['id']:25s}  expected={case['expected']:25s}  "
              f"actual={r.label:25s}  conf={r.confidence:.2f}")

    # Per-class metrics.
    classes = sorted({c["case"]["expected"] for c in results} | {c["actual"] for c in results})
    tp = defaultdict(int); fp = defaultdict(int); fn = defaultdict(int)
    for r in results:
        exp = r["case"]["expected"]; act = r["actual"]
        if exp == act:
            tp[exp] += 1
        else:
            fp[act] += 1
            fn[exp] += 1

    print(f"\n  {'class':28s}  {'precision':>9s}  {'recall':>7s}  {'F1':>5s}  {'support':>7s}")
    for c in classes:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        rec = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1 = 2 * p * rec / (p + rec) if (p + rec) > 0 else 0.0
        print(f"  {c:28s}  {p:>9.2f}  {rec:>7.2f}  {f1:>5.2f}  {tp[c] + fn[c]:>7d}")

    passed = sum(1 for r in results if r["passed"])
    print(f"\n  Accuracy: {passed}/{len(results)} ({passed / len(results):.0%})")
    return passed == len(results)


def run_drafts() -> bool:
    cases = load("drafts.json")
    drafter = Drafter()
    print(f"\n=== Draft eval ({len(cases)} cases) ===\n")

    all_passed = True
    for case in cases:
        email_obj = parse_eml_file(FIXTURES / case["fixture"])
        result = drafter.draft(email_obj, case["class"])
        if result is None or result.error:
            print(f"  FAIL  {case['id']:45s} (drafter returned no draft / error: {result.error if result else 'n/a'})")
            all_passed = False
            continue
        body = result.body.lower()
        required = case["rubric"].get("contains_all", [])
        missing = [r for r in required if r.lower() not in body]
        if missing:
            print(f"  FAIL  {case['id']:45s} missing: {missing}")
            all_passed = False
        else:
            print(f"  PASS  {case['id']:45s}")

    return all_passed


def main() -> int:
    classification_ok = run_classification()
    drafts_ok = run_drafts()
    print(f"\nOverall: classification {'OK' if classification_ok else 'FAIL'}, "
          f"drafts {'OK' if drafts_ok else 'FAIL'}")
    return 0 if classification_ok and drafts_ok else 1


if __name__ == "__main__":
    sys.exit(main())

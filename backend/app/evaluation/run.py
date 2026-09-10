"""Offline deterministic evaluation CLI.

    python -m app.evaluation.run [--json] [--keep] [--reingest]

Always runs with fake embeddings and rule-based agents: the evaluation is a
correctness gate for the workflow's logic, so it must produce the same numbers
on every machine and cost nothing to run in CI. Model quality is a separate
question that a paid judge would answer, and is deliberately not this gate.
"""

import argparse
import json
import logging
import os
import sys


def _enforce_offline() -> None:
    """Must run before any app.* import — Settings reads os.environ at import time,
    and langsmith caches its tracing lookup on first read.
    """
    os.environ["USE_FAKE_EMBEDDINGS"] = "true"
    os.environ["USE_FAKE_LLM"] = "true"
    # The evaluation is a correctness gate, not a traced run: keep it fully
    # offline. LangChain reads the flag from either namespace.
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


_enforce_offline()

from app.db.init_db import init_db  # noqa: E402
from app.db.models import DocumentChunk  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.evaluation.dataset import load_cases  # noqa: E402
from app.evaluation.harness import CaseResult, cleanup, evaluate_case  # noqa: E402
from app.services.ingestion import ingest_all  # noqa: E402

logger = logging.getLogger(__name__)


def _prepare(reingest: bool) -> dict:
    init_db()
    if reingest:
        # Chunks embedded by a different model live in a different vector space,
        # so re-embedding is the only way to make a local run match CI exactly.
        with SessionLocal() as db:
            db.query(DocumentChunk).delete()
            db.commit()
    return ingest_all()


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _print_report(results: list[CaseResult], ingest_summary: dict) -> None:
    print("\nOffline evaluation — fake embeddings, rule-based agents")
    embedded = ingest_summary["chunks_embedded"]
    reused = ingest_summary["chunks_reused"]
    print(
        f"corpus: {ingest_summary['files']} files, {ingest_summary['chunks_seen']} chunks "
        f"({embedded} embedded, {reused} reused)\n"
    )

    header = f"{'CASE':<32}{'RISK (exp)':<22}{'APPROVAL (exp)':<18}{'EVID':<7}{'KEYS':<7}RESULT"
    print(header)
    print("-" * len(header))
    for r in results:
        risk = f"{r.observed_risk_level or '-'} ({r.case.expected_risk_level})"
        approval = (
            f"{'yes' if r.observed_approval_required else 'no'} "
            f"({'yes' if r.case.expected_approval_required else 'no'})"
        )
        print(
            f"{r.case.case_id:<32}{risk:<22}{approval:<18}"
            f"{_fmt_pct(r.evidence_coverage):<7}{_fmt_pct(r.key_findings_matched):<7}"
            f"{'PASS' if r.passed else 'FAIL'}"
        )

    failures = [r for r in results if not r.passed]
    if failures:
        print("\nFailures")
        for r in failures:
            failed = [name for name, ok in r.checks.items() if not ok]
            print(f"  {r.case.case_id}: {', '.join(failed)}")
            for note in r.notes:
                print(f"      {note}")

    total = len(results)
    print("\nAggregate")
    print(f"  cases passed                 {sum(r.passed for r in results)}/{total}")
    print(f"  risk classification          {sum(r.checks['risk_level'] for r in results)}/{total}")
    print(
        f"  approval policy              "
        f"{sum(r.checks['approval_policy'] for r in results)}/{total}"
    )
    print(
        f"  evidence coverage            "
        f"{_fmt_pct(sum(r.evidence_coverage for r in results) / total)}"
    )
    print(
        f"  tool safety                  "
        f"{sum(r.checks['tool_safety'] for r in results)}/{total} "
        f"(no ticket without an explicit approval)"
    )
    print(
        f"  key findings (informational) "
        f"{_fmt_pct(sum(r.key_findings_matched for r in results) / total)}"
    )


def _as_json(results: list[CaseResult], ingest_summary: dict) -> dict:
    total = len(results)
    return {
        "corpus": ingest_summary,
        "cases": [
            {
                "case_id": r.case.case_id,
                "scenario_type": r.case.scenario_type,
                "sample_app_id": r.case.sample_app_id,
                "passed": r.passed,
                "checks": r.checks,
                "expected_risk_level": r.case.expected_risk_level,
                "observed_risk_level": r.observed_risk_level,
                "expected_approval_required": r.case.expected_approval_required,
                "observed_approval_required": r.observed_approval_required,
                "evidence_coverage": r.evidence_coverage,
                "key_findings_matched": r.key_findings_matched,
                "removed_claim_count": r.removed_claim_count,
                "tickets_per_decision": {
                    str(run.decision): run.ticket_count for run in r.runs
                },
                "notes": r.notes,
            }
            for r in results
        ],
        "aggregate": {
            "cases": total,
            "cases_passed": sum(r.passed for r in results),
            "risk_classification_match": sum(r.checks["risk_level"] for r in results) / total,
            "approval_policy_correct": sum(r.checks["approval_policy"] for r in results) / total,
            "evidence_coverage": sum(r.evidence_coverage for r in results) / total,
            "tool_safety": sum(r.checks["tool_safety"] for r in results) / total,
            "key_findings_matched": sum(r.key_findings_matched for r in results) / total,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline golden-dataset evaluation.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--keep", action="store_true", help="keep the assessments this run created"
    )
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="re-embed the corpus with fake embeddings first (needed after a live ingestion)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)

    ingest_summary = _prepare(args.reingest)
    results = [evaluate_case(case) for case in load_cases()]

    if args.json:
        print(json.dumps(_as_json(results, ingest_summary), indent=2))
    else:
        _print_report(results, ingest_summary)

    if not args.keep:
        removed = cleanup(results)
        if not args.json:
            print(f"\ncleaned up {removed} evaluation assessment(s)")

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

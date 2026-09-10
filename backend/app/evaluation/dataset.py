"""The golden dataset: hand-written cases with the outcome each one must produce.

Expectations here describe the *deterministic* behavior of the rule-based agents,
which is what the offline evaluation exercises. They are the contract; when the
harness disagrees with them, one of the two is wrong and the run fails loudly
rather than adjusting itself to whatever the code currently does.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import settings

DATASET_PATH = Path(settings.sample_data_dir) / "golden_dataset" / "assessment_cases.jsonl"


class EvalCase(BaseModel):
    case_id: str
    sample_app_id: str
    objective: str
    scenario_type: str
    expected_risk_level: str
    expected_key_findings: list[str] = Field(default_factory=list)
    expected_approval_required: bool
    # Risk categories that must appear in the report. This is what keeps the
    # cases distinct: overall risk collapses to "critical" for most of the legacy
    # app, so without it every legacy case would assert the same thing.
    expected_finding_categories: list[str] = Field(default_factory=list)
    # Only set on cases that exist to prove the reviewer strips unsupported
    # claims; None means "not asserted either way".
    expected_removed_claims: bool | None = None


def load_cases(path: Path | None = None) -> list[EvalCase]:
    path = path or DATASET_PATH
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found at {path}")

    cases: list[EvalCase] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            cases.append(EvalCase.model_validate(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"{path}:{line_no} is not a valid eval case: {exc}") from exc

    if not cases:
        raise ValueError(f"Golden dataset at {path} contains no cases")

    ids = [c.case_id for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"Duplicate case_id(s) in {path}: {sorted(duplicates)}")

    return cases

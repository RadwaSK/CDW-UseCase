"""The golden dataset: hand-written cases and the deterministic outcome each must
produce. Expectations are the contract — a disagreement fails the run loudly
rather than adjusting to whatever the code currently does."""

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
    # Risk categories that must appear — what keeps the legacy cases distinct,
    # since overall risk collapses to "critical" for most of them.
    expected_finding_categories: list[str] = Field(default_factory=list)
    # None = not asserted. Set only on cases that check the reviewer's stripping.
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

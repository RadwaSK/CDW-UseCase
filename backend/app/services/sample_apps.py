"""Registry of sample apps available to assess — the only apps the UI/API can select."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SampleAppInfo:
    id: str
    name: str
    description: str
    folder: str  # subfolder name under settings.sample_data_dir


SAMPLE_APPS: list[SampleAppInfo] = [
    SampleAppInfo(
        id="legacy_order_service",
        name="Legacy Order Service",
        description=(
            "Synthetic Flask-style order service with planted architecture, security, "
            "and PII-handling issues, used as read-only evidence for the assessment."
        ),
        folder="legacy_order_service",
    ),
    SampleAppInfo(
        id="modern_inventory_service",
        name="Modern Inventory Service",
        description=(
            "Synthetic service that already follows the engineering standards — "
            "vault-sourced config, parameterized queries, enforced authorization. "
            "Assessing it yields a low-risk report with no approval gate."
        ),
        folder="modern_inventory_service",
    ),
]

SAMPLE_APPS_BY_ID = {app.id: app for app in SAMPLE_APPS}

STANDARDS_FOLDER = "engineering_standards"

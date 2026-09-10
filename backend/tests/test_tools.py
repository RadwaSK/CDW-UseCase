"""The tool layer: interface conformance and read-only guarantees."""

from app.tools.asset_inventory import MockAssetInventoryTool
from app.tools.base import AssetInventoryTool, ChangeManagementTool
from app.tools.repository_evidence import RepositoryEvidenceTool
from app.tools.servicenow import MockServiceNowChangeTool


def test_mocks_satisfy_their_protocols(db_session):
    """Structural conformance, so a real integration can drop in unchanged."""
    change_tool: ChangeManagementTool = MockServiceNowChangeTool(db_session)
    inventory_tool: AssetInventoryTool = MockAssetInventoryTool()

    assert callable(change_tool.create_assessment_ticket)
    assert callable(inventory_tool.get_service_context)


def test_asset_inventory_returns_synthetic_context():
    context = MockAssetInventoryTool().get_service_context("legacy_order_service")
    assert context["business_criticality"] == "high"
    assert context["data_classification"] == "contains-pii"
    assert context["upstream_dependencies"]


def test_asset_inventory_returns_empty_for_unknown_app():
    assert MockAssetInventoryTool().get_service_context("nope") == {}


def test_asset_inventory_callers_cannot_mutate_the_source_data():
    first = MockAssetInventoryTool().get_service_context("legacy_order_service")
    first["business_criticality"] = "tampered"

    second = MockAssetInventoryTool().get_service_context("legacy_order_service")
    assert second["business_criticality"] == "high"


def test_repository_evidence_tool_exposes_no_write_path(db_session):
    tool = RepositoryEvidenceTool(db_session)
    public = {name for name in dir(tool) if not name.startswith("_")}
    assert public == {"db", "search"}


def test_repository_evidence_tool_respects_category_filter(ingested, db_session):
    results = RepositoryEvidenceTool(db_session).search(
        "secrets must use a vault", source_category="standard", top_k=4
    )
    assert results
    assert all(r.source_category == "standard" for r in results)

"""Mock asset/configuration-management tool. Static synthetic data, no external calls."""

from app.tools.base import timed_call

# Synthetic CMDB-style context, fixed so the demo is reproducible.
_SERVICE_CONTEXT: dict[str, dict] = {
    "legacy_order_service": {
        "service_name": "Legacy Order Service",
        "business_criticality": "high",
        "environment": "on-premises",
        "owner_team": "Commerce Platform (synthetic)",
        "upstream_dependencies": ["storefront-web", "partner-order-feed"],
        "downstream_dependencies": ["orders-db", "payment-gateway"],
        "data_classification": "contains-pii",
        "supported_until": "2027-01-01",
    }
}


class MockAssetInventoryTool:
    def get_service_context(self, sample_app_id: str) -> dict:
        with timed_call("MockAssetInventoryTool.get_service_context", sample_app_id):
            return dict(_SERVICE_CONTEXT.get(sample_app_id, {}))

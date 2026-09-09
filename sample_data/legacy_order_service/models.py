"""Data types for the synthetic legacy order service.

Note: Customer includes PII fields (email, address, phone). The security
agent should flag any place these are logged or persisted without
protection, per sample_data/engineering_standards/security_standard.md.
"""

from dataclasses import dataclass


@dataclass
class Customer:
    customer_id: int
    full_name: str
    email: str  # PII
    phone: str  # PII
    shipping_address: str  # PII
    loyalty_tier: str = "standard"


@dataclass
class OrderLine:
    sku: str
    quantity: int
    unit_price_cents: int


@dataclass
class Order:
    order_id: int
    customer: Customer
    lines: list[OrderLine]
    status: str = "pending"
    total_cents: int = 0

    def compute_total(self) -> int:
        self.total_cents = sum(line.quantity * line.unit_price_cents for line in self.lines)
        return self.total_cents

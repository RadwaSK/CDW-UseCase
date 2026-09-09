# Modern Inventory Service (synthetic demo fixture)

A **synthetic demo application only** — not connected to any real system and containing no real
data. It is the counterpart to `legacy_order_service`: this one deliberately follows the
engineering standards (vault-sourced configuration, parameterized queries, enforced
authorization, no PII in logs, health endpoints), so an assessment of it produces a low-risk
report with no approval gate.

It still has genuine *modernization* gaps — no managed database, no container definition — so the
architecture analyst and planner have real material to work with. The point is that none of those
gaps are policy violations.

Do not add real credentials or real customer data to this folder.

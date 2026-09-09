# Cloud Modernization Standard (sample)

A concise, synthetic standard used as retrieval evidence for the architecture analyst and
modernization planner agents.

## Containerization

- Services targeted for cloud deployment must run in a container with a minimal, pinned base
  image and no development-only tooling in the production image.

## Health checks

- Every service must expose a liveness endpoint and, where it has dependencies (database,
  downstream APIs), a readiness endpoint that reflects real dependency health.

## Structured logging

- Logs must be structured (JSON), include a correlation/trace identifier, and exclude PII and
  secrets. Unstructured `print`/ad-hoc logging is a modernization gap, not a blocker by itself.

## Managed database

- Direct, hand-rolled connection management to a self-hosted database (as opposed to a managed
  database service with pooling, backups, and failover) is a modernization gap to flag and plan
  for, proportional to the service's criticality.

## Phased migration guidance

- Prefer a phased approach: (1) stabilize and add observability without behavior change,
  (2) remediate critical/high security findings, (3) containerize and externalize configuration,
  (4) migrate data layer to a managed service, (5) decommission legacy infrastructure.
- Do not recommend a "big bang" rewrite unless the evidence shows the current architecture is
  unsalvageable; prefer incremental, verifiable steps.

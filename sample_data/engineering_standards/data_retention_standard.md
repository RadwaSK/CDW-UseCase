# Data Retention Standard (sample)

A concise, synthetic policy used as retrieval evidence for the security/governance analyst agent.

## Customer data storage

- Customer PII (name, email, phone, address) must be retained only as long as required for the
  active order lifecycle plus any applicable legal/financial retention period.
- Order records may be retained longer than the PII they reference; where feasible, PII should be
  separable from the order record so it can be purged independently.

## Deletion and access requests

- The system must support locating all records for a given customer identifier so that deletion
  or export requests can be fulfilled within a reasonable timeframe.

## Backups

- Backups containing customer PII are subject to the same retention limits as primary storage and
  must not be retained indefinitely "just in case."

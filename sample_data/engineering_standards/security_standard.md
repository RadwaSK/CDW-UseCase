# Security Standard (sample)

This is a concise, synthetic engineering standard used as retrieval evidence for the
security/governance analyst agent. It is illustrative, not a real corporate policy.

## Secrets management

- Secrets (API keys, database credentials, tokens) must never be hard-coded in source files.
- Secrets must be sourced from a managed vault (e.g. Azure Key Vault) or environment variables
  injected at deploy time, never committed to version control.
- Any string literal resembling a credential found in source code is a **critical** finding.

## PII handling

- Personally identifiable information (name, email, phone, physical address, and similar fields)
  must never be written to application logs, even at debug level.
- PII at rest must be access-controlled and, where feasible, encrypted or tokenized.
- Any log statement that includes a PII-bearing object or field is a **critical** finding.

## Authentication and authorization

- Every state-changing endpoint must enforce authentication and role-based authorization.
- Endpoints that mutate business data (orders, payments, customer records) without an
  authentication/authorization check are a **high** severity finding.

## Data access patterns

- Database queries must use parameterized statements or an ORM's parameter binding.
- String-formatted or concatenated SQL built from request input is a **high** severity finding
  (SQL-injection-shaped weak query pattern).

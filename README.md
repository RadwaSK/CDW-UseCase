# Enterprise Modernization Assessment Multi-Agent System

A stateful multi-agent workflow that assesses a legacy service against
engineering standards, cites its evidence line-by-line, and stops for a human
before it touches a change-management system.

> **Demo application.** Every sample application, finding, and change ticket here
> is synthetic. The system is read-only with respect to any code it analyzes, and
> the ServiceNow integration is mocked — nothing leaves the machine.

---

## The problem

An assessment tool that reads a codebase and recommends changes has two failure
modes that matter more than answer quality:

1. **It says things the code doesn't support.** A confident, unsourced finding is
   worse than no finding — it costs reviewer time to disprove, and it only has to
   happen once for the tool to stop being trusted.
2. **It acts on its own conclusions.** Anything that writes to a change system or
   an environment turns a wrong answer into a wrong action.

This project is built around closing those two gaps. The model is treated as a
component that can be wrong, not as the authority:

- **Every finding must cite evidence** — a schema constraint, so an uncited
  finding is a validation error rather than a silent one.
- **Every citation is verified mechanically** against the chunks actually
  retrieved. Fabricated references are removed and recorded in the report.
- **The one consequential action requires a human**, gated by a deterministic
  policy — not a model judgment.

---

## Architecture

```
                    ┌──▶ architecture ──┐
START ──▶ retrieve ─┤                   ├──▶ planner ──▶ reviewer ──┐
                    └──▶ security ──────┘        ▲                  │
                                                 │                  │
                                     revise (max 1) ─────────────────┤
                                                                    ▼
                                                            approval_gate
                                                             │         │
                                              approved ──────┤         └── not required
                                                             ▼              or denied
                                                          ticket ──▶ report ──▶ END
```

**Stack**: FastAPI · LangGraph · PostgreSQL + pgvector · React/TypeScript/Vite ·
Azure OpenAI (chat + embeddings), with deterministic offline fallbacks.

Two design choices carry most of the weight:

- **The evidence reviewer is a pure function, not a model call.** Asking an LLM
  whether its own output was grounded is the weakest available check. Instead,
  every citation's chunk id is compared against the retrieved set; anything
  dangling is stripped and reported under "removed claims".
- **The approval policy is a pure function too.** Four explicit triggers over the
  structured findings. Governance rules shouldn't be probabilistic.

Full detail — retrieval strategy, chunking, checkpointing, the tool layer — is in
**[docs/architecture.md](docs/architecture.md)**.

---

## Setup

```bash
cp .env.example .env
docker compose up --build
docker compose exec api python -m app.services.ingestion
```

- Web: http://localhost:5173
- API: http://localhost:8000 (OpenAPI docs at `/api/v1/docs`)
- PostgreSQL: localhost:5432 (`app` / `app`)

The defaults in `.env.example` are fully offline (`USE_FAKE_EMBEDDINGS=true`,
`USE_FAKE_LLM=true`), so a fresh clone runs end to end with no credentials and no
spend. Set both to `false` and fill in the Azure values to use live models.

```bash
docker compose exec api pytest -q                 # backend tests
docker compose exec api python -m app.evaluation.run   # offline evaluation
docker compose exec web npm test                  # frontend tests
```

If the API ever hangs on the first assessment against a **brand-new** database,
see the checkpointer note in [docs/architecture.md](docs/architecture.md) — that
deadlock is fixed, and the fix is why `setup()` now runs at startup.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Must contain `test` (or set `TEST_DB=true`) or the test suite refuses to run, so a production URL can't be wiped by a stray `pytest` |
| `LLM_PROVIDER` | `azure_openai` | `azure_openai` or `openai` |
| `AZURE_OPENAI_ENDPOINT` | — | Resource URL |
| `AZURE_OPENAI_API_KEY` | — | Credential |
| `AZURE_OPENAI_API_VERSION` | — | API version |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | — | Chat deployment name |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | — | Embedding deployment name |
| `OPENAI_API_KEY` / `OPENAI_CHAT_MODEL` / `OPENAI_EMBEDDING_MODEL` | — | Fallback provider |
| `USE_FAKE_EMBEDDINGS` | `true` | Deterministic SHA-256 pseudo-embeddings. Forced on in tests and evaluation |
| `USE_FAKE_LLM` | `true` | Rule-based agents instead of live chat calls. Forced on in tests and evaluation |
| `EMBEDDING_DIMENSION` | `1536` | Must match the deployed model |
| `RETRIEVAL_TOP_K` | `6` | Chunks per query |
| `MAX_REVISIONS` | `1` | Revision-loop budget |
| `SAMPLE_DATA_DIR` | `sample_data` | Corpus root |
| `LANGSMITH_TRACING` | `false` | Optional; local tracing works without it |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173` | Dev frontend origin |

Tests and the evaluation set the two fake flags **before** any application import
and cannot be configured otherwise — `Settings` reads the environment at import
time, so this is enforced in `conftest.py` and `app/evaluation/run.py` rather
than left to the caller.

---

## Demo scenarios

Full walkthrough with talking points: **[docs/demo-script.md](docs/demo-script.md)**.

| # | Sample app | Shows |
|---|---|---|
| 1 | Modern Inventory Service | Clean service → low risk, **no approval, no ticket**. The gate is policy-driven, so it doesn't fire on a service that follows the standards |
| 2 | Legacy Order Service | Hard-coded secret + PII in logs → **pauses for approval** with stated reasons → approve → `CHG-DEMO-0001`. Reject gives the same report with no ticket |
| 3 | Legacy Order Service, "should it be rewritten?" | The planner overreaches with a fabricated citation; the reviewer **removes it** and the report says so |

The two sample apps are deliberately different: one plants real defects, the
other follows the standards. Without the clean one there is no way to show the
gate *not* firing.

---

## Safety design

| Property | How it is enforced |
|---|---|
| No unapproved side effects | The routing edge sends only approved runs to the ticket node, **and** the node independently re-checks the decision and raises otherwise |
| No fabricated citations | Every `chunk_id` is validated against the retrieved set; failures are removed and recorded |
| No uncited findings | Pydantic `min_length=1` on every finding's evidence list |
| No prompt or PII leakage into traces | Trace payloads pass an allow-list of 19 keys — counts, names, durations. Anything else is dropped, not stored |
| No arbitrary file access | The client selects from a fixed registry of sample apps; no path is accepted from the UI |
| No code execution | There is no shell or exec tool |
| Bounded work | One revision, capped retrieval, capped chunk size |
| Scoped approval | Approval authorizes a **simulated ticket only** — never code changes or deployment. Stated in the API, the UI banner, and the ticket payload |

The doubled ticket guard is intentional. "No ticket without approval" is a safety
property; it shouldn't depend on a single graph edge staying correct through
future edits.

---

## Evaluation results

```
$ docker compose exec api python -m app.evaluation.run

CASE                            RISK (exp)            APPROVAL (exp)    EVID   KEYS   RESULT
case-001-clean-readiness        low (low)             no (no)           100%   100%   PASS
case-002-pii-logging            critical (critical)   yes (yes)         100%   100%   PASS
case-003-hardcoded-secret       critical (critical)   yes (yes)         100%   100%   PASS
case-004-weak-evidence          critical (critical)   yes (yes)         100%   100%   PASS
case-005-high-risk-auth-gap     critical (critical)   yes (yes)         100%   100%   PASS
case-006-sql-injection-pattern  critical (critical)   yes (yes)         100%   100%   PASS

cases passed                 6/6
risk classification          6/6
approval policy              6/6
evidence coverage            100%
tool safety                  6/6  (no ticket without an explicit approval)
```

Runs fully offline in a few seconds, against the real graph, retrieval, reviewer,
policy, and tool code — only the model boundary is replaced.

Two properties worth calling out:

- **Tool safety is checked in three arms per case** — approval missing, approval
  denied, approval granted. "No ticket without approval" has to hold when the
  decision never arrives, not only when it's a "no".
- **The gate can actually fail.** Disabling the hard-coded-secret detector makes
  `case-003` fail on `finding_categories` and exits non-zero. Notably the overall
  risk level stays `critical` in that scenario, so a coarser assertion would have
  missed the regression — which is why the dataset asserts *which* detectors
  fired, not just the severity.

CI (`.github/workflows/ci.yml`) runs lint, the backend suite, the evaluation, and
the frontend build. No model credentials are configured in CI and none are needed.

---

## Limitations

- **The rule-based agents are pattern detectors, not analysts.** They exist to
  make the workflow testable and the evaluation free. The live-model path is
  wired but is not what the numbers above measure.
- **`POST /assessments` is synchronous** and holds a database connection for the
  duration of the run. A real deployment would return `202` and use a worker.
- **No authentication or authorization anywhere.** Deliberately not faked. In a
  real deployment the approval endpoint would sit behind Entra ID and a
  change-approver role, and the approver's identity would be recorded on the
  ticket — the approval record currently has no user identity at all.
- **`init_db()` uses `create_all`**, not versioned migrations. Correct for a demo
  with disposable data; wrong for anything that must preserve it.
- **Retrieval quality is untested against a large corpus.** The sample apps are
  ~45 chunks; ranking behavior at repository scale is unknown.
- **The `key findings` evaluation metric is informational only** — it is keyword
  overlap against prose, so gating on it would measure wording, not behavior.

---

## Why this is relevant to enterprise AI delivery

The hard part of shipping an agent into an enterprise is rarely the agent. It's
answering three questions to someone who will be accountable for the output:

**"Where did this come from?"** Every finding carries a file path, a line range,
and the snippet that produced it. The report also lists what was *removed* and
why, so the audit trail includes the system's own rejected claims.

**"What can it do without me?"** Exactly one action has a side effect, it is
gated by a deterministic policy, the gate is a real suspension point in a
checkpointed state machine, and the action is guarded twice. The scope of
approval is stated at the point of decision.

**"How do you know it still works?"** A golden dataset with per-case behavioral
assertions, run offline in CI on every push, that has been demonstrated to fail
when the behavior regresses. Not a benchmark score — a gate.

The same shape transfers directly to the integrations this pattern usually meets
next: the tool layer is already behind Protocols, so a real ServiceNow, CMDB, or
repository client drops in without touching the workflow.

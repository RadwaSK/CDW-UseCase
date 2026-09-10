# Architecture

## The problem this shapes around

An assessment tool that reads a codebase and recommends changes has two failure
modes that matter more than answer quality:

1. **It says things the code doesn't support.** A confident, unsourced finding is
   worse than no finding, because it costs reviewer time to disprove.
2. **It acts on its own conclusions.** Anything that writes to a change system,
   a repository, or an environment turns a wrong answer into a wrong action.

Almost every structural decision below exists to close one of those two gaps.
The model is treated as a component that can be wrong, not as the authority.

## System shape

```
┌──────────┐      ┌─────────────────┐      ┌──────────────┐
│ React UI │─────▶│ FastAPI          │─────▶│ LangGraph     │
└──────────┘      │ /api/v1/...      │      │ StateGraph    │
                  └─────────────────┘      └───────┬──────┘
                          │                        │
                  ┌───────▼────────┐      ┌────────▼─────────┐
                  │ PostgreSQL      │      │ Tool layer       │
                  │ + pgvector      │      │ (Protocols)      │
                  │ + checkpoints   │      │ ServiceNow(mock) │
                  └─────────────────┘      │ Asset inventory  │
                                           │ Repo evidence    │
                                           └──────────────────┘
```

Three containers: `postgres` (pgvector), `api` (FastAPI + LangGraph), `web`
(Vite dev server). One database holds both the application tables and LangGraph's
checkpoint tables.

## The workflow graph

```
                    ┌──▶ architecture ──┐
START ──▶ retrieve ─┤                   ├──▶ planner ──▶ reviewer ──┐
                    └──▶ security ──────┘        ▲                  │
                                                 │                  │
                                     revise (max 1) ─────────────────┤
                                                                    ▼
                                                            approval_gate
                                                             │         │
                                              approved ──────┤         └────── not required
                                                             ▼                 or denied
                                                          ticket ──▶ report ──▶ END
```

**retrieve** — Issues three separate queries (application architecture,
application security, engineering standards) rather than one, because a single
embedding of a long objective retrieves blandly. Results are deduplicated into
one evidence set. Also pulls synthetic CMDB context from the asset-inventory tool.

**architecture** / **security** — Run in parallel off the same evidence and write
to different state keys, so no reducer is needed. Each finding must cite at least
one chunk (`min_length=1` on the Pydantic model), which makes an uncited finding
a validation error rather than a silent one.

**planner** — Produces modernization options, a recommendation, and a phased
roadmap.

**reviewer** — Not a model call. See "Evidence discipline" below.

**approval_gate** — Evaluates a deterministic policy and, if sign-off is needed,
calls `interrupt()`. The graph suspends; Postgres holds the full state.

**ticket** — Reached only via the approved branch, and *also* re-checks the
decision itself before acting.

**report** — Assembles the auditable report from validated state.

## Evidence discipline

The reviewer is a pure function (`app/graph/reviewer.py`), deliberately not an
LLM call. Asking a model whether its own output was grounded is the weakest
available check — it has every incentive to agree with itself.

Instead, every citation's `chunk_id` is compared against the set of chunk ids
actually retrieved this run:

- A finding citing a chunk that isn't in the set is **removed**, and recorded in
  `removed_claims` with the reason.
- A plan option with a dangling citation is **dropped whole**, not silently
  stripped of its citation — otherwise the reader still sees a claim with nothing
  behind it.
- If the recommendation pointed at a dropped option, it falls back to one that
  survived, and that fallback is itself recorded as a removed claim.

The final report therefore carries its own audit trail of what was discarded.
`fake_plan()` deliberately fabricates a citation when the objective asks about a
rewrite, so this path is exercised on every run of `case-004`.

**One bounded revision.** The reviewer sets an explicit `will_revise` flag once,
based on the decision *and* the remaining budget; the conditional edge only reads
the flag. An earlier version re-derived the decision inside the edge, which meant
a second pass still reported unsupported claims after the budget was spent — an
infinite loop.

## Retrieval

- **Chunking is language-aware** (`app/services/chunking.py`): Markdown splits on
  headers, Python on top-level `def`/`class` via AST, everything else on 40-line
  windows. Any span over `MAX_CHUNK_LINES = 60` is subdivided. Line numbers are
  preserved so citations can point at `file.py:10-24`.
- **Ranking is hybrid**: pgvector cosine distance fetches `top_k × 3` candidates,
  then reranks as `0.6 × vector_similarity + 0.4 × token-set Jaccard`. Pure vector
  search misses exact identifiers; pure lexical misses paraphrase.
- **Ingestion is idempotent**: each chunk stores a SHA-256 `content_hash`, and
  unchanged chunks reuse their stored embedding instead of paying for a new call.
  Chunks left over from a file that shrank are deleted.

## State and resumability

LangGraph's `PostgresSaver` checkpoints after every node, keyed by `thread_id`,
which is the assessment id. A run paused at the approval gate survives an API
restart: `GET /assessments/{id}/state` reads the checkpoint back.

This is also why there is no `assessment_artifacts` table. Intermediate outputs
(architecture findings, risk findings, the plan) live in the checkpointed state;
the final report is written once to `assessments.state` as JSONB. A dedicated
per-artifact table was scaffolded in Phase 1 and removed once the checkpointer
covered the same ground.

Two details that were not obvious:

- **Serialization allow-list.** The state carries Pydantic models. Without an
  explicit `allowed_msgpack_modules` list on `JsonPlusSerializer`, LangGraph warns
  now and refuses to deserialize them in a later version.
- **`setup()` must run at startup, not on first use.** Its migrations include
  `CREATE INDEX CONCURRENTLY`, which blocks until every open transaction finishes.
  Called lazily inside a request that already holds a transaction, it waits on
  that request — a self-deadlock with no error and no timeout. It now runs in the
  FastAPI lifespan, before any request exists.

## Tool layer

Tools sit behind `Protocol` interfaces (`app/tools/base.py`) so a real ServiceNow
client can replace the mock without touching graph code.

- **`MockServiceNowChangeTool`** — Idempotent by construction: a unique constraint
  on `change_tickets.assessment_id` means a resumed or retried run cannot produce
  a second ticket.
- **`MockAssetInventoryTool`** — Static synthetic CMDB context.
- **`RepositoryEvidenceTool`** — Read-only by construction: `search()` is its only
  public method. There is no write path to expose.

## Safety design

| Property | How it is enforced |
|---|---|
| No unapproved side effects | Routing edge sends only approved runs to `ticket`, **and** `ticket_node` independently re-checks the decision and raises otherwise |
| No fabricated citations | Reviewer validates every `chunk_id` against the retrieved set |
| No uncited findings | Pydantic `min_length=1` on every finding's `evidence` |
| No prompt/PII leakage into traces | Every node emits a sanitized `node_completed` or `node_failed` event; payloads pass through an allow-list of 19 keys (counts, names, durations), and a failure records only the exception's type, never its message |
| No arbitrary file access | The UI selects from a fixed registry of sample apps; no path is accepted from the client |
| No code execution | There is no shell or exec tool |
| Approval means one thing | Approval authorizes a *simulated ticket only* — never code changes or deployment. Stated in the API docstring, the UI banner, and the ticket payload |

The doubled ticket guard is deliberate. "No ticket without approval" is a safety
property, and it should not depend on one graph edge staying correct through
future edits.

## Determinism and cost

`USE_FAKE_LLM` swaps the analyst/planner agents for rule-based detectors over the
same retrieved evidence; `USE_FAKE_EMBEDDINGS` swaps in a deterministic embedder
that SHA-256-hashes each whitespace token into a normalized bag-of-tokens vector
— not semantically meaningful, but stable, so near-identical text still scores
high and retrieval logic can be tested offline. Tests and the evaluation force
both on and cannot be configured otherwise — `conftest.py` and
`app/evaluation/run.py` set them before any `app.*` import, because `Settings`
reads the environment at import time.

This is what makes the offline evaluation a real gate: it exercises the actual
graph, retrieval, reviewer, policy, and tool code, with only the model boundary
replaced.

## Where a real deployment would differ

- **AuthN/AuthZ**: Entra ID on the API, with the approval endpoint restricted to a
  change-approver role and the approver's identity recorded on the ticket. Not
  faked here — there is no login, and the approval record has no user identity.
- **Real ServiceNow**: swap the tool implementation behind the existing Protocol.
- **Async execution**: `POST /assessments` currently runs the graph synchronously
  and holds a DB connection for the duration. A real deployment would return
  `202` immediately and run the graph on a worker.
- **Schema migrations**: `init_db()` uses `create_all`, which is right for a demo
  with disposable data and wrong for anything that must preserve it.

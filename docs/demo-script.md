# Demo script

Three scenarios, ~10 minutes. Each one demonstrates a different property, so
running only one undersells the system.

**Before you start**

```bash
docker compose up --build          # wait for "Application startup complete"
docker compose exec api python -m app.services.ingestion
```

Open http://localhost:5173. Ingestion is idempotent — re-running it is free and
only re-embeds chunks whose content actually changed.

> Say once, up front: every sample application, finding, and ticket in this demo
> is synthetic. Nothing describes a real system, and no ticket leaves the machine.

---

## Scenario 1 — Clean service: a report, and no ticket

**App:** Modern Inventory Service
**Objective:** `Assess overall cloud readiness, focusing on containerization and health checks.`

Runs to completion without stopping.

**What to point at**

- **No approval banner.** The gate is policy-driven, not decorative — a service
  that follows the standards doesn't trigger it, so approval fatigue never starts.
- **Overall risk: low**, zero risk findings.
- **The trace panel**: `retrieve → security → architecture → planner → reviewer →
  approval_gate`, with durations. `architecture` and `security` ran in parallel.
- Everything in the trace is a count, a node name, or a duration. No prompts, no
  model output, nothing that could carry PII into a log aggregator.

**The point:** the system can say "this is fine". A tool that always finds
something is a tool nobody believes twice.

---

## Scenario 2 — Real risk: the approval gate and the ticket

**App:** Legacy Order Service
**Objective:** `Prepare the order service for cloud deployment while protecting customer PII.`

Pauses partway through.

**What to point at**

- **The approval banner**, and specifically its *reasons* — the policy states why
  it stopped: critical findings, sensitive exposure (pii, secret), and that the
  recommended work touches authentication. It is a deterministic function of the
  findings, not a model judgment.
- **The banner text**: approval creates a *simulated change ticket*. No code is
  modified. The one irreversible-looking action in the product is scoped and
  labelled at the point of decision.
- **Expand an evidence block** on a finding — it shows `file.py:10-24` and the
  actual snippet. Every finding is traceable to a line of source.

Now click **Approve**.

- A ticket appears: `CHG-DEMO-0001`.
- Worth stating: the ticket tool is idempotent by database constraint, so a
  resumed or retried run cannot create a second one.

**If you have time, show the other branch.** Run the same objective again and
click **Reject**: you still get the full report, but no ticket. The gate controls
the side effect, not the analysis.

**The point:** the human decision is a real gate in the state machine, not a
confirmation dialog after the fact. The run is checkpointed while it waits — you
could restart the API here and resume.

---

## Scenario 3 — Weak evidence: the system disagreeing with itself

**App:** Legacy Order Service
**Objective:** `Evaluate whether the order service should be fully rewritten in a new language.`

**What to point at**

- Scroll to **Removed claims**. A "Full rewrite in a new language" option was
  generated and then **removed**, because its citation pointed at a chunk that
  wasn't in the retrieved evidence.
- The reviewer that caught it is a **pure function**, not a second model call. It
  compares every citation's chunk id against the ids actually retrieved. A model
  asked to grade its own grounding will usually agree with itself.
- **Limitations** at the bottom of the report states what the assessment could
  not support.

**The point:** this is the failure mode that matters in enterprise AI — a
confident, plausible, unsupported recommendation. Catching it mechanically is
worth more than a better prompt.

---

## Optional: the evaluation

```bash
docker compose exec api python -m app.evaluation.run
```

Six golden cases, fully offline, in a few seconds:

```
cases passed                 6/6
risk classification          6/6
approval policy              6/6
evidence coverage            100%
tool safety                  6/6  (no ticket without an explicit approval)
```

Two things worth saying about it:

- **Tool safety is tested in three arms per case** — approval missing, approval
  denied, approval granted — because "no ticket without approval" has to hold when
  the decision never arrives, not just when it's a "no".
- **The gate can fail.** Disabling the hard-coded-secret detector makes
  `case-003` fail on `finding_categories` and the command exit non-zero. Note that
  the overall risk level stays `critical` in that scenario, so a coarser
  assertion would have missed the regression entirely.

---

## Questions you should expect

**"Is the approval decision made by the model?"**
No. `evaluate_approval_policy()` is a pure function over the structured findings,
with four explicit triggers. Governance rules shouldn't be probabilistic.

**"What stops it hallucinating a finding?"**
Two things. Every finding must cite evidence — that's a schema constraint, so an
uncited finding fails validation. And every citation is checked against the
retrieved chunk ids, so a fabricated one is removed and recorded.

**"What would it take to point this at a real repository?"**
Ingestion already walks a directory tree, so the corpus is the easy part. The real
work is authentication, per-repo authorization, and swapping the ServiceNow mock
for a client behind the Protocol that already exists.

**"Why rule-based agents instead of the LLM?"**
Both paths exist — `USE_FAKE_LLM` selects. The deterministic path is what tests
and the evaluation run against, so the gate measures workflow correctness rather
than model variance, and costs nothing in CI.

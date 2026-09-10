import { useState } from "react";
import type { SampleApp } from "../types/api";

const EXAMPLE_OBJECTIVES: Record<string, string> = {
  legacy_order_service:
    "Prepare the order service for cloud deployment while protecting customer PII.",
  modern_inventory_service:
    "Assess overall cloud readiness, focusing on containerization and health checks.",
};

interface Props {
  sampleApps: SampleApp[];
  disabled: boolean;
  onSubmit: (sampleAppId: string, objective: string) => void;
}

export function AssessmentForm({ sampleApps, disabled, onSubmit }: Props) {
  const [sampleAppId, setSampleAppId] = useState("");
  const [objective, setObjective] = useState("");

  const selected = sampleApps.find((a) => a.id === sampleAppId);
  const canSubmit = Boolean(sampleAppId) && objective.trim().length > 0 && !disabled;

  function handleAppChange(id: string) {
    setSampleAppId(id);
    // Prefill a matching objective so the demo is runnable without inventing one.
    if (!objective.trim() || Object.values(EXAMPLE_OBJECTIVES).includes(objective)) {
      setObjective(EXAMPLE_OBJECTIVES[id] ?? "");
    }
  }

  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit(sampleAppId, objective.trim());
      }}
    >
      <h2>1. Start an assessment</h2>

      <label htmlFor="sample-app">Sample application</label>
      <select
        id="sample-app"
        value={sampleAppId}
        disabled={disabled}
        onChange={(e) => handleAppChange(e.target.value)}
      >
        <option value="">Select an application…</option>
        {sampleApps.map((app) => (
          <option key={app.id} value={app.id}>
            {app.name}
          </option>
        ))}
      </select>
      {selected && <p className="hint">{selected.description}</p>}

      <label htmlFor="objective">Assessment objective</label>
      <textarea
        id="objective"
        rows={3}
        value={objective}
        disabled={disabled}
        placeholder="e.g. Prepare the order service for cloud deployment while protecting customer PII."
        onChange={(e) => setObjective(e.target.value)}
      />

      <button type="submit" disabled={!canSubmit}>
        {disabled ? "Running assessment…" : "Run assessment"}
      </button>
      {disabled && (
        <p className="hint">
          The workflow runs synchronously: retrieval, two analysts, planning, and review.
        </p>
      )}
    </form>
  );
}

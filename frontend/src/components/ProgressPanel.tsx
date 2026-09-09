import type { Assessment } from "../types/api";

const NODES = [
  { key: "retrieve", label: "Retrieve evidence" },
  { key: "analyze", label: "Architecture + security analysis" },
  { key: "plan", label: "Modernization planning" },
  { key: "review", label: "Evidence review" },
  { key: "approval", label: "Approval gate" },
  { key: "report", label: "Final report" },
];

/** How far the run has progressed, derived from the status the API reports. */
function reachedIndex(status: string): number {
  switch (status) {
    case "pending":
      return 0;
    case "retrieving":
      return 1;
    case "analyzing":
      return 2;
    case "reviewing":
      return 4;
    case "awaiting_approval":
      return 4;
    case "completed":
    case "approved":
    case "rejected":
      return NODES.length;
    default:
      return 0;
  }
}

export function ProgressPanel({ assessment }: { assessment: Assessment }) {
  const reached = reachedIndex(assessment.status);
  const paused = assessment.status === "awaiting_approval";

  return (
    <div className="card">
      <h2>2. Workflow progress</h2>
      <p>
        Status: <strong className={`status status-${assessment.status}`}>{assessment.status}</strong>
      </p>
      <ol className="progress">
        {NODES.map((node, i) => {
          const done = i < reached;
          const current = paused && node.key === "approval";
          return (
            <li key={node.key} className={current ? "current" : done ? "done" : "todo"}>
              {current ? "⏸" : done ? "✓" : "○"} {node.label}
            </li>
          );
        })}
      </ol>
      <p className="hint">Assessment ID: <code>{assessment.id}</code></p>
    </div>
  );
}

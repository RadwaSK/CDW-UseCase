import type { TraceEvent } from "../types/api";

/** Sanitized execution timeline. The API never returns prompts or model reasoning. */
export function TracePanel({ events }: { events: TraceEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="card">
        <h2>4. Execution trace</h2>
        <p className="hint">No trace events recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>4. Execution trace</h2>
      <p className="hint">
        Node timings and counts only — prompts and model reasoning are never stored or shown.
      </p>
      <table className="trace">
        <thead>
          <tr>
            <th>Node</th>
            <th>Event</th>
            <th>Duration</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e, i) => (
            <tr key={`${e.node}-${e.created_at}-${i}`} className={e.error_class ? "failed" : ""}>
              <td>
                <code>{e.node}</code>
              </td>
              <td>{e.event_type}</td>
              <td>{e.duration_ms == null ? "—" : `${e.duration_ms} ms`}</td>
              <td>
                {e.error_class && <span className="error-tag">{e.error_class}</span>}
                <span className="payload">
                  {Object.entries(e.payload)
                    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.length : String(v)}`)
                    .join("  ") || "—"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import type { EvidenceReference } from "../types/api";

/** Expandable citations. Every finding must show what actually backs it. */
export function EvidenceList({ evidence }: { evidence: EvidenceReference[] }) {
  if (evidence.length === 0) {
    return <p className="hint">No evidence attached.</p>;
  }

  return (
    <div className="evidence">
      {evidence.map((ref) => (
        <details key={ref.chunk_id + ref.start_line}>
          <summary>
            <code>
              {ref.file_path}:{ref.start_line}-{ref.end_line}
            </code>
          </summary>
          <pre>{ref.snippet}</pre>
        </details>
      ))}
    </div>
  );
}

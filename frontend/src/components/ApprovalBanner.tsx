import { useState } from "react";
import type { PendingApproval } from "../types/api";

interface Props {
  request: PendingApproval;
  submitting: boolean;
  onDecide: (approved: boolean, comment: string) => void;
}

export function ApprovalBanner({ request, submitting, onDecide }: Props) {
  const [comment, setComment] = useState("");

  return (
    <div className="card approval">
      <h2>⏸ Human approval required</h2>
      <p>
        The workflow paused. It resumes with the same state once you decide —
        nothing was lost while it waited.
      </p>

      <h3>Why approval is required</h3>
      <ul>
        {request.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>

      <dl className="kv">
        <dt>Highest severity</dt>
        <dd>
          <span className={`sev sev-${request.highest_severity}`}>
            {request.highest_severity}
          </span>
        </dd>
        {request.recommended_option && (
          <>
            <dt>Recommended option</dt>
            <dd>{request.recommended_option}</dd>
          </>
        )}
        {request.estimated_effort && (
          <>
            <dt>Estimated effort</dt>
            <dd>{request.estimated_effort}</dd>
          </>
        )}
      </dl>

      <h3>What you are approving</h3>
      <p className="proposed-action">{request.proposed_action}</p>

      <label htmlFor="approval-comment">Comment (recorded in the report)</label>
      <input
        id="approval-comment"
        type="text"
        value={comment}
        disabled={submitting}
        placeholder="Optional note explaining your decision"
        onChange={(e) => setComment(e.target.value)}
      />

      <div className="actions">
        <button
          type="button"
          className="approve"
          disabled={submitting}
          onClick={() => onDecide(true, comment)}
        >
          {submitting ? "Submitting…" : "Approve — create simulated ticket"}
        </button>
        <button
          type="button"
          className="reject"
          disabled={submitting}
          onClick={() => onDecide(false, comment)}
        >
          Reject — no ticket
        </button>
      </div>
    </div>
  );
}

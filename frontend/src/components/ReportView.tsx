import type { AssessmentReport } from "../types/api";
import { EvidenceList } from "./EvidenceList";

export function ReportView({ report }: { report: AssessmentReport }) {
  const { approval, plan } = report;

  return (
    <div className="card">
      <h2>3. Assessment report</h2>

      <section>
        <h3>Executive summary</h3>
        <p>{report.executive_summary}</p>
        <p>
          Overall risk:{" "}
          <span className={`sev sev-${report.overall_risk_level}`}>
            {report.overall_risk_level}
          </span>
        </p>
      </section>

      <section>
        <h3>Scope and evidence reviewed</h3>
        <p>
          Objective: <em>{report.scope.objective}</em>
        </p>
        <p>
          {report.scope.evidence_count} evidence chunk(s) across{" "}
          {report.scope.files_reviewed.length} file(s):
        </p>
        <ul className="files">
          {report.scope.files_reviewed.map((f) => (
            <li key={f}>
              <code>{f}</code>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Current-state architecture</h3>
        <p>{report.architecture_summary}</p>
        {report.architecture_findings.map((f) => (
          <div key={f.title} className="finding">
            <h4>
              {f.title} <span className="tag">{f.category}</span>
            </h4>
            <p>{f.description}</p>
            <EvidenceList evidence={f.evidence} />
          </div>
        ))}
      </section>

      <section>
        <h3>Risk register</h3>
        {report.risk_findings.length === 0 ? (
          <p>No policy violations were identified in the retrieved evidence.</p>
        ) : (
          report.risk_findings.map((f) => (
            <div key={f.title} className="finding">
              <h4>
                <span className={`sev sev-${f.severity}`}>{f.severity}</span> {f.title}
              </h4>
              <p>{f.description}</p>
              <p>
                <strong>Recommended action:</strong> {f.recommended_action}
              </p>
              <p className="hint">
                Policy: <code>{f.policy_reference}</code>
              </p>
              <EvidenceList evidence={f.evidence} />
            </div>
          ))
        )}
      </section>

      {plan && (
        <>
          <section>
            <h3>Modernization options</h3>
            <p>{plan.summary}</p>
            {plan.options.map((option) => (
              <div
                key={option.name}
                className={
                  option.name === plan.recommended_option ? "option recommended" : "option"
                }
              >
                <h4>
                  {option.name}
                  {option.name === plan.recommended_option && (
                    <span className="tag recommended-tag">recommended</span>
                  )}
                </h4>
                <p>{option.description}</p>
                <p>
                  <strong>Trade-offs:</strong> {option.trade_offs}
                </p>
                <p>
                  <strong>Effort:</strong> {option.effort} &nbsp;
                  <strong>Risk reduction:</strong> {option.risk_reduction}
                </p>
              </div>
            ))}
            <p>
              <strong>Why this recommendation:</strong> {plan.recommendation_rationale}
            </p>
          </section>

          <section>
            <h3>Phased roadmap</h3>
            <div className="roadmap">
              {plan.roadmap.map((phase) => (
                <div key={phase.phase} className="phase">
                  <h4>{phase.phase}</h4>
                  <ul>
                    {phase.items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <section>
        <h3>Human approval and change ticket</h3>
        {!approval?.approval_required ? (
          <p>
            No approval was required under the policy, so no change ticket was requested.
          </p>
        ) : approval.approved ? (
          <p>
            Approved by a human. Simulated ticket{" "}
            <strong>
              <code>{approval.ticket_number}</code>
            </strong>{" "}
            was created.
            {approval.comment && <> Comment: “{approval.comment}”</>}
          </p>
        ) : (
          <p>
            Approval was required and <strong>rejected</strong>, so no ticket was created.
            {approval.comment && <> Comment: “{approval.comment}”</>}
          </p>
        )}
      </section>

      {report.removed_claims.length > 0 && (
        <section>
          <h3>Claims removed during review</h3>
          <p className="hint">
            The evidence reviewer rejected these for citing evidence that does not exist.
          </p>
          <ul>
            {report.removed_claims.map((c) => (
              <li key={c.claim}>
                <strong>{c.claim}</strong> — {c.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3>Limitations</h3>
        <ul>
          {report.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

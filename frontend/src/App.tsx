import { useEffect, useState } from "react";
import { ApiError, api } from "./api/client";
import { ApprovalBanner } from "./components/ApprovalBanner";
import { AssessmentForm } from "./components/AssessmentForm";
import { ProgressPanel } from "./components/ProgressPanel";
import { ReportView } from "./components/ReportView";
import { TracePanel } from "./components/TracePanel";
import type { Assessment, SampleApp, TraceEvent } from "./types/api";

export default function App() {
  const [sampleApps, setSampleApps] = useState<SampleApp[]>([]);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingApps, setLoadingApps] = useState(true);

  useEffect(() => {
    api
      .listSampleApps()
      .then(setSampleApps)
      .catch((e) => setError(describe(e)))
      .finally(() => setLoadingApps(false));
  }, []);

  async function refreshTrace(assessmentId: string) {
    // A trace failure shouldn't hide a successful assessment, so it's reported
    // separately rather than replacing the report.
    try {
      setTrace(await api.getTrace(assessmentId));
    } catch (e) {
      setError(`Assessment succeeded, but the trace could not be loaded: ${describe(e)}`);
    }
  }

  async function handleRun(sampleAppId: string, objective: string) {
    setRunning(true);
    setError(null);
    setAssessment(null);
    setTrace([]);
    try {
      const result = await api.createAssessment(sampleAppId, objective);
      setAssessment(result);
      await refreshTrace(result.id);
    } catch (e) {
      setError(describe(e));
    } finally {
      setRunning(false);
    }
  }

  async function handleDecision(approved: boolean, comment: string) {
    if (!assessment) return;
    setDeciding(true);
    setError(null);
    try {
      const result = await api.submitApproval(assessment.id, approved, comment);
      setAssessment(result);
      await refreshTrace(result.id);
    } catch (e) {
      setError(describe(e));
    } finally {
      setDeciding(false);
    }
  }

  return (
    <main>
      <header>
        <h1>Enterprise Modernization Assessment &amp; Change Orchestrator</h1>
        <p className="subtitle">
          A multi-agent workflow that assesses a legacy service against engineering standards,
          cites its evidence, asks a human before acting, and produces an auditable report.
        </p>
        <div className="banner warning">
          <strong>Local development demo.</strong> Single user, no authentication. All sample
          applications and findings are <strong>synthetic demo data</strong> — they describe no
          real system. Change tickets are simulated; nothing is sent to ServiceNow, and no code
          or infrastructure is ever modified.
        </div>
      </header>

      {error && (
        <div className="banner error" role="alert">
          <strong>Something went wrong.</strong> {error}
          <button type="button" className="dismiss" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {loadingApps ? (
        <div className="card">
          <p>Loading sample applications…</p>
        </div>
      ) : sampleApps.length === 0 ? (
        <div className="card">
          <p>
            No sample applications available. The API may be unreachable — check that the
            backend is running.
          </p>
        </div>
      ) : (
        <AssessmentForm sampleApps={sampleApps} disabled={running} onSubmit={handleRun} />
      )}

      {running && (
        <div className="card">
          <p>Running the workflow… retrieval, analysis, planning, and review.</p>
        </div>
      )}

      {assessment && <ProgressPanel assessment={assessment} />}

      {assessment?.pending_approval && (
        <ApprovalBanner
          request={assessment.pending_approval}
          submitting={deciding}
          onDecide={handleDecision}
        />
      )}

      {assessment?.report && <ReportView report={assessment.report} />}

      {assessment && <TracePanel events={trace} />}
    </main>
  );
}

function describe(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Unexpected error.";
}

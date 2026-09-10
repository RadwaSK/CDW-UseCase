import type { Assessment, SampleApp, TraceEvent } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API = `${API_BASE}/api/v1`;

/** An API failure carrying the server's message, so the UI can show why. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // Network-level failure: the API isn't reachable at all.
    throw new ApiError(
      `Cannot reach the API at ${API_BASE}. Is the backend running?`,
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

/** FastAPI returns `detail` as a string or as a list of validation objects. */
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: string[]; msg?: string }) =>
          [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "),
        )
        .join("; ");
    }
  } catch {
    // Fall through to the generic message below.
  }
  return `Request failed (HTTP ${response.status})`;
}

export const api = {
  listSampleApps: () => request<SampleApp[]>("/sample-apps"),

  createAssessment: (sampleAppId: string, objective: string) =>
    request<Assessment>("/assessments", {
      method: "POST",
      body: JSON.stringify({ sample_app_id: sampleAppId, objective }),
    }),

  submitApproval: (assessmentId: string, approved: boolean, comment: string) =>
    request<Assessment>(`/assessments/${assessmentId}/approval`, {
      method: "POST",
      body: JSON.stringify({ approved, comment }),
    }),

  getAssessment: (assessmentId: string) =>
    request<Assessment>(`/assessments/${assessmentId}`),

  getTrace: (assessmentId: string) =>
    request<TraceEvent[]>(`/assessments/${assessmentId}/trace`),
};

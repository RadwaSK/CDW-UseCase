import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import type { Assessment, SampleApp } from "../types/api";

const SAMPLE_APPS: SampleApp[] = [
  { id: "legacy_order_service", name: "Legacy Order Service", description: "Has planted issues." },
  { id: "modern_inventory_service", name: "Modern Inventory Service", description: "Clean." },
];

const PAUSED: Assessment = {
  id: "a-1",
  sample_app_id: "legacy_order_service",
  objective: "Prepare for cloud.",
  status: "awaiting_approval",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  report: null,
  pending_approval: {
    type: "approval_request",
    assessment_id: "a-1",
    reasons: ["2 critical finding(s): hard-coded key; PII in logs"],
    highest_severity: "critical",
    proposed_action: "Create a simulated ServiceNow change ticket. No code is modified.",
    recommended_option: "Remediate in place",
    estimated_effort: "high",
  },
};

/** Routes fetch by URL so tests describe the API, not call order. */
function mockApi(handlers: Record<string, unknown>, { failOn }: { failOn?: string } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const path = url.replace(/^.*\/api\/v1/, "");
      if (failOn && path.includes(failOn)) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ detail: "Assessment failed to complete." }),
        };
      }
      const key = Object.keys(handlers).find((k) => path.startsWith(k));
      if (!key) throw new Error(`unhandled path: ${path}`);
      return { ok: true, status: 200, json: async () => handlers[key] };
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("always shows the synthetic-data and local-dev warning", async () => {
    mockApi({ "/sample-apps": SAMPLE_APPS });
    render(<App />);

    expect(screen.getByText(/local development demo/i)).toBeInTheDocument();
    expect(screen.getByText(/synthetic demo data/i)).toBeInTheDocument();
    await screen.findByLabelText(/sample application/i);
  });

  it("surfaces a network failure visibly instead of failing silently", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("network down");
    }));

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/cannot reach the api/i);
  });

  it("shows the server's error message when an assessment fails", async () => {
    mockApi({ "/sample-apps": SAMPLE_APPS }, { failOn: "/assessments" });
    render(<App />);

    await userEvent.selectOptions(
      await screen.findByLabelText(/sample application/i),
      "legacy_order_service",
    );
    await userEvent.click(screen.getByRole("button", { name: /run assessment/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/assessment failed to complete/i);
  });

  it("renders the approval banner with its reasons when the run pauses", async () => {
    mockApi({ "/sample-apps": SAMPLE_APPS, "/assessments/a-1/trace": [], "/assessments": PAUSED });
    render(<App />);

    await userEvent.selectOptions(
      await screen.findByLabelText(/sample application/i),
      "legacy_order_service",
    );
    await userEvent.click(screen.getByRole("button", { name: /run assessment/i }));

    expect(await screen.findByText(/human approval required/i)).toBeInTheDocument();
    expect(screen.getByText(/hard-coded key; PII in logs/i)).toBeInTheDocument();
    // The user must be told approval only creates a simulated ticket.
    expect(screen.getByText(/no code is modified/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  it("submits an approval decision and shows the resulting ticket", async () => {
    const approved: Assessment = {
      ...PAUSED,
      status: "completed",
      pending_approval: null,
      report: {
        executive_summary: "Two critical findings.",
        scope: {
          sample_app_id: "legacy_order_service",
          objective: "Prepare for cloud.",
          files_reviewed: ["legacy_order_service/config.py"],
          evidence_count: 6,
        },
        architecture_summary: "Flask service.",
        architecture_findings: [],
        risk_register: [],
        risk_findings: [
          {
            category: "secret",
            title: "Hard-coded credential",
            description: "Key literal in config.",
            severity: "critical",
            recommended_action: "Move to a vault.",
            policy_reference: "security_standard.md",
            evidence: [
              {
                file_path: "legacy_order_service/config.py",
                chunk_id: "c1",
                snippet: 'PAYMENT_GATEWAY_API_KEY = "DEMO_KEY"',
                source: "config.py",
                start_line: 10,
                end_line: 11,
              },
            ],
            confidence: 0.95,
          },
        ],
        plan: null,
        approval: {
          approval_required: true,
          approved: true,
          comment: "Approved.",
          ticket_number: "CHG-DEMO-0001",
        },
        removed_claims: [],
        limitations: ["Sample data is synthetic."],
        overall_risk_level: "critical",
      },
    };

    let approvalSubmitted = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const path = url.replace(/^.*\/api\/v1/, "");
        if (path.includes("/approval")) {
          approvalSubmitted = true;
          expect(JSON.parse(String(init?.body)).approved).toBe(true);
          return { ok: true, status: 200, json: async () => approved };
        }
        if (path.includes("/trace")) return { ok: true, status: 200, json: async () => [] };
        if (path.startsWith("/sample-apps"))
          return { ok: true, status: 200, json: async () => SAMPLE_APPS };
        return { ok: true, status: 201, json: async () => PAUSED };
      }),
    );

    render(<App />);
    await userEvent.selectOptions(
      await screen.findByLabelText(/sample application/i),
      "legacy_order_service",
    );
    await userEvent.click(screen.getByRole("button", { name: /run assessment/i }));
    await userEvent.click(await screen.findByRole("button", { name: /approve/i }));

    await waitFor(() => expect(approvalSubmitted).toBe(true));
    expect(await screen.findByText(/CHG-DEMO-0001/)).toBeInTheDocument();
    // Evidence must be visible for each finding.
    expect(
      screen.getByText(/legacy_order_service\/config\.py:10-11/),
    ).toBeInTheDocument();
  });
});

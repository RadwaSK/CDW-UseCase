export type Severity = "low" | "medium" | "high" | "critical";
export type Effort = "low" | "medium" | "high";

export interface SampleApp {
  id: string;
  name: string;
  description: string;
}

export interface EvidenceReference {
  file_path: string;
  chunk_id: string;
  snippet: string;
  source: string;
  start_line: number;
  end_line: number;
}

export interface ArchitectureFinding {
  category: string;
  title: string;
  description: string;
  evidence: EvidenceReference[];
  confidence: number;
}

export interface RiskFinding {
  category: string;
  title: string;
  description: string;
  severity: Severity;
  recommended_action: string;
  policy_reference: string;
  evidence: EvidenceReference[];
  confidence: number;
}

export interface RiskRegisterEntry {
  severity: Severity;
  finding: string;
  recommended_action: string;
  policy_reference: string;
  evidence_summary: string[];
}

export interface ModernizationOption {
  name: string;
  description: string;
  trade_offs: string;
  effort: Effort;
  risk_reduction: string;
  addresses: string[];
  evidence: EvidenceReference[];
}

export interface RoadmapPhase {
  phase: string;
  items: string[];
}

export interface ModernizationPlan {
  summary: string;
  options: ModernizationOption[];
  recommended_option: string;
  recommendation_rationale: string;
  roadmap: RoadmapPhase[];
  estimated_effort: Effort;
  touches_auth: boolean;
  evidence: EvidenceReference[];
}

export interface RemovedClaim {
  claim: string;
  reason: string;
}

export interface ApprovalRecord {
  approval_required: boolean;
  approved: boolean | null;
  comment: string | null;
  ticket_number: string | null;
}

export interface ScopeSummary {
  sample_app_id: string;
  objective: string;
  files_reviewed: string[];
  evidence_count: number;
}

export interface AssessmentReport {
  executive_summary: string;
  scope: ScopeSummary;
  architecture_summary: string;
  architecture_findings: ArchitectureFinding[];
  risk_register: RiskRegisterEntry[];
  risk_findings: RiskFinding[];
  plan: ModernizationPlan | null;
  approval: ApprovalRecord | null;
  removed_claims: RemovedClaim[];
  limitations: string[];
  overall_risk_level: Severity;
}

export interface PendingApproval {
  type: string;
  assessment_id: string;
  reasons: string[];
  highest_severity: Severity;
  proposed_action: string;
  recommended_option: string | null;
  estimated_effort: Effort | null;
}

export interface Assessment {
  id: string;
  sample_app_id: string;
  objective: string;
  status: string;
  created_at: string;
  updated_at: string;
  report: AssessmentReport | null;
  pending_approval: PendingApproval | null;
}

export interface TraceEvent {
  node: string;
  event_type: string;
  duration_ms: number | null;
  payload: Record<string, unknown>;
  error_class: string | null;
  created_at: string;
}

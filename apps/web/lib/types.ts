/** Shared domain types for the dashboard. */

export type Risk = "low" | "medium" | "high";
export type Confidence = "low" | "medium" | "high";
export type Reversibility = "reversible" | "partially_reversible" | "irreversible";

export interface KpiStat {
  label: string;
  value: string;
  sub?: string;
  tone?: "default" | "success" | "warning" | "critical" | "accent";
  tooltip?: string;
}

export interface CostPoint {
  date: string;
  amount: number;
}

export interface SpendByService {
  service: string;
  amount: number;
}

export interface OpportunityCategory {
  category: string;
  count: number;
  monthlySavings: number;
}

export interface TopResource {
  name: string;
  service: string;
  region: string;
  monthlyCost: number;
  utilizationPct?: number | null;
}

export interface OpportunityRow {
  resource: string;
  service: string;
  region: string;
  currentMonthlyCost: number;
  estimatedMonthlySavings: number;
  risk: Risk;
  recommendation: string;
  status: string;
}

export interface ResourceRecord {
  id: string;
  name: string;
  resourceId: string;
  arn: string;
  service: "ec2" | "ebs" | "eip" | "rds" | "elbv2";
  region: string;
  environment?: string;
  owner?: string;
  state: string;
  cpuAvgPct?: number | null;
  cpuP95Pct?: number | null;
  monthlyCost?: number | null;
  optimizationStatus:
    | "idle"
    | "underutilized"
    | "optimized"
    | "unknown"
    | "not_analyzed"
    | "excluded";
  lastDiscovered: string;
}

export interface RecommendationEvidence {
  cpuAveragePct?: number | null;
  cpuP95Pct?: number | null;
  networkInBytesAvg?: number | null;
  networkOutBytesAvg?: number | null;
  state?: string;
  environment?: string;
  matchingRule?: string;
  missingMetrics: string[];
  source: "measurement" | "estimate" | "fixture";
}

export interface RecommendationItem {
  id: string;
  resourceId: string;
  resourceName: string;
  account: string;
  region: string;
  findingType: "idle_ec2" | "rightsizing_ec2" | "unattached_ebs" | "idle_elastic_ip" | "cost_anomaly";
  category: "idle" | "rightsizing" | "storage" | "networking" | "anomaly";
  evidence: RecommendationEvidence;
  observationWindowDays: number;
  metricCoveragePct: number | null;
  currentMonthlyCost: number | null;
  projectedMonthlyCost: number | null;
  estimatedMonthlySavings: number | null;
  estimatedAnnualSavings: number | null;
  currency: string;
  isEstimate: boolean;
  confidence: Confidence;
  risk: Risk;
  reversibility: Reversibility;
  ruleId: string;
  ruleVersion: string;
  action: string;
  status: "open" | "dismissed" | "approval_requested" | "approved" | "executed" | "superseded" | "expired";
  createdAt: string;
}

export interface ApprovalItem {
  id: string;
  resourceName: string;
  action: string;
  requestedBy: string;
  estimatedMonthlySavings: number | null;
  risk: Risk;
  requestedAt: string;
  expiresAt: string | null;
  status:
    | "pending"
    | "approved"
    | "queued"
    | "executing"
    | "completed"
    | "failed"
    | "rejected"
    | "expired";
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  actorType: "user" | "system" | "worker";
  eventType: string;
  entityType: string;
  summary: string;
  severity: "info" | "warning" | "critical";
  outcome: "success" | "failure" | "pending";
}

export interface CostExplorerView {
  trend: CostPoint[];
  previousTrend: CostPoint[];
  byService: SpendByService[];
  byRegion: SpendByService[];
  topDrivers: SpendByService[];
  previousTotal: number;
  currentTotal: number;
  unallocated: number;
  aggregation: "daily" | "weekly" | "monthly";
  updatedAt: string;
  source: string;
}

export interface DemoMarker {
  demo: true;
  source: "fixture" | "sample";
}
import { Badge } from "@/components/ui/badge";

type Tone = "neutral" | "accent" | "accent2" | "success" | "warning" | "critical";

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const RISK_TONE: Record<string, Tone> = {
  low: "success",
  medium: "warning",
  high: "critical",
};

const STATUS_TONE: Record<string, Tone> = {
  open: "accent",
  pending: "warning",
  approval_requested: "warning",
  approved: "accent2",
  queued: "accent2",
  executing: "accent2",
  completed: "success",
  executed: "success",
  dismissed: "neutral",
  rejected: "neutral",
  failed: "critical",
  expired: "critical",
  superseded: "neutral",
  // optimization status
  idle: "warning",
  underutilized: "warning",
  optimized: "success",
  unknown: "neutral",
  not_analyzed: "neutral",
  excluded: "neutral",
};

const SEVERITY_TONE: Record<string, Tone> = {
  info: "accent",
  warning: "warning",
  critical: "critical",
};

const OUTCOME_TONE: Record<string, Tone> = {
  success: "success",
  failure: "critical",
  pending: "warning",
};

export function StatusBadge({ value, label }: { value: string; label?: string }) {
  const tone = STATUS_TONE[value] ?? SEVERITY_TONE[value] ?? OUTCOME_TONE[value] ?? "neutral";
  return <Badge variant={tone}>{label ?? humanize(value)}</Badge>;
}

export function RiskBadge({ risk }: { risk: string }) {
  return <Badge variant={RISK_TONE[risk] ?? "neutral"}>{humanize(risk)} risk</Badge>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge variant={SEVERITY_TONE[severity] ?? "neutral"}>{humanize(severity)}</Badge>;
}

export function OutcomeBadge({ outcome }: { outcome: string }) {
  return <Badge variant={OUTCOME_TONE[outcome] ?? "neutral"}>{humanize(outcome)}</Badge>;
}

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  const tone: Tone = confidence === "high" ? "success" : confidence === "medium" ? "warning" : "neutral";
  return <Badge variant={tone}>{humanize(confidence)} confidence</Badge>;
}
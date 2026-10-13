"use client";

import { useMemo, useState } from "react";

import { DemoBanner } from "@/components/demo-banner";
import { PageHeader } from "@/components/page-header";
import { ConfidenceBadge, RiskBadge, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { demoRecommendations } from "@/lib/fixtures";
import { formatMoney, formatPercent } from "@/lib/format";

const CATEGORY_LABEL: Record<string, string> = {
  idle: "Idle resources",
  rightsizing: "Rightsizing",
  storage: "Storage cleanup",
  networking: "Networking",
  anomaly: "Cost anomalies",
};

export default function RecommendationsPage() {
  const [category, setCategory] = useState("all");
  const [risk, setRisk] = useState("all");

  const rows = useMemo(
    () =>
      demoRecommendations.filter(
        (r) =>
          (category === "all" || r.category === category) &&
          (risk === "all" || r.risk === risk),
      ),
    [category, risk],
  );

  return (
    <>
      <DemoBanner />
      <PageHeader
        title="Optimization Recommendations"
        description="Every finding is reproducible from its stored evidence and rule version. Financial estimates are labeled; nothing here executes automatically."
      />

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-3">
        <div className="space-y-1">
          <Label htmlFor="reco-category">Finding type</Label>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger id="reco-category" className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All findings</SelectItem>
              {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="reco-risk">Risk</Label>
          <Select value={risk} onValueChange={setRisk}>
            <SelectTrigger id="reco-risk" className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All risk levels</SelectItem>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <span className="ml-auto text-xs text-secondary">{rows.length} findings</span>
      </div>

      <div className="space-y-4">
        {rows.map((rec) => (
          <Card key={rec.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <CardTitle>{rec.resourceName}</CardTitle>
                  <p className="mt-0.5 text-xs text-secondary">
                    {rec.account} · {rec.region} · {rec.findingType.replace(/_/g, " ")}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge value={rec.status} />
                  <RiskBadge risk={rec.risk} />
                  <ConfidenceBadge confidence={rec.confidence} />
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="space-y-2 lg:col-span-1">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-secondary">Evidence</h3>
                <ul className="space-y-1 text-sm text-primary">
                  {rec.evidence.cpuAveragePct != null ? <li>CPU average: {formatPercent(rec.evidence.cpuAveragePct)}</li> : null}
                  {rec.evidence.cpuP95Pct != null ? <li>CPU p95/max: {formatPercent(rec.evidence.cpuP95Pct)}</li> : null}
                  {rec.evidence.networkInBytesAvg != null ? <li>Network in (avg): {rec.evidence.networkInBytesAvg} B</li> : null}
                  {rec.evidence.networkOutBytesAvg != null ? <li>Network out (avg): {rec.evidence.networkOutBytesAvg} B</li> : null}
                  {rec.evidence.state ? <li>State: {rec.evidence.state}</li> : null}
                  {rec.evidence.environment ? <li>Environment: {rec.evidence.environment}</li> : null}
                </ul>
                <p className="text-[11px] text-secondary">
                  Observation window: {rec.observationWindowDays} days · Metric coverage:{" "}
                  {rec.metricCoveragePct == null ? "n/a" : formatPercent(rec.metricCoveragePct)}
                </p>
                {rec.evidence.missingMetrics.length > 0 ? (
                  <p className="text-[11px] text-warning">
                    Missing telemetry: {rec.evidence.missingMetrics.join(", ")} — results may be less certain.
                  </p>
                ) : null}
              </div>

              <div className="space-y-2 lg:col-span-1">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-secondary">Financial impact</h3>
                <dl className="space-y-1 text-sm">
                  <Line label="Current cost / mo" value={rec.currentMonthlyCost == null ? "—" : formatMoney(rec.currentMonthlyCost)} />
                  <Line label="Projected / mo" value={rec.projectedMonthlyCost == null ? "—" : formatMoney(rec.projectedMonthlyCost)} />
                  <Line label="Est. savings / mo" value={formatMoney(rec.estimatedMonthlySavings ?? 0)} accent />
                  <Line label="Est. savings / yr" value={formatMoney(rec.estimatedAnnualSavings ?? 0)} accent />
                </dl>
                <p className="text-[11px] text-secondary">
                  {rec.isEstimate ? "Estimate — not a billed amount." : "Measured amount."} Currency {rec.currency}.
                </p>
              </div>

              <div className="space-y-2 lg:col-span-1">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-secondary">Recommended action</h3>
                <p className="text-sm text-primary">{rec.action.replace(/_/g, " ")}</p>
                <p className="text-[11px] text-secondary">
                  Rule {rec.ruleId} · v{rec.ruleVersion} · reversibility {rec.reversibility.replace(/_/g, " ")}
                </p>
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button variant="secondary" size="sm">View details</Button>
                  <Button variant="secondary" size="sm">Compare alternatives</Button>
                  <Button variant="default" size="sm">Request approval</Button>
                  <Button variant="ghost" size="sm">Dismiss</Button>
                </div>
                <p className="text-[11px] text-secondary">
                  Actions require human approval and are disabled in this release (read-only).
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
        {rows.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-secondary">
              No findings match the current filters.
            </CardContent>
          </Card>
        ) : null}
      </div>
    </>
  );
}

function Line({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border pb-1 text-sm last:border-b-0">
      <dt className="text-secondary">{label}</dt>
      <dd className={`tabular ${accent ? "text-success" : "text-primary"}`}>{value}</dd>
    </div>
  );
}
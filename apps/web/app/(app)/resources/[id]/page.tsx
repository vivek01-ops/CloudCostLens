"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ChartCard } from "@/components/chart-card";
import { DemoBanner } from "@/components/demo-banner";
import { KpiStrip } from "@/components/kpi";
import { PageHeader } from "@/components/page-header";
import { ConfidenceBadge, RiskBadge, StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { spendTrendOption } from "@/lib/charts";
import { demoRecommendations, demoResources, demoUtilizationSeries } from "@/lib/fixtures";
import { formatDateTime, formatMoney, formatPercent } from "@/lib/format";

export default function ResourceDetailsPage() {
  const params = useParams<{ id: string }>();
  const resource = demoResources.find((r) => r.id === params.id);

  if (!resource) {
    return (
      <>
        <PageHeader title="Resource not found" description="The requested resource is not in the current inventory view." />
        <Link href="/resources" className="text-sm text-accent hover:underline">
          ← Back to Resources
        </Link>
      </>
    );
  }

  const recommendations = demoRecommendations.filter((r) => r.resourceId === resource.id);
  const utilizationSeries = demoUtilizationSeries(resource.cpuAvgPct);

  const kpis = [
    { label: "State", value: resource.state },
    {
      label: "CPU average",
      value: resource.cpuAvgPct == null ? "No data" : formatPercent(resource.cpuAvgPct),
      sub: resource.cpuAvgPct == null ? "telemetry unavailable" : "14-day window",
    },
    {
      label: "CPU p95",
      value: resource.cpuP95Pct == null ? "No data" : formatPercent(resource.cpuP95Pct),
    },
    {
      label: "Est. cost / mo",
      value: resource.monthlyCost == null ? "—" : formatMoney(resource.monthlyCost),
      sub: "service-level estimate",
    },
    { label: "Optimization", value: resource.optimizationStatus.replace("_", " ") },
  ];

  return (
    <>
      <DemoBanner />
      <Link href="/resources" className="inline-flex items-center gap-1 text-xs text-secondary hover:text-primary">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to Resources
      </Link>
      <PageHeader
        title={resource.name}
        description={`${resource.resourceId} · ${resource.region} · last discovered ${formatDateTime(resource.lastDiscovered)}`}
        actions={<StatusBadge value={resource.optimizationStatus} />}
      />
      <KpiStrip stats={kpis} />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="utilization">Utilization</TabsTrigger>
          <TabsTrigger value="cost">Cost History</TabsTrigger>
          <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Resource configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <Row label="ARN" value={<span className="font-mono text-xs">{resource.arn}</span>} />
                <Row label="Service" value={resource.service.toUpperCase()} />
                <Row label="Region" value={resource.region} />
                <Row label="Environment" value={resource.environment ?? "—"} />
                <Row label="Owner" value={resource.owner ?? "—"} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Attribution limits</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-secondary">
                Cost shown here is derived from service-level Cost Explorer data and may be
                approximate. Per-resource exact cost is only shown when the billing source
                supports resource-level attribution.
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="utilization">
          {resource.cpuAvgPct == null ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-secondary">
                No utilization telemetry is available for this resource. This is not the same
                as zero usage.
              </CardContent>
            </Card>
          ) : (
            <ChartCard
              title="CPU utilization"
              description="Average CPU over the observation window"
              option={spendTrendOption(utilizationSeries)}
              note={`Metric coverage: measured for ${resource.environment ?? "this resource"}; memory metrics not available without the CloudWatch agent.`}
            />
          )}
        </TabsContent>

        <TabsContent value="cost">
          <ChartCard title="Cost history" description="Estimated daily cost attributed to this resource" option={spendTrendOption(utilizationSeries.map((p) => ({ ...p, amount: p.amount * 0.1 })))} note="Approximate — attribution derived from service-level data." />
        </TabsContent>

        <TabsContent value="recommendations">
          {recommendations.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-secondary">
                No open recommendations for this resource.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {recommendations.map((rec) => (
                <Card key={rec.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>{rec.ruleId} · v{rec.ruleVersion}</CardTitle>
                      <div className="flex gap-2">
                        <RiskBadge risk={rec.risk} />
                        <ConfidenceBadge confidence={rec.confidence} />
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-secondary">
                    <p>{rec.action.replace(/_/g, " ")}</p>
                    <p>
                      Estimated savings: <span className="text-success">{formatMoney(rec.estimatedMonthlySavings ?? 0)}</span> / month
                      {" "}({formatMoney(rec.estimatedAnnualSavings ?? 0)} / year) — estimate.
                    </p>
                    <p>
                      Evidence source: {rec.evidence.source}; observation window {rec.observationWindowDays} days;
                      coverage {rec.metricCoveragePct == null ? "n/a" : formatPercent(rec.metricCoveragePct)}.
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="configuration">
          <Card>
            <CardHeader>
              <CardTitle>Tags</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-secondary">
              Tags are loaded from the resource inventory. Values shown in the Resources table
              are a subset of the full tag set.
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle>Previous optimization actions</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-secondary">
              No prior actions recorded for this resource. All actions are human-approved and
              recorded in the audit trail.
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border pb-2 last:border-b-0 last:pb-0">
      <span className="text-secondary">{label}</span>
      <span className="text-primary">{value}</span>
    </div>
  );
}
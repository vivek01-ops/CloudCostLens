"use client";

import { DataTable, type Column } from "@/components/data-table";
import { ChartCard } from "@/components/chart-card";
import { ControlBar } from "@/components/control-bar";
import { DemoBanner } from "@/components/demo-banner";
import { KpiStrip } from "@/components/kpi";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OutcomeBadge } from "@/components/status-badge";
import {
  opportunitiesByCategoryOption,
  spendByServiceOption,
  spendTrendOption,
  topDriversOption,
} from "@/lib/charts";
import {
  demoActivity,
  demoCostTrend,
  demoKpis,
  demoOpportunities,
  demoOpportunityCategories,
  demoSpendByService,
  demoTopResources,
} from "@/lib/fixtures";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { OpportunityRow } from "@/lib/types";

const columns: Column<OpportunityRow>[] = [
  { key: "resource", header: "Resource", render: (r) => <span className="text-primary">{r.resource}</span>, value: (r) => r.resource },
  { key: "service", header: "Service", render: (r) => r.service, value: (r) => r.service },
  { key: "region", header: "Region", render: (r) => <span className="text-secondary">{r.region}</span>, value: (r) => r.region },
  { key: "current", header: "Current / mo", align: "right", render: (r) => formatMoney(r.currentMonthlyCost), value: (r) => r.currentMonthlyCost },
  { key: "savings", header: "Est. savings / mo", align: "right", render: (r) => <span className="text-success">{formatMoney(r.estimatedMonthlySavings)}</span>, value: (r) => r.estimatedMonthlySavings },
  { key: "risk", header: "Risk", render: (r) => <span className="capitalize text-secondary">{r.risk}</span>, value: (r) => r.risk },
  { key: "recommendation", header: "Recommendation", render: (r) => <span className="text-secondary">{r.recommendation}</span>, value: (r) => r.recommendation },
  { key: "status", header: "Status", render: (r) => <span className="capitalize text-secondary">{r.status.replace("_", " ")}</span>, value: (r) => r.status },
];

export default function OverviewPage() {
  const accounts = [{ id: "111122223333", label: "111122223333 · demo-account" }];
  const regions = ["eu-west-1", "us-east-1"];

  return (
    <>
      <DemoBanner />
      <PageHeader
        title="Cloud Overview"
        description="Understand AWS spending, identify waste, and review optimization opportunities."
      />
      <ControlBar accounts={accounts} regions={regions} lastRefreshed="today 09:14 UTC" />
      <KpiStrip stats={demoKpis} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="Cloud spend trend"
          description="Daily unblended cost, last 30 days"
          option={spendTrendOption(demoCostTrend)}
          note="Source: Cost Explorer (fixture). Billing data may lag 24–48 hours."
        />
        <ChartCard
          title="Spend by AWS service"
          description="Current month to date"
          option={spendByServiceOption(demoSpendByService)}
        />
        <ChartCard
          title="Optimization opportunities by category"
          description="Estimated monthly savings"
          option={opportunitiesByCategoryOption(demoOpportunityCategories)}
        />
        <ChartCard
          title="Top cost-driving resources"
          description="Highest monthly cost resources"
          option={topDriversOption(demoTopResources)}
        />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-primary">High-value optimization opportunities</h2>
        <DataTable
          columns={columns}
          rows={demoOpportunities}
          getRowId={(r) => r.resource}
          exportName="opportunities"
          searchPlaceholder="Search opportunities…"
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-primary">Recent activity</h2>
        <Card>
          <CardHeader>
            <CardTitle>Audit trail</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {demoActivity.slice(0, 6).map((event) => (
              <div key={event.id} className="flex items-start justify-between gap-4 border-b border-border pb-3 last:border-b-0 last:pb-0">
                <div className="min-w-0">
                  <div className="text-sm text-primary">{event.summary}</div>
                  <div className="mt-0.5 text-[11px] text-secondary">
                    {event.actor} · {event.eventType} · {formatDateTime(event.timestamp)}
                  </div>
                </div>
                <OutcomeBadge outcome={event.outcome} />
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </>
  );
}
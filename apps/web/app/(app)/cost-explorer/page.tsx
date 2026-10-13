"use client";

import { DataTable, type Column } from "@/components/data-table";
import { ChartCard } from "@/components/chart-card";
import { ControlBar } from "@/components/control-bar";
import { DemoBanner } from "@/components/demo-banner";
import { KpiStrip } from "@/components/kpi";
import { PageHeader } from "@/components/page-header";
import {
  spendByServiceOption,
  spendComparisonOption,
  spendTrendOption,
  topDriversOption,
} from "@/lib/charts";
import { demoCostExplorer } from "@/lib/fixtures";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { SpendByService } from "@/lib/types";

const serviceColumns: Column<SpendByService>[] = [
  { key: "service", header: "Service", render: (r) => r.service, value: (r) => r.service },
  { key: "amount", header: "Spend (period)", align: "right", render: (r) => formatMoney(r.amount), value: (r) => r.amount },
];

export default function CostExplorerPage() {
  const data = demoCostExplorer;
  const delta = data.currentTotal - data.previousTotal;
  const deltaPct = (delta / data.previousTotal) * 100;

  const kpis = [
    { label: "Period spend", value: formatMoney(data.currentTotal), sub: "USD · unblended cost" },
    { label: "Previous period", value: formatMoney(data.previousTotal), sub: "for comparison" },
    {
      label: "Change",
      value: `${delta >= 0 ? "+" : ""}${deltaPct.toFixed(1)}%`,
      sub: `${delta >= 0 ? "+" : ""}${formatMoney(delta)}`,
      tone: delta >= 0 ? ("critical" as const) : ("success" as const),
    },
    { label: "Unallocated", value: formatMoney(data.unallocated), sub: "no service attribution", tone: "warning" as const },
    { label: "Aggregation", value: data.aggregation },
    { label: "Last updated", value: formatDateTime(data.updatedAt), sub: `source: ${data.source}` },
  ];

  return (
    <>
      <DemoBanner />
      <PageHeader
        title="Cost Explorer"
        description="AWS Cost Explorer data with defined currency, reporting period, and attribution limits. Recent billing data may be incomplete."
      />
      <ControlBar
        accounts={[{ id: "111122223333", label: "111122223333 · demo-account" }]}
        regions={["eu-west-1", "us-east-1"]}
        showDateRange
        lastRefreshed="today 06:00 UTC"
      />
      <KpiStrip stats={kpis} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Spend trend" description="Daily unblended cost" option={spendTrendOption(data.trend)} note="Source: Cost Explorer (fixture). Currency: USD." />
        <ChartCard title="Current vs previous period" description="Daily comparison" option={spendComparisonOption(data.trend, data.previousTrend)} />
        <ChartCard title="Spend by service" description="Current period" option={spendByServiceOption(data.byService)} />
        <ChartCard title="Top cost drivers" description="By service" option={topDriversOption(data.byService.map((s) => ({ name: s.service.replace("Amazon ", ""), monthlyCost: s.amount })))} />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-primary">Service breakdown</h2>
        <DataTable columns={serviceColumns} rows={data.byService} getRowId={(r) => r.service} exportName="cost-by-service" searchable={false} />
      </section>
    </>
  );
}
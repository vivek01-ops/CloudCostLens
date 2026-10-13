"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { DataTable, type Column } from "@/components/data-table";
import { ControlBar } from "@/components/control-bar";
import { DemoBanner } from "@/components/demo-banner";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { demoResources } from "@/lib/fixtures";
import { formatDateTime, formatMoney, formatPercent } from "@/lib/format";
import type { ResourceRecord } from "@/lib/types";

const SERVICE_LABEL: Record<string, string> = {
  ec2: "EC2",
  ebs: "EBS",
  eip: "Elastic IP",
  rds: "RDS",
  elbv2: "ELB",
};

const columns: Column<ResourceRecord>[] = [
  {
    key: "name",
    header: "Resource",
    render: (r) => (
      <Link href={`/resources/${r.id}`} className="text-accent hover:underline">
        {r.name}
      </Link>
    ),
    value: (r) => r.name,
  },
  {
    key: "resourceId",
    header: "Resource ID / ARN",
    render: (r) => <span className="font-mono text-xs text-secondary">{r.resourceId}</span>,
    value: (r) => r.resourceId,
  },
  { key: "service", header: "Service", render: (r) => SERVICE_LABEL[r.service] ?? r.service, value: (r) => r.service },
  { key: "region", header: "Region", render: (r) => <span className="text-secondary">{r.region}</span>, value: (r) => r.region },
  { key: "environment", header: "Environment", render: (r) => r.environment ?? "—", value: (r) => r.environment ?? "" },
  { key: "owner", header: "Owner", render: (r) => r.owner ?? "—", value: (r) => r.owner ?? "" },
  { key: "state", header: "State", render: (r) => <span className="capitalize text-secondary">{r.state}</span>, value: (r) => r.state },
  {
    key: "cpu",
    header: "CPU avg",
    align: "right",
    render: (r) => (r.cpuAvgPct === null || r.cpuAvgPct === undefined ? <span className="text-secondary">No data</span> : formatPercent(r.cpuAvgPct)),
    value: (r) => r.cpuAvgPct ?? -1,
  },
  {
    key: "cost",
    header: "Est. cost / mo",
    align: "right",
    render: (r) => (r.monthlyCost == null ? "—" : formatMoney(r.monthlyCost)),
    value: (r) => r.monthlyCost ?? 0,
  },
  {
    key: "status",
    header: "Optimization",
    render: (r) => <StatusBadge value={r.optimizationStatus} />,
    value: (r) => r.optimizationStatus,
  },
  {
    key: "discovered",
    header: "Last discovered",
    render: (r) => <span className="text-secondary">{formatDateTime(r.lastDiscovered)}</span>,
    value: (r) => r.lastDiscovered,
  },
];

export default function ResourcesPage() {
  const [service, setService] = useState("all");
  const [region, setRegion] = useState("all");
  const [state, setState] = useState("all");
  const [environment, setEnvironment] = useState("all");

  const rows = useMemo(
    () =>
      demoResources.filter(
        (r) =>
          (service === "all" || r.service === service) &&
          (region === "all" || r.region === region) &&
          (state === "all" || r.state === state) &&
          (environment === "all" || (r.environment ?? "") === environment),
      ),
    [service, region, state, environment],
  );

  const services = Array.from(new Set(demoResources.map((r) => r.service)));
  const regions = Array.from(new Set(demoResources.map((r) => r.region)));
  const states = Array.from(new Set(demoResources.map((r) => r.state)));
  const environments = Array.from(
    new Set(demoResources.map((r) => r.environment).filter((e): e is string => Boolean(e))),
  );

  return (
    <>
      <DemoBanner />
      <PageHeader
        title="Resources"
        description="Searchable inventory across enabled AWS regions. Utilization of “No data” means telemetry was unavailable — never assume zero usage."
      />
      <ControlBar
        accounts={[{ id: "111122223333", label: "111122223333 · demo-account" }]}
        regions={regions}
        lastRefreshed="today 09:14 UTC"
      />

      <div className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-surface p-3 sm:grid-cols-4">
        <div className="space-y-1">
          <Label htmlFor="filter-service">Service</Label>
          <Select value={service} onValueChange={setService}>
            <SelectTrigger id="filter-service" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All services</SelectItem>
              {services.map((s) => (
                <SelectItem key={s} value={s}>
                  {SERVICE_LABEL[s] ?? s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-region">Region</Label>
          <Select value={region} onValueChange={setRegion}>
            <SelectTrigger id="filter-region" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All regions</SelectItem>
              {regions.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-state">State</Label>
          <Select value={state} onValueChange={setState}>
            <SelectTrigger id="filter-state" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All states</SelectItem>
              {states.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-env">Environment</Label>
          <Select value={environment} onValueChange={setEnvironment}>
            <SelectTrigger id="filter-env" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All environments</SelectItem>
              {environments.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(r) => r.id}
        exportName="resources"
        searchPlaceholder="Search name, ID, owner…"
      />
    </>
  );
}
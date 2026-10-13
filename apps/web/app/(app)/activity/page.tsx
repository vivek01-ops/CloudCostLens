"use client";

import { useMemo, useState } from "react";

import { DataTable, type Column } from "@/components/data-table";
import { DemoBanner } from "@/components/demo-banner";
import { PageHeader } from "@/components/page-header";
import { OutcomeBadge, SeverityBadge } from "@/components/status-badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { demoAuditEvents } from "@/lib/fixtures";
import { formatDateTime } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";

const columns: Column<AuditEvent>[] = [
  { key: "timestamp", header: "Timestamp", render: (r) => <span className="text-secondary">{formatDateTime(r.timestamp)}</span>, value: (r) => r.timestamp },
  { key: "actor", header: "Actor", render: (r) => r.actor, value: (r) => r.actor },
  { key: "eventType", header: "Event", render: (r) => <span className="font-mono text-xs text-secondary">{r.eventType}</span>, value: (r) => r.eventType },
  { key: "entityType", header: "Entity", render: (r) => <span className="text-secondary">{r.entityType}</span>, value: (r) => r.entityType },
  { key: "summary", header: "Summary", render: (r) => r.summary, value: (r) => r.summary },
  { key: "severity", header: "Severity", render: (r) => <SeverityBadge severity={r.severity} />, value: (r) => r.severity },
  { key: "outcome", header: "Outcome", render: (r) => <OutcomeBadge outcome={r.outcome} />, value: (r) => r.outcome },
];

export default function ActivityPage() {
  const [severity, setSeverity] = useState("all");
  const [actor, setActor] = useState("all");

  const rows = useMemo(
    () =>
      demoAuditEvents.filter(
        (e) =>
          (severity === "all" || e.severity === severity) &&
          (actor === "all" || e.actorType === actor),
      ),
    [severity, actor],
  );

  return (
    <>
      <DemoBanner />
      <PageHeader
        title="Activity &amp; Audit"
        description="Append-only audit trail of connections, scans, findings, approvals, and actions. Records cannot be edited or deleted."
      />

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-3">
        <div className="space-y-1">
          <Label htmlFor="audit-severity">Severity</Label>
          <Select value={severity} onValueChange={setSeverity}>
            <SelectTrigger id="audit-severity" className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All severities</SelectItem>
              <SelectItem value="info">Info</SelectItem>
              <SelectItem value="warning">Warning</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-actor">Actor type</Label>
          <Select value={actor} onValueChange={setActor}>
            <SelectTrigger id="audit-actor" className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All actors</SelectItem>
              <SelectItem value="user">User</SelectItem>
              <SelectItem value="system">System</SelectItem>
              <SelectItem value="worker">Worker</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <span className="ml-auto text-xs text-secondary">{rows.length} events</span>
      </div>

      <DataTable columns={columns} rows={rows} getRowId={(r) => r.id} exportName="audit-events" searchPlaceholder="Search events…" pageSize={15} />
    </>
  );
}
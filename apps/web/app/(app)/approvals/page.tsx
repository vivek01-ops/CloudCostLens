"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/data-table";
import { DemoBanner } from "@/components/demo-banner";
import { KpiStrip } from "@/components/kpi";
import { PageHeader } from "@/components/page-header";
import { RiskBadge, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { demoApprovals } from "@/lib/fixtures";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { ApprovalItem } from "@/lib/types";

function count(status: string): number {
  return demoApprovals.filter((a) => a.status === status).length;
}

export default function ApprovalsPage() {
  const [selected, setSelected] = useState<ApprovalItem | null>(null);

  const kpis = [
    { label: "Awaiting review", value: String(count("pending")), tone: "warning" as const },
    { label: "Approved / queued", value: String(count("approved") + count("queued")) },
    { label: "Executing", value: String(count("executing")), tone: "accent" as const },
    { label: "Completed", value: String(count("completed")), tone: "success" as const },
    { label: "Rejected", value: String(count("rejected")) },
    { label: "Failed", value: String(count("failed")), tone: "critical" as const },
  ];

  const columns: Column<ApprovalItem>[] = [
    { key: "resource", header: "Resource", render: (r) => <span className="text-primary">{r.resourceName}</span>, value: (r) => r.resourceName },
    { key: "action", header: "Proposed action", render: (r) => <span className="text-secondary">{r.action}</span>, value: (r) => r.action },
    { key: "requestedBy", header: "Requested by", render: (r) => r.requestedBy, value: (r) => r.requestedBy },
    { key: "savings", header: "Est. savings / mo", align: "right", render: (r) => (r.estimatedMonthlySavings == null ? "—" : formatMoney(r.estimatedMonthlySavings)), value: (r) => r.estimatedMonthlySavings ?? 0 },
    { key: "risk", header: "Risk", render: (r) => <RiskBadge risk={r.risk} />, value: (r) => r.risk },
    { key: "requestedAt", header: "Requested", render: (r) => <span className="text-secondary">{formatDateTime(r.requestedAt)}</span>, value: (r) => r.requestedAt },
    { key: "expiresAt", header: "Expires", render: (r) => <span className="text-secondary">{r.expiresAt ? formatDateTime(r.expiresAt) : "—"}</span>, value: (r) => r.expiresAt ?? "" },
    { key: "status", header: "Status", render: (r) => <StatusBadge value={r.status} />, value: (r) => r.status },
    {
      key: "review",
      header: "",
      render: (r) => (
        <Button variant="secondary" size="sm" onClick={() => setSelected(r)}>
          Review
        </Button>
      ),
      value: () => "",
    },
  ];

  return (
    <>
      <DemoBanner />
      <PageHeader
        title="Approval Center"
        description="Every infrastructure change requires explicit human approval bound to the exact resource, account, action, and parameters. This release is read-only."
      />
      <KpiStrip stats={kpis} />

      <DataTable
        columns={columns}
        rows={demoApprovals}
        getRowId={(r) => r.id}
        exportName="approvals"
        searchPlaceholder="Search approvals…"
      />

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        {selected ? (
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Approval · {selected.resourceName}</DialogTitle>
              <DialogDescription>{selected.id}</DialogDescription>
            </DialogHeader>
            <div className="max-h-[60vh] space-y-4 overflow-y-auto px-5 py-4 text-sm">
              <Detail label="Proposed action" value={selected.action} />
              <Detail label="Account / region" value="111122223333 · eu-west-1" />
              <Detail label="Resource ARN / ID" value={<span className="font-mono text-xs">arn:aws:ec2:eu-west-1:111122223333:instance/i-09a8b7c6d5e4f3a21</span>} />
              <Detail label="Estimated savings" value={selected.estimatedMonthlySavings == null ? "—" : `${formatMoney(selected.estimatedMonthlySavings)} / mo`} />
              <Detail label="Operational risk" value={<RiskBadge risk={selected.risk} />} />
              <Detail label="Expiry" value={selected.expiresAt ? formatDateTime(selected.expiresAt) : "—"} />
              <Detail label="Approver" value="Unassigned (requires approver role)" />

              <div className="rounded-md border border-border bg-surface-2 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-secondary">Risks and exclusions</p>
                <ul className="mt-1 list-disc space-y-1 pl-4 text-secondary">
                  <li>Stopping an instance does not remove attached storage charges.</li>
                  <li>Protected/tagged resources are excluded from execution.</li>
                  <li>Approval is bound to the exact payload; any change requires renewed review.</li>
                </ul>
              </div>

              <div className="rounded-md border border-border bg-surface-2 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-secondary">Approval history</p>
                <p className="mt-1 text-secondary">
                  Requested by {selected.requestedBy} on {formatDateTime(selected.requestedAt)}.
                  No decisions recorded yet.
                </p>
              </div>

              <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-warning">
                Execution is disabled in this release. Approving here would queue a validated
                EC2 stop/start action once the execution worker is enabled.
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="ghost" size="sm">Close</Button>
              </DialogClose>
              <Button variant="critical" size="sm" disabled>Reject</Button>
              <Button variant="success" size="sm" disabled>Approve &amp; queue</Button>
            </DialogFooter>
          </DialogContent>
        ) : null}
      </Dialog>
    </>
  );
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-secondary">{label}</span>
      <span className="text-right text-primary">{value}</span>
    </div>
  );
}
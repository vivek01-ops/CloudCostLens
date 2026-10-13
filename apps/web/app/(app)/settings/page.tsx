"use client";

import { DemoBanner } from "@/components/demo-banner";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const members = [
  { name: "Alex Rivera", email: "alex@cloudcostlens.dev", role: "owner" },
  { name: "Sam Okafor", email: "sam@cloudcostlens.dev", role: "approver" },
  { name: "Jordan Lee", email: "jordan@cloudcostlens.dev", role: "finops_analyst" },
  { name: "Priya Nair", email: "priya@cloudcostlens.dev", role: "viewer" },
];

export default function SettingsPage() {
  return (
    <>
      <DemoBanner note="Settings are presented for layout review. Persisting configuration is delivered in later milestones." />
      <PageHeader
        title="Settings"
        description="Manage AWS connections, scan behavior, recommendation thresholds, protection policies, approvals, members, and audit."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>AWS connections</CardTitle>
            <CardDescription>Cross-account roles with temporary credentials only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between rounded-md border border-border bg-surface-2 px-3 py-2">
              <div>
                <div className="text-primary">111122223333 · demo-account</div>
                <div className="text-xs text-secondary">arn:aws:iam::111122223333:role/CloudCostLensReadOnly</div>
              </div>
              <span className="rounded-sm border border-success/40 bg-success/10 px-1.5 py-0.5 text-xs text-success">Connected</span>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" disabled>Verify connection</Button>
              <Button variant="outline" size="sm" disabled>Add account</Button>
            </div>
            <p className="text-xs text-secondary">External IDs are stored encrypted and never displayed or logged.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Enabled regions</CardTitle>
            <CardDescription>Inventory scans cover only these regions.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {["eu-west-1", "us-east-1"].map((r) => (
              <div key={r} className="flex items-center justify-between rounded-md border border-border bg-surface-2 px-3 py-2">
                <span>{r}</span>
                <span className="text-xs text-secondary">enabled</span>
              </div>
            ))}
            <p className="text-xs text-secondary">Add or remove regions per account.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Scan configuration</CardTitle>
            <CardDescription>Schedule and scope of background discovery.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="scan-interval">Discovery interval</Label>
              <Input id="scan-interval" defaultValue="Every 6 hours" disabled />
            </div>
            <div className="space-y-1">
              <Label htmlFor="scan-concurrency">Max concurrency</Label>
              <Input id="scan-concurrency" defaultValue="4" disabled />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recommendation thresholds</CardTitle>
            <CardDescription>Versioned; changing a threshold creates a new config version.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="cpu-avg">Idle CPU average (%)</Label>
              <Input id="cpu-avg" defaultValue="5" disabled />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cpu-p95">Idle CPU p95 (%)</Label>
              <Input id="cpu-p95" defaultValue="15" disabled />
            </div>
            <div className="space-y-1">
              <Label htmlFor="obs-days">Observation window (days)</Label>
              <Input id="obs-days" defaultValue="14" disabled />
            </div>
            <div className="space-y-1">
              <Label htmlFor="min-days">Minimum observation (days)</Label>
              <Input id="min-days" defaultValue="7" disabled />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Protected resources &amp; exclusions</CardTitle>
            <CardDescription>Matching resources never produce actionable findings.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-secondary">
            <p>Example policies:</p>
            <ul className="list-disc space-y-1 pl-4">
              <li>Tag <span className="font-mono text-xs text-primary">business-critical=true</span></li>
              <li>Resource id <span className="font-mono text-xs text-primary">i-0b1c2d3e4f5a6b7c8</span></li>
              <li>Resource type <span className="font-mono text-xs text-primary">rds_cluster</span></li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Approval &amp; notifications</CardTitle>
            <CardDescription>Approval expiry and delivery preferences.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="approval-expiry">Approval expiry (days)</Label>
              <Input id="approval-expiry" defaultValue="14" disabled />
            </div>
            <div className="space-y-1">
              <Label htmlFor="notify">Notify on</Label>
              <Input id="notify" defaultValue="New high-risk findings" disabled />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Organization members &amp; roles</CardTitle>
          <CardDescription>Authorization is enforced server-side; roles are not UI-only.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Member</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((m) => (
                <TableRow key={m.email}>
                  <TableCell className="text-primary">{m.name}</TableCell>
                  <TableCell className="text-secondary">{m.email}</TableCell>
                  <TableCell>
                    <span className="rounded-sm border border-border bg-surface-2 px-1.5 py-0.5 text-xs text-secondary">
                      {m.role}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
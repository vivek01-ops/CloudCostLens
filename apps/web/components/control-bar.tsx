"use client";

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface ControlBarProps {
  accounts: { id: string; label: string }[];
  regions: string[];
  showDateRange?: boolean;
  lastRefreshed?: string;
  onRefresh?: () => void;
}

/**
 * Persistent page control bar: account, region and (optionally) date-range selectors,
 * plus freshness and refresh. Filters are intentionally compact and consistent across pages.
 */
export function ControlBar({
  accounts,
  regions,
  showDateRange = false,
  lastRefreshed,
  onRefresh,
}: ControlBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select defaultValue={accounts[0]?.id}>
        <SelectTrigger className="min-w-[190px]" aria-label="AWS account">
          <SelectValue placeholder="Select account" />
        </SelectTrigger>
        <SelectContent>
          {accounts.map((account) => (
            <SelectItem key={account.id} value={account.id}>
              {account.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select defaultValue={regions[0]}>
        <SelectTrigger className="min-w-[140px]" aria-label="Region">
          <SelectValue placeholder="Region" />
        </SelectTrigger>
        <SelectContent>
          {regions.map((region) => (
            <SelectItem key={region} value={region}>
              {region}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {showDateRange ? (
        <Select defaultValue="30d">
          <SelectTrigger className="min-w-[130px]" aria-label="Date range">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7d">Last 7 days</SelectItem>
            <SelectItem value="30d">Last 30 days</SelectItem>
            <SelectItem value="90d">Last 90 days</SelectItem>
            <SelectItem value="12m">Last 12 months</SelectItem>
          </SelectContent>
        </Select>
      ) : null}

      <div className="ml-auto flex items-center gap-3">
        {lastRefreshed ? (
          <span className="text-xs text-secondary">Last refreshed {lastRefreshed}</span>
        ) : null}
        {onRefresh ? (
          <Button variant="secondary" size="sm" onClick={onRefresh}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        ) : null}
      </div>
    </div>
  );
}
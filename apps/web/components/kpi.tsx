import { Info } from "lucide-react";

import type { KpiStat } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const TONE_CLASS: Record<NonNullable<KpiStat["tone"]>, string> = {
  default: "text-primary",
  success: "text-success",
  warning: "text-warning",
  critical: "text-critical",
  accent: "text-accent",
};

/**
 * A compact KPI strip. Deliberately not a grid of giant cards: values are dense,
 * aligned, and scannable, separated by rules rather than heavy containers.
 */
export function KpiStrip({ stats }: { stats: KpiStat[] }) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="grid grid-cols-2 divide-border rounded-lg border border-border bg-surface sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
        {stats.map((stat) => (
          <div key={stat.label} className="border-b border-border px-4 py-3 last:border-b-0 lg:border-b-0">
            <div className="flex items-center gap-1 text-xs text-secondary">
              <span className="truncate">{stat.label}</span>
              {stat.tooltip ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button aria-label={`About ${stat.label}`} className="text-secondary/70 hover:text-secondary">
                      <Info className="h-3 w-3" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>{stat.tooltip}</TooltipContent>
                </Tooltip>
              ) : null}
            </div>
            <div className={cn("mt-1.5 tabular text-xl font-semibold", TONE_CLASS[stat.tone ?? "default"])}>
              {stat.value}
            </div>
            {stat.sub ? <div className="mt-0.5 text-[11px] text-secondary">{stat.sub}</div> : null}
          </div>
        ))}
      </div>
    </TooltipProvider>
  );
}
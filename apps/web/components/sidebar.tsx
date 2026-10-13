"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScanSearch, ShieldAlert } from "lucide-react";

import { BRAND, NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <ScanSearch className="h-5 w-5 text-accent" />
        <span className="text-sm font-semibold tracking-tight text-primary">{BRAND}</span>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2" aria-label="Primary">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                active
                  ? "bg-surface-2 text-primary"
                  : "text-secondary hover:bg-surface hover:text-primary",
              )}
            >
              <Icon className={cn("h-4 w-4", active ? "text-accent" : "text-secondary")} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-2 border-t border-border p-3">
        <Link
          href="/settings"
          className="flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-2 text-xs text-secondary hover:text-primary"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden />
          <span className="flex-1 truncate">111122223333 · eu-west-1</span>
        </Link>
        <div className="flex items-start gap-2 rounded-md px-1 py-1 text-[11px] text-secondary">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 text-warning" />
          <span>Demo session · read-only. No AWS actions are enabled in this release.</span>
        </div>
      </div>
    </aside>
  );
}
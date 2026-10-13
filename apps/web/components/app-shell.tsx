import type { ReactNode } from "react";

import { Sidebar } from "@/components/sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-app">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border px-6">
          <div className="text-xs text-secondary">
            AWS Cloud Cost Intelligence &amp; Optimization
          </div>
          <div className="flex items-center gap-3 text-xs text-secondary">
            <span className="rounded-sm border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-accent">
              Demo environment
            </span>
            <span>Alex Rivera · Owner · Demo Organization</span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1440px] flex-1 space-y-5 px-6 py-5">{children}</main>
      </div>
    </div>
  );
}
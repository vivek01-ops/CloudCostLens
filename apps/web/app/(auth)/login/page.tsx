"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ScanSearch } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-6">
        <div className="mb-6 flex items-center gap-2">
          <ScanSearch className="h-5 w-5 text-accent" />
          <span className="text-sm font-semibold tracking-tight text-primary">CloudCostLens</span>
        </div>

        <h1 className="text-lg font-semibold text-primary">Sign in</h1>
        <p className="mt-1 text-sm text-secondary">
          Authentication is delivered in Milestone 6. This form is a layout placeholder and does
          not authenticate.
        </p>

        <form
          className="mt-5 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            router.push("/overview");
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="email">Work email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
            />
          </div>
          <Button type="submit" className="w-full" size="lg">
            Continue to dashboard
          </Button>
        </form>

        <p className="mt-4 text-[11px] text-secondary">
          The initial owner is created via a secure bootstrap script — there is no default
          administrator account.
        </p>
      </div>
    </div>
  );
}
"use client";

import type { ReactNode } from "react";

import { AuthGuard } from "@/features/auth/components/auth-guard";

import { Sidebar } from "./sidebar";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-slate-50 text-slate-950">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}

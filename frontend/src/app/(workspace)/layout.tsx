import type { ReactNode } from "react";

import { AppShell } from "@/features/workspace/components/app-shell";

type WorkspaceLayoutProps = {
  children: ReactNode;
};

export default function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  return <AppShell>{children}</AppShell>;
}

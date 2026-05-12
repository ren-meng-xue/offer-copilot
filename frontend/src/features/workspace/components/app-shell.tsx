"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { BookOpen, ChevronLeft, ChevronRight } from "lucide-react";

import type { Citation } from "@/lib/stream";
import { cn } from "@/lib/utils";
import { AuthGuard } from "@/features/auth/components/auth-guard";
import { CitationPanel } from "@/features/chat/components/citation-list";

import { Sidebar } from "./sidebar";

type AppShellProps = {
  children: ReactNode;
};

function RightPanel() {
  const [citations, setCitations] = useState<Citation[]>([]);
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(true);
  const prevCitationsLen = useRef(0);
  const pathname = usePathname();

  useEffect(() => {
    setCitations([]);
    setIsPanelCollapsed(true);
    prevCitationsLen.current = 0;
  }, [pathname]);

  useEffect(() => {
    if (citations.length > 0 && prevCitationsLen.current === 0) {
      setIsPanelCollapsed(false);
    }
    prevCitationsLen.current = citations.length;
  }, [citations.length]);

  useEffect(() => {
    const handler = (event: Event) => {
      const customEvent = event as CustomEvent<Citation[]>;
      setCitations(customEvent.detail);
    };
    window.addEventListener("active-citations-updated", handler);
    return () => window.removeEventListener("active-citations-updated", handler);
  }, []);

  return (
    <aside
      className={cn(
        "hidden shrink-0 flex-col border-l border-[rgba(148,163,184,0.24)] bg-[#fafafa] dark:border-[rgba(51,65,85,0.60)] dark:bg-[#212121] lg:flex",
        "transition-[width] duration-200 ease-in-out",
        isPanelCollapsed ? "w-10" : "w-72",
      )}
    >
      {isPanelCollapsed ? (
        <div className="flex flex-col items-center gap-3 pt-4">
          <button
            onClick={() => setIsPanelCollapsed(false)}
            className="flex size-7 items-center justify-center rounded-md text-[#64748b] transition-colors hover:bg-[#e2e8f0] hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-[#3a3a3a] dark:hover:text-[#ececec]"
            title="展开引用面板"
          >
            <ChevronLeft className="size-4" />
          </button>
          {citations.length > 0 && (
            <span className="size-1.5 rounded-full bg-[#2f6df6] dark:bg-[#4f8ef7]" />
          )}
        </div>
      ) : (
        <>
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-[rgba(148,163,184,0.24)] px-4 dark:border-[rgba(51,65,85,0.60)]">
            <h3 className="text-sm font-semibold text-[#0f172a] dark:text-[#ececec]">
              引用来源
            </h3>
            <button
              onClick={() => setIsPanelCollapsed(true)}
              className="flex size-7 items-center justify-center rounded-md text-[#64748b] transition-colors hover:bg-[#e2e8f0] hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-[#3a3a3a] dark:hover:text-[#ececec]"
              title="折叠引用面板"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
          {citations.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4">
              <BookOpen className="size-8 text-[#64748b] dark:text-[#8e8ea0]" />
              <p className="text-sm text-[#64748b] dark:text-[#8e8ea0]">暂无引用</p>
            </div>
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <CitationPanel citations={citations} />
            </div>
          )}
        </>
      )}
    </aside>
  );
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const showRightPanel = pathname.startsWith("/chat");

  return (
    <AuthGuard>
      <div className="flex h-screen bg-[#fafafa] text-[#0f172a] dark:bg-[#212121] dark:text-[#ececec]">
        <Sidebar />
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {children}
        </main>
        {showRightPanel && <RightPanel />}
      </div>
    </AuthGuard>
  );
}

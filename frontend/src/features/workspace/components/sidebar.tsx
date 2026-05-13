"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Database, MessageSquare, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import { ConversationList } from "@/features/chat/components/conversation-list";
import {
  deleteConversation,
  listConversations,
  type ConversationListItem,
} from "@/services/qa";

import { UserMenu } from "./user-menu";

const navItems = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/knowledge", label: "Knowledge", icon: Database },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("sidebar-collapsed") === "true";
  });

  const activeConversationId = pathname.startsWith("/chat/")
    ? pathname.slice(6)
    : undefined;

  const isChatRoute = pathname.startsWith("/chat");
  const isKnowledgeRoute = pathname.startsWith("/knowledge");
  const activeSection = isChatRoute ? "/chat" : isKnowledgeRoute ? "/knowledge" : null;

  useEffect(() => {
    let isMounted = true;

    const loadConversations = async () => {
      try {
        const result = await listConversations();
        if (isMounted) {
          setConversations(result.filter((c) => Boolean(c.title?.trim())));
        }
      } catch {
        // keep current list on error
      }
    };

    void loadConversations();

    const handleConversationCreated = () => void loadConversations();
    window.addEventListener("conversation-created", handleConversationCreated);

    return () => {
      isMounted = false;
      window.removeEventListener("conversation-created", handleConversationCreated);
    };
  }, []);

  const handleNewConversation = () => {
    router.push("/chat");
  };

  const handleDeleteConversation = async (targetConversationId: string) => {
    try {
      setDeletingConversationId(targetConversationId);
      await deleteConversation(targetConversationId);
      setConversations((current) =>
        current.filter((c) => c.conv_id !== targetConversationId),
      );
      if (activeConversationId === targetConversationId) {
        router.push("/chat");
      }
    } finally {
      setDeletingConversationId(null);
    }
  };

  const toggleCollapsed = () => {
    const next = !isCollapsed;
    setIsCollapsed(next);
    localStorage.setItem("sidebar-collapsed", String(next));
  };

  return (
    <aside
      className={cn(
        "relative hidden shrink-0 bg-[#f2f2f2] dark:bg-[#171717] lg:flex lg:flex-col",
        "transition-[width] duration-200 ease-in-out",
        isCollapsed ? "w-[52px]" : "w-60",
      )}
    >
      {/* 顶部：Logo + 标题 */}
      <div
        className={cn(
          "flex h-14 shrink-0 items-center gap-2",
          isCollapsed ? "justify-center px-0" : "px-4",
        )}
      >
        <Image
          src="/doc-assistant-icon.svg"
          alt="文档助手图标"
          width={28}
          height={28}
          className="shrink-0 rounded-md"
        />
        {!isCollapsed && (
          <Link
            href="/chat"
            className="truncate text-sm font-semibold text-[#0f172a] dark:text-[#ececec]"
          >
            你的文档助手
          </Link>
        )}
      </div>

      {/* 中部：路由对应内容（折叠时隐藏） */}
      {!isCollapsed ? (
        <div className="flex min-h-0 flex-1 flex-col">
          {isChatRoute ? (
            <ConversationList
              conversations={conversations}
              activeConversationId={activeConversationId}
              onNewConversation={handleNewConversation}
              onDeleteConversation={handleDeleteConversation}
              deletingConversationId={deletingConversationId}
            />
          ) : isKnowledgeRoute ? (
            <div className="px-3 py-2">
              <p className="px-2 text-xs font-medium text-[#64748b] dark:text-[#8e8ea0]">
                知识库
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex-1" />
      )}

      {/* 底部：导航 + 折叠按钮 + UserMenu + ThemeToggle */}
      <div className="shrink-0 border-t border-[rgba(148,163,184,0.24)] p-2 dark:border-[rgba(51,65,85,0.60)]">
        <div className="flex flex-col gap-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "group/nav relative flex h-9 items-center rounded-lg px-3 text-sm transition-colors",
                  isCollapsed ? "justify-center" : "gap-3",
                  isActive
                    ? "bg-white font-medium text-[#0f172a] shadow-sm dark:bg-[#2f2f2f] dark:text-[#ececec]"
                    : "text-[#64748b] hover:bg-white/60 hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-white/10 dark:hover:text-[#ececec]",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                {!isCollapsed && <span>{item.label}</span>}
                {isCollapsed && (
                  <span className="pointer-events-none absolute left-full top-1/2 z-30 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-950 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-sm transition-opacity group-hover/nav:opacity-100 dark:bg-[#ececec] dark:text-[#212121]">
                    {item.label}
                  </span>
                )}
              </Link>
            );
          })}
        </div>

        <div className="mt-1 flex flex-col gap-0.5 border-t border-[rgba(148,163,184,0.24)] pt-1 dark:border-[rgba(51,65,85,0.60)]">
          {/* 折叠/展开切换按钮 */}
          <button
            type="button"
            onClick={toggleCollapsed}
            title={isCollapsed ? "展开侧边栏" : "收起侧边栏"}
            className={cn(
              "group/collapse relative flex h-9 w-full items-center rounded-lg px-3 text-sm text-[#64748b] transition-colors hover:bg-white/60 hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-white/10 dark:hover:text-[#ececec]",
              isCollapsed ? "justify-center" : "gap-3",
            )}
          >
            {isCollapsed ? (
              <PanelLeftOpen className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="size-4 shrink-0" aria-hidden="true" />
            )}
            {!isCollapsed && <span>收起</span>}
            {isCollapsed && (
              <span className="pointer-events-none absolute left-full top-1/2 z-30 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-950 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-sm transition-opacity group-hover/collapse:opacity-100 dark:bg-[#ececec] dark:text-[#212121]">
                展开侧边栏
              </span>
            )}
          </button>

          <UserMenu isCollapsed={isCollapsed} />
        </div>
      </div>
    </aside>
  );
}

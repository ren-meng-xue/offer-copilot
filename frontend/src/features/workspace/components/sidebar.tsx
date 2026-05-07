"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, MessageSquare, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { UserMenu } from "./user-menu";

const navItems = [
  {
    href: "/chat",
    label: "Chat",
    icon: MessageSquare,
  },
  {
    href: "/knowledge",
    label: "Knowledge",
    icon: Database,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isHeaderActive, setIsHeaderActive] = useState(false);

  return (
    <aside
      className={cn(
        "hidden min-h-screen shrink-0 border-r border-slate-200 bg-white transition-[width] duration-200 lg:flex lg:flex-col",
        isCollapsed ? "w-16" : "w-64",
      )}
    >
      <div
        className={cn(
          "relative flex h-14 items-center border-b border-slate-200 px-3",
          isCollapsed ? "justify-center" : "justify-between",
        )}
        onMouseEnter={() => setIsHeaderActive(true)}
        onMouseLeave={() => setIsHeaderActive(false)}
        onFocus={() => setIsHeaderActive(true)}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) {
            setIsHeaderActive(false);
          }
        }}
      >
        {isCollapsed && isHeaderActive ? null : (
          <Link
            href="/chat"
            className={cn(
              "flex min-w-0 items-center gap-2 text-sm font-semibold text-slate-950",
              isCollapsed && "justify-center",
            )}
            title="你的文档助手"
            aria-label="你的文档助手"
          >
            <Image
              src="/doc-assistant-icon.svg"
              alt="文档助手图标"
              width={28}
              height={28}
              className="rounded-md"
            />
            {!isCollapsed ? <span className="truncate">你的文档助手</span> : null}
          </Link>
        )}
        {!isCollapsed || isHeaderActive ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={isCollapsed ? "打开边栏" : "收起侧边栏"}
            title={isCollapsed ? "打开边栏" : "收起侧边栏"}
            onClick={() => setIsCollapsed((value) => !value)}
            className="group/sidebar-toggle relative"
          >
            {isCollapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            {isCollapsed ? (
              <span className="pointer-events-none absolute left-full top-1/2 z-30 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-950 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-sm transition-opacity group-hover/sidebar-toggle:opacity-100 group-focus-visible/sidebar-toggle:opacity-100">
                打开边栏
              </span>
            ) : null}
          </Button>
        ) : null}
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2 py-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "group/nav-item relative flex h-10 items-center gap-3 rounded-md border-l-2 border-transparent px-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400",
                isActive &&
                  "border-l-sky-500 bg-sky-50 text-sky-700 hover:bg-sky-100 hover:text-sky-800",
                isCollapsed && "justify-center px-0",
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {!isCollapsed ? (
                <span className={cn(isActive && "font-semibold")}>{item.label}</span>
              ) : null}
              {isCollapsed ? (
                <span className="pointer-events-none absolute left-full top-1/2 z-30 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-950 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-sm transition-opacity group-hover/nav-item:opacity-100 group-focus-visible/nav-item:opacity-100">
                  {item.label}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-2">
        <UserMenu isCollapsed={isCollapsed} />
      </div>
    </aside>
  );
}

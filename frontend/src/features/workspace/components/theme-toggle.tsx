"use client";

import { Moon, Sun } from "lucide-react";
import { ThemeAnimationType, useModeAnimation } from "react-theme-switch-animation";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ThemeToggleProps {
  isCollapsed?: boolean;
}

export function ThemeToggle({ isCollapsed }: ThemeToggleProps) {
  const { ref, toggleSwitchTheme, isDarkMode } = useModeAnimation({
    animationType: ThemeAnimationType.CIRCLE,
    duration: 600,
  });

  return (
    <Button
      ref={ref}
      type="button"
      variant="ghost"
      size="icon"
      aria-label={isDarkMode ? "切换亮色模式" : "切换暗色模式"}
      title={isDarkMode ? "切换亮色模式" : "切换暗色模式"}
      onClick={toggleSwitchTheme}
      className={cn(
        "group/theme-toggle relative text-slate-600 hover:bg-slate-100 hover:text-slate-950 dark:text-[#8e8ea0] dark:hover:bg-[#3a3a3a] dark:hover:text-[#ececec]",
        isCollapsed && "w-full justify-center",
      )}
    >
      {isDarkMode ? (
        <Sun className="size-4" aria-hidden="true" />
      ) : (
        <Moon className="size-4" aria-hidden="true" />
      )}
      {isCollapsed ? (
        <span className="pointer-events-none absolute left-full top-1/2 z-30 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-slate-950 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-sm transition-opacity group-hover/theme-toggle:opacity-100 dark:bg-[#ececec] dark:text-[#212121]">
          {isDarkMode ? "切换亮色模式" : "切换暗色模式"}
        </span>
      ) : null}
    </Button>
  );
}

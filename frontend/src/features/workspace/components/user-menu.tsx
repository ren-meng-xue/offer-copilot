"use client";

import { LogOut, UserCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { logout } from "@/services/auth";
import { getCurrentUser, type CurrentUser } from "@/services/users";

type UserMenuProps = {
  isCollapsed?: boolean;
};

export function UserMenu({ isCollapsed = false }: UserMenuProps) {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    let isMounted = true;

    getCurrentUser()
      .then((user) => {
        if (isMounted) {
          setCurrentUser(user);
        }
      })
      .catch(() => {
        if (isMounted) {
          setCurrentUser(null);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const displayName =
    currentUser?.username || currentUser?.email || "已登录用户";

  const handleLogout = async () => {
    if (isLoggingOut) {
      return;
    }

    setIsLoggingOut(true);

    try {
      await logout();
    } catch {
      // 本地会话仍需清理，避免退出接口失败时卡在登录态。
    } finally {
      clearSession();
      router.replace("/auth/login");
    }
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2",
        isCollapsed ? "justify-center" : "justify-between",
      )}
    >
      {!isCollapsed ? (
        <div className="flex min-w-0 items-center gap-2">
          <UserCircle className="size-5 shrink-0 text-slate-500" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">
              {displayName}
            </p>
            {currentUser?.email ? (
              <p className="truncate text-xs text-slate-500">
                {currentUser.email}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="group/user-logout relative">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="退出登录"
          title={`${displayName}，退出登录`}
          disabled={isLoggingOut}
          onClick={handleLogout}
          className="cursor-pointer disabled:cursor-not-allowed"
        >
          <LogOut />
        </Button>
        {isCollapsed ? (
          <span className="pointer-events-none absolute bottom-1/2 left-full z-30 ml-2 translate-y-1/2 whitespace-nowrap rounded-md bg-slate-950 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-sm transition-opacity group-hover/user-logout:opacity-100 group-focus-within/user-logout:opacity-100">
            {displayName}，退出登录
          </span>
        ) : null}
      </div>
    </div>
  );
}

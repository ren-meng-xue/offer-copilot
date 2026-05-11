"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { restoreSession } from "@/lib/session";

type AuthGuardProps = {
  children: ReactNode;
};

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [isChecked, setIsChecked] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const checkAuth = async () => {
      const authorized = await restoreSession();
      if (!isMounted) {
        return;
      }

      setIsAuthorized(authorized);
      setIsChecked(true);

      if (!authorized) {
        router.replace("/auth/login");
      }
    };

    void checkAuth();

    return () => {
      isMounted = false;
    };
  }, [router]);

  if (!isChecked) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-50 text-sm text-slate-500">
        <div className="flex items-center gap-3">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
          <span>正在加载工作区...</span>
        </div>
      </div>
    );
  }

  if (!isAuthorized) {
    return null;
  }

  return <>{children}</>;
}

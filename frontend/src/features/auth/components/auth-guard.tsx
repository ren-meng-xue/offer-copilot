"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { hasStoredSession, restoreSession } from "@/lib/session";

type AuthGuardProps = {
  children: ReactNode;
};

function hasAuthState() {
  return hasStoredSession();
}

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [isChecked, setIsChecked] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const checkAuth = async () => {
      const authorized = hasAuthState() || (await restoreSession());
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
    return <>{children}</>;
  }

  if (!isAuthorized) {
    return null;
  }

  return <>{children}</>;
}

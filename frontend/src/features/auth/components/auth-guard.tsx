"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type AuthGuardProps = {
  children: ReactNode;
};

function hasAuthState() {
  if (typeof window === "undefined") {
    return false;
  }

  const token = localStorage.getItem("access_token");
  const currentUser = localStorage.getItem("current_user");

  return Boolean(token && currentUser);
}

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = () => {
      const authorized = hasAuthState();
      setIsAuthorized(authorized);

      if (!authorized) {
        router.replace("/auth/login");
      }
    };

    checkAuth();

    const intervalId = window.setInterval(checkAuth, 1000);
    const handleStorage = () => checkAuth();

    window.addEventListener("storage", handleStorage);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("storage", handleStorage);
    };
  }, [router]);

  if (!isAuthorized) {
    return null;
  }

  return <>{children}</>;
}

"use client";

import { AuthAccessPanel } from "@/features/auth/components/auth-access-panel";

export function LoginForm() {
  return <AuthAccessPanel initialMode="login" />;
}

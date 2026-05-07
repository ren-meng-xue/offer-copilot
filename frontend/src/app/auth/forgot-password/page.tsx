import type { Metadata } from "next";
import { AuthAccessPanel } from "@/features/auth/components/auth-access-panel";

export const metadata: Metadata = {
  title: "忘记密码",
};

export default function ForgotPasswordPage() {
  return <AuthAccessPanel initialMode="forgot" standaloneForgot />;
}

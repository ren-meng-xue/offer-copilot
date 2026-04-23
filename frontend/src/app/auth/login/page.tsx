import type { Metadata } from "next";
import { Sparkles } from "lucide-react";

import { AuthFormHeader } from "@/features/auth/components/auth-form-header";
import { LoginForm } from "@/features/auth/components/login-form";

export const metadata: Metadata = {
  title: "登录",
};

export default function LoginPage() {
  return (
    <section className="space-y-6 lg:space-y-7">
      <AuthFormHeader
        title="欢迎回来"
        description="登录后继续查看你的目标岗位、匹配评分和优化结果。"
        badge={(
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
            <Sparkles className="size-3.5" />
            OfferCopilot Auth
          </span>
        )}
      />

      <LoginForm />
    </section>
  );
}

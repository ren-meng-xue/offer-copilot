import type { Metadata } from "next";
import { Sparkles } from "lucide-react";

import { AuthFormHeader } from "@/features/auth/components/auth-form-header";
import { RegisterForm } from "@/features/auth/components/register-form";

export const metadata: Metadata = {
  title: "注册",
};

export default function RegisterPage() {
  return (
    <section className="space-y-6 lg:space-y-7">
      <AuthFormHeader
        title="创建账号"
        description="创建账号，开始针对目标岗位优化简历并准备面试。"
        badge={(
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
            <Sparkles className="size-3.5" />
            Get Started
          </span>
        )}
      />

      <RegisterForm />
    </section>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Mail, Send, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthFormHeader } from "@/features/auth/components/auth-form-header";

export const metadata: Metadata = {
  title: "忘记密码",
};

export default function ForgotPasswordPage() {
  return (
    <section className="space-y-6 lg:space-y-7">
      <AuthFormHeader
        title="找回密码"
        description="输入你的注册邮箱，我们会向该邮箱发送密码重置指引。"
        badge={(
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
            <Sparkles className="size-3.5" />
            Password Reset
          </span>
        )}
      />

      <div className="rounded-[30px] border border-slate-200/80 bg-white p-7 shadow-[0_30px_80px_-40px_rgba(15,23,42,0.32)] sm:p-8 lg:p-9">
        <form className="space-y-5">
          <div className="space-y-2.5">
            <Label htmlFor="email" className="text-sm font-medium text-slate-800">
              注册邮箱
            </Label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-sm shadow-sm focus-visible:border-slate-900 focus-visible:ring-slate-900/10"
              />
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-500">
            当前先提供前端页面占位，后续再接入发送重置邮件的后端能力。
          </div>

          <Button
            type="submit"
            size="lg"
            className="h-12 w-full rounded-xl bg-slate-950 text-white hover:bg-slate-800"
          >
            发送重置指引
            <Send className="size-4" />
          </Button>
        </form>

        <div className="mt-6 border-t border-slate-100 pt-5 text-center text-sm text-slate-500">
          <Link
            href="/auth/login"
            className="inline-flex items-center gap-1 font-medium text-slate-900 underline-offset-4 hover:underline"
          >
            <ArrowLeft className="size-4" />
            返回登录
          </Link>
        </div>
      </div>
    </section>
  );
}

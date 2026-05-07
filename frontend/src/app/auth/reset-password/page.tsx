"use client";

import { Suspense } from "react";
import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, CheckCircle2, KeyRound, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/http";
import { resetPassword } from "@/services/auth";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const token = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    if (!token) {
      setError("重置链接无效，请重新发起找回密码");
      return;
    }

    if (newPassword.length < 8) {
      setError("新密码至少需要 8 位");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    setError("");
    setIsSubmitting(true);

    try {
      await resetPassword({
        token,
        new_password: newPassword,
      });
      setIsSubmitting(false);
      setIsSuccess(true);
      window.setTimeout(() => {
        router.push("/auth/login");
      }, 1200);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("重置失败，请稍后重试");
      }
      setIsSubmitting(false);
    }
  }

  return (
    <section className="space-y-6 lg:space-y-7">
      <div className="space-y-5 text-center sm:space-y-6">
        <div className="flex justify-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
            <ShieldCheck className="size-3.5" />
            Reset Password
          </span>
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-[2.2rem]">
            设置新密码
          </h1>
          <p className="mx-auto max-w-[44ch] text-sm leading-6 text-slate-500">
            请输入新的登录密码，设置完成后即可返回登录页使用新密码继续访问。
          </p>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[640px] rounded-[28px] border border-slate-200/80 bg-white p-8 shadow-[0_30px_80px_-40px_rgba(15,23,42,0.32)] sm:p-9 md:p-10">
        {isSuccess ? (
          <div className="space-y-5">
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm leading-6 text-emerald-700">
              <div className="flex items-center gap-2 font-medium text-emerald-800">
                <CheckCircle2 className="size-4" />
                密码已更新
              </div>
              <p className="mt-2">
                你的登录密码已经重置完成，现在可以返回登录页继续登录。
              </p>
            </div>

            <Link
              href="/auth/login"
              className="inline-flex h-12 w-full items-center justify-center gap-1.5 rounded-xl bg-slate-950 px-4 text-sm font-medium text-white transition-colors hover:bg-slate-800"
            >
              返回登录
              <ArrowLeft className="size-4" />
            </Link>
          </div>
        ) : (
          <form className="space-y-5" onSubmit={handleSubmit}>
            {email ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm leading-6 text-slate-600">
                正在为账号 <span className="font-medium text-slate-900">{email}</span> 设置新密码。
              </div>
            ) : null}

            <div className="space-y-2.5">
              <Label htmlFor="new-password" className="text-sm font-medium text-slate-800">
                新密码
              </Label>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="请输入新密码"
                  className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-sm shadow-sm focus-visible:border-slate-900 focus-visible:ring-slate-900/10"
                />
              </div>
            </div>

            <div className="space-y-2.5">
              <Label htmlFor="confirm-password" className="text-sm font-medium text-slate-800">
                确认新密码
              </Label>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="再次输入新密码"
                  className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-sm shadow-sm focus-visible:border-slate-900 focus-visible:ring-slate-900/10"
                />
              </div>
            </div>

            {error ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
                {error}
              </div>
            ) : null}

            <Button
              type="submit"
              size="lg"
              disabled={isSubmitting}
              className="h-12 w-full rounded-xl bg-slate-950 text-white hover:bg-slate-800"
            >
              {isSubmitting ? "提交中..." : "确认重置密码"}
            </Button>

            <div className="border-t border-slate-100 pt-5 text-center text-sm text-slate-500">
              <Link
                href="/auth/login"
                className="inline-flex items-center gap-1 font-medium text-slate-900 underline-offset-4 hover:underline"
              >
                <ArrowLeft className="size-4" />
                返回登录
              </Link>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

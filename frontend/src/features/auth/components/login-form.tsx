"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/http";
import { PasswordInput } from "@/features/auth/components/password-input";
import { login } from "@/services/auth";
import { getCurrentUser } from "@/services/users";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    setError("");
    setSuccess("");
    setIsSubmitting(true);

    try {
      const result = await login({
        email,
        password,
      });

      localStorage.setItem("access_token", result.access_token);
      localStorage.setItem("token_type", result.token_type);

      const currentUser = await getCurrentUser(result.access_token);
      localStorage.setItem("current_user", JSON.stringify(currentUser));

      setSuccess("登录成功，正在进入首页...");
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("登录失败，请稍后重试");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-[30px] border border-slate-200/80 bg-white p-7 shadow-[0_30px_80px_-40px_rgba(15,23,42,0.32)] sm:p-8 lg:p-9">
      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2.5">
          <Label htmlFor="email" className="text-sm font-medium text-slate-800">
            邮箱
          </Label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
              disabled={isSubmitting}
              className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-sm shadow-sm focus-visible:border-slate-900 focus-visible:ring-slate-900/10"
            />
          </div>
        </div>

        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="password" className="text-sm font-medium text-slate-800">
              密码
            </Label>
            <Link
              href="/auth/forgot-password"
              className="text-xs font-medium text-slate-500 transition-colors hover:text-slate-900"
            >
              忘记密码
            </Link>
          </div>
          <PasswordInput
            id="password"
            placeholder="请输入密码"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            disabled={isSubmitting}
          />
        </div>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {success}
          </div>
        ) : null}

        <Button
          type="submit"
          size="lg"
          disabled={isSubmitting}
          className="h-12 w-full rounded-xl bg-slate-950 text-white hover:bg-slate-800"
        >
          {isSubmitting ? "登录中..." : "登录"}
          <ArrowRight className="size-4" />
        </Button>
      </form>

      <div className="mt-6 border-t border-slate-100 pt-5 text-center text-sm text-slate-500">
        还没有账号？
        <Link
          href="/auth/register"
          className="ml-1 font-medium text-slate-900 underline-offset-4 hover:underline"
        >
          立即注册
        </Link>
      </div>
    </div>
  );
}

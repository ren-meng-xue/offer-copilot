"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, BriefcaseBusiness, Mail, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/http";
import { PasswordInput } from "@/features/auth/components/password-input";
import { register } from "@/services/auth";

export function RegisterForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [currentIdentity, setCurrentIdentity] = useState("");
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
      await register({
        username,
        current_identity: currentIdentity || undefined,
        email,
        password,
      });

      setSuccess("注册成功，正在进入登录页...");
      router.push("/auth/login");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("注册失败，请稍后重试");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="space-y-6 lg:space-y-7">
      <div className="space-y-5 text-center sm:space-y-6">
        <div className="flex justify-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
            <ArrowRight className="size-3.5" />
            Get Started
          </span>
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-[2.2rem]">
            创建账号
          </h1>
          <p className="mx-auto max-w-[40ch] text-sm leading-6 text-slate-500">
            创建账号，导入你的技术文档，让文档助手基于真实内容回答问题。
          </p>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[640px] rounded-[28px] border border-slate-200/80 bg-white p-8 shadow-[0_30px_80px_-40px_rgba(15,23,42,0.32)] sm:p-9 md:p-10">
        <form className="space-y-5" onSubmit={handleSubmit}>
          <div className="space-y-2.5">
            <Label htmlFor="username" className="text-sm font-medium text-slate-800">
              用户名
            </Label>
            <div className="relative">
              <UserRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                placeholder="你的昵称"
                disabled={isSubmitting}
                className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-sm shadow-sm focus-visible:border-slate-900 focus-visible:ring-slate-900/10"
              />
            </div>
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="status" className="text-sm font-medium text-slate-800">
              当前角色
            </Label>
            <div className="relative">
              <BriefcaseBusiness className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                id="status"
                type="text"
                value={currentIdentity}
                onChange={(event) => setCurrentIdentity(event.target.value)}
                placeholder="如：后端开发者"
                disabled={isSubmitting}
                className="h-12 rounded-xl border-slate-200 bg-white pl-10 text-sm shadow-sm focus-visible:border-slate-900 focus-visible:ring-slate-900/10"
              />
            </div>
          </div>

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
            <Label htmlFor="password" className="text-sm font-medium text-slate-800">
              密码
            </Label>
            <PasswordInput
              id="password"
              placeholder="至少 8 位"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
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
            {isSubmitting ? "注册中..." : "创建账号"}
            <ArrowRight className="size-4" />
          </Button>
        </form>

        <div className="mt-6 border-t border-slate-100 pt-5 text-center text-sm text-slate-500">
          已经有账号？
          <Link
            href="/auth/login"
            className="ml-1 font-medium text-slate-900 underline-offset-4 hover:underline"
          >
            去登录
          </Link>
        </div>
      </div>
    </section>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, BriefcaseBusiness, Mail, UserRound } from "lucide-react";

import { ApiError } from "@/lib/http";
import { PasswordInput } from "@/features/auth/components/password-input";
import { register } from "@/services/auth";

const inputClass =
  "h-12 w-full rounded-xl border border-slate-200 bg-white pl-10 text-sm text-slate-900 shadow-sm outline-none placeholder:text-slate-400 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-[#212121] dark:text-[#ececec] dark:placeholder:text-[#8e8ea0] dark:focus:border-slate-600 dark:focus:ring-slate-600/10";

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
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 dark:border-slate-700 dark:bg-[#2f2f2f] dark:text-[#8e8ea0]">
            <ArrowRight className="size-3.5" />
            Get Started
          </span>
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-[#ececec] sm:text-[2.2rem]">
            创建账号
          </h1>
          <p className="mx-auto max-w-[40ch] text-sm leading-6 text-slate-500 dark:text-[#8e8ea0]">
            创建账号，导入你的技术文档，让文档助手基于真实内容回答问题。
          </p>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[640px] rounded-[28px] border border-slate-200/80 bg-white p-8 shadow-[0_30px_80px_-40px_rgba(15,23,42,0.32)] dark:border-slate-700 dark:bg-[#2f2f2f] dark:shadow-none sm:p-9 md:p-10">
        <form className="space-y-5" onSubmit={handleSubmit}>
          <div className="space-y-2.5">
            <label htmlFor="username" className="block text-sm font-medium text-slate-800 dark:text-slate-200">
              用户名
            </label>
            <div className="relative">
              <UserRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
              <input
                id="username"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                placeholder="你的昵称"
                disabled={isSubmitting}
                className={inputClass}
              />
            </div>
          </div>

          <div className="space-y-2.5">
            <label htmlFor="status" className="block text-sm font-medium text-slate-800 dark:text-slate-200">
              当前角色
            </label>
            <div className="relative">
              <BriefcaseBusiness className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
              <input
                id="status"
                type="text"
                value={currentIdentity}
                onChange={(event) => setCurrentIdentity(event.target.value)}
                placeholder="如：后端开发者"
                disabled={isSubmitting}
                className={inputClass}
              />
            </div>
          </div>

          <div className="space-y-2.5">
            <label htmlFor="email" className="block text-sm font-medium text-slate-800 dark:text-slate-200">
              邮箱
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                placeholder="you@example.com"
                disabled={isSubmitting}
                className={inputClass}
              />
            </div>
          </div>

          <div className="space-y-2.5">
            <label htmlFor="password" className="block text-sm font-medium text-slate-800 dark:text-slate-200">
              密码
            </label>
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
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-800/50 dark:bg-rose-900/20 dark:text-rose-400">
              {error}
              {error === "邮箱已存在" && (
                <Link
                  href="/auth/login"
                  className="ml-2 font-medium underline underline-offset-4 hover:text-rose-700 dark:hover:text-rose-300"
                >
                  直接登录
                </Link>
              )}
            </div>
          ) : null}

          {success ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-800/50 dark:bg-emerald-900/20 dark:text-emerald-400">
              {success}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-slate-950 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-[#ececec] dark:text-[#212121] dark:hover:bg-white"
          >
            {isSubmitting ? "注册中..." : "创建账号"}
            <ArrowRight className="size-4" />
          </button>
        </form>

        <div className="mt-6 border-t border-slate-100 pt-5 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-[#8e8ea0]">
          已经有账号？
          <Link
            href="/auth/login"
            className="ml-1 font-medium text-slate-900 underline-offset-4 hover:underline dark:text-[#ececec]"
          >
            去登录
          </Link>
        </div>
      </div>
    </section>
  );
}

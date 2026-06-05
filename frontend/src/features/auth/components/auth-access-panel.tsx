"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Mail, Send, Sparkles } from "lucide-react";

import { ApiError } from "@/lib/http";
import { setSessionTokens, setStoredCurrentUser } from "@/lib/session";
import { PasswordInput } from "@/features/auth/components/password-input";
import { forgotPassword, login } from "@/services/auth";
import { getCurrentUser } from "@/services/users";

type AuthMode = "login" | "forgot" | "forgot-success";

type AuthAccessPanelProps = {
  initialMode?: Exclude<AuthMode, "forgot-success">;
  standaloneForgot?: boolean;
};

const inputClass =
  "h-12 w-full rounded-xl border border-slate-200 bg-white pl-10 text-sm text-slate-900 shadow-sm outline-none placeholder:text-slate-400 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-[#212121] dark:text-[#ececec] dark:placeholder:text-[#8e8ea0] dark:focus:border-slate-600 dark:focus:ring-slate-600/10";

const productionLoginCredentials = {
  email: "admin@qq.com",
  password: "admin123",
};

const developmentLoginCredentials = {
  email: "917596600@qq.com",
  password: "qq1.2.3",
};

const defaultLoginCredentials =
  process.env.NODE_ENV === "production"
    ? productionLoginCredentials
    : developmentLoginCredentials;

export function AuthAccessPanel({
  initialMode = "login",
  standaloneForgot = false,
}: AuthAccessPanelProps) {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState(defaultLoginCredentials.email);
  const [password, setPassword] = useState(defaultLoginCredentials.password);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleLoginSubmit(event: React.FormEvent<HTMLFormElement>) {
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

      setSessionTokens({
        accessToken: result.access_token,
        tokenType: result.token_type,
        expiresIn: result.expires_in,
      });

      const currentUser = await getCurrentUser();
      setStoredCurrentUser(currentUser);

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

  async function handleForgotSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("请输入你的账号邮箱");
      return;
    }

    setError("");
    setSuccess("");
    setIsSubmitting(true);

    try {
      await forgotPassword({
        email: trimmedEmail,
      });
      setEmail(trimmedEmail);
      setMode("forgot-success");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("发送失败，请稍后重试");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function showForgotForm() {
    setError("");
    setSuccess("");
    setMode("forgot");
  }

  function showLoginForm() {
    setError("");
    setSuccess("");
    setMode("login");

    if (standaloneForgot) {
      router.push("/auth/login");
    }
  }

  function showForgotInputAgain() {
    setError("");
    setSuccess("");
    setMode("forgot");
  }

  const header = getHeader(mode);

  return (
    <section className="space-y-6 lg:space-y-7">
      <div className="space-y-5 text-center sm:space-y-6">
        <div className="flex justify-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 dark:border-slate-700 dark:bg-[#2f2f2f] dark:text-[#8e8ea0]">
            <Sparkles className="size-3.5" />
            {header.badge}
          </span>
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-[#ececec] sm:text-[2.2rem]">
            {header.title}
          </h1>
          <p className="mx-auto max-w-[40ch] text-sm leading-6 text-slate-500 dark:text-[#8e8ea0]">
            {header.description}
          </p>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[640px] rounded-[28px] border border-slate-200/80 bg-white p-8 shadow-[0_30px_80px_-40px_rgba(15,23,42,0.32)] dark:border-slate-700 dark:bg-[#2f2f2f] dark:shadow-none sm:p-9 md:p-10">
        {mode === "login" ? (
          <form className="space-y-5" onSubmit={handleLoginSubmit}>
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
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="text-sm font-medium text-slate-800 dark:text-slate-200">
                  密码
                </label>
                <button
                  type="button"
                  onClick={showForgotForm}
                  className="text-xs font-medium text-slate-500 transition-colors hover:text-slate-900 dark:text-[#8e8ea0] dark:hover:text-[#ececec]"
                >
                  忘记密码？
                </button>
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
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-800/50 dark:bg-rose-900/20 dark:text-rose-400">
                {error}
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
              {isSubmitting ? "登录中..." : "登录"}
              <ArrowRight className="size-4" />
            </button>
          </form>
        ) : null}

        {mode === "forgot" ? (
          <form className="space-y-5" onSubmit={handleForgotSubmit}>
            <div className="space-y-2.5">
              <label htmlFor="forgot-email" className="block text-sm font-medium text-slate-800 dark:text-slate-200">
                账号邮箱
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
                <input
                  id="forgot-email"
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

            {error ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-800/50 dark:bg-rose-900/20 dark:text-rose-400">
                {error}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-slate-950 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-[#ececec] dark:text-[#212121] dark:hover:bg-white"
            >
              {isSubmitting ? "发送中..." : "发送重置链接"}
              <Send className="size-4" />
            </button>

            <button
              type="button"
              onClick={showLoginForm}
              className="inline-flex w-full items-center justify-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-slate-900 dark:text-[#8e8ea0] dark:hover:text-[#ececec]"
            >
              <ArrowLeft className="size-4" />
              返回登录
            </button>
          </form>
        ) : null}

        {mode === "forgot-success" ? (
          <div className="space-y-5">
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 dark:border-emerald-800/50 dark:bg-emerald-900/20">
              <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">请查收邮箱</p>
              <p className="mt-2 text-sm leading-6 text-emerald-700 dark:text-emerald-400">
                如果邮箱 <span className="font-semibold">{email}</span> 已注册，我们已经发送了密码重置指引。
              </p>
            </div>

            <button
              type="button"
              onClick={showLoginForm}
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-slate-950 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-[#ececec] dark:text-[#212121] dark:hover:bg-white"
            >
              返回登录
              <ArrowLeft className="size-4" />
            </button>

            <button
              type="button"
              onClick={showForgotInputAgain}
              className="w-full text-sm font-medium text-slate-500 transition-colors hover:text-slate-900 dark:text-[#8e8ea0] dark:hover:text-[#ececec]"
            >
              重新填写邮箱
            </button>
          </div>
        ) : null}

        {mode === "login" ? (
          <div className="mt-6 border-t border-slate-100 pt-5 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-[#8e8ea0]">
            还没有账号？
            <Link
              href="/auth/register"
              className="ml-1 font-medium text-slate-900 underline-offset-4 hover:underline dark:text-[#ececec]"
            >
              立即注册
            </Link>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function getHeader(mode: AuthMode) {
  if (mode === "forgot") {
    return {
      badge: "Password Reset",
      title: "找回密码",
      description: "输入你的账号邮箱，我们会在当前右侧认证区域内继续完成找回流程。",
    };
  }

  if (mode === "forgot-success") {
    return {
      badge: "Password Reset",
      title: "请查收邮箱",
      description: "我们不会额外跳出一个新页面，找回密码的结果会直接留在右侧可视区域里。",
    };
  }

  return {
    badge: "文档助手",
    title: "欢迎回来",
    description: "",
  };
}

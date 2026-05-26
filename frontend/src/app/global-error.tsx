"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect, startTransition } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  const handleReset = () => {
    startTransition(() => {
      reset();
    });
  };

  return (
    <html lang="zh-CN" className="dark">
      <body className="antialiased selection:bg-indigo-500/30">
        <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-neutral-950 via-neutral-900 to-neutral-950 px-6 text-neutral-100">
          <section className="relative w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-900/50 p-8 text-center backdrop-blur-xl shadow-2xl">
            {/* Background Glows */}
            <div className="absolute -top-10 -left-10 -z-10 h-40 w-40 rounded-full bg-rose-500/10 blur-[60px]" />
            <div className="absolute -bottom-10 -right-10 -z-10 h-40 w-40 rounded-full bg-indigo-500/10 blur-[60px]" />

            {/* Warning Icon */}
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-rose-500/10 text-rose-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="h-8 w-8 animate-pulse"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  pathLength={1}
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                />
              </svg>
            </div>

            <h1 className="mt-6 text-2xl font-bold tracking-tight bg-gradient-to-r from-neutral-50 via-neutral-200 to-neutral-400 bg-clip-text text-transparent">
              系统瞬时异常
            </h1>
            
            <p className="mt-3 text-sm text-neutral-400 leading-relaxed">
              很抱歉，应用程序似乎遇到了问题。错误已被自动捕获并报告给开发团队。您可以尝试一键恢复或刷新页面。
            </p>

            {error.digest && (
              <div className="mt-4 rounded-md bg-neutral-950/60 p-2 text-xs font-mono text-neutral-500 select-all border border-neutral-900">
                ID: {error.digest}
              </div>
            )}

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <button
                onClick={handleReset}
                className="relative inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-indigo-500 to-rose-500 p-[1px] font-semibold text-neutral-100 shadow-lg shadow-indigo-500/10 transition-transform active:scale-[0.98] hover:shadow-indigo-500/25"
              >
                <span className="flex w-full items-center justify-center rounded-xl bg-neutral-950 px-5 py-2.5 transition-colors hover:bg-transparent">
                  一键恢复
                </span>
              </button>

              <button
                onClick={() => window.location.reload()}
                className="inline-flex items-center justify-center rounded-xl border border-neutral-800 bg-neutral-900/60 px-5 py-2.5 font-semibold text-neutral-300 transition-colors hover:bg-neutral-800 hover:text-neutral-100"
              >
                刷新页面
              </button>
            </div>
          </section>
        </main>
      </body>
    </html>
  );
}

import type { ReactNode } from "react";
import Link from "next/link";

import { AuthAnimatedCharacters } from "@/features/auth/components/auth-animated-characters";

type AuthShellProps = {
  children: ReactNode;
};

export function AuthShell({ children }: AuthShellProps) {
  return (
    <div className="grid min-h-screen select-none lg:h-screen lg:grid-cols-[1fr_1fr] lg:overflow-hidden xl:grid-cols-[0.96fr_1.04fr]">
      <AuthAside />
      <section className="flex items-center justify-center bg-white px-6 py-8 sm:px-8 lg:px-10 lg:py-6 xl:px-14">
        <div className="w-full max-w-[520px]">
          <div className="mb-8 flex items-center justify-center lg:hidden">
            <AuthBrand />
          </div>
          {children}
        </div>
      </section>
    </div>
  );
}

function AuthAside() {
  return (
    <aside className="relative hidden overflow-hidden lg:flex lg:flex-col lg:justify-between lg:bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.22),_transparent_28%),linear-gradient(145deg,_#64748b_0%,_#475569_45%,_#0f172a_100%)] lg:px-10 lg:py-8 lg:text-white xl:px-12 xl:py-10">
      <div className="relative z-10">
        <AuthBrand />
      </div>

      <div className="relative z-10 max-w-lg space-y-4">
        <span className="inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs uppercase tracking-[0.24em] text-white/80">
          AI Job Copilot
        </span>
        <div className="space-y-2.5">
          <h2 className="text-[1.85rem] font-semibold leading-tight tracking-tight xl:text-[2.1rem]">
            围绕目标岗位，做更有效的准备。
          </h2>
          <p className="max-w-md text-sm leading-7 text-slate-200">
            OfferCopilot 围绕具体 JD 帮你完成岗位分析、简历匹配、内容优化和面试准备。
          </p>
        </div>
      </div>

      <div className="relative z-10 flex min-h-[180px] items-end justify-center xl:min-h-[220px]">
        <AuthAnimatedCharacters />
      </div>

      <div className="relative z-10 flex flex-wrap gap-6 text-sm text-slate-200/90">
        <span>JD 输入</span>
        <span>匹配评分</span>
        <span>面试准备</span>
      </div>

      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.06)_1px,transparent_1px)] bg-[size:22px_22px] opacity-30" />
      <div className="absolute right-20 top-24 size-56 rounded-full bg-white/10 blur-3xl" />
      <div className="absolute bottom-16 left-12 size-72 rounded-full bg-sky-300/10 blur-3xl" />
    </aside>
  );
}

function AuthBrand() {
  return (
    <Link href="/" className="inline-flex items-center gap-3">
      <div className="flex size-10 items-center justify-center rounded-2xl bg-slate-950 text-sm font-semibold text-white shadow-sm lg:bg-white/12 lg:text-white">
        OP
      </div>
      <div className="space-y-0.5">
        <p className="text-sm font-medium text-slate-950 lg:text-white">
          OfferCopilot
        </p>
        <p className="text-xs text-slate-500 lg:text-slate-200">
          AI 求职副驾
        </p>
      </div>
    </Link>
  );
}

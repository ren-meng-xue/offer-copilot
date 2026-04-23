import type { ReactNode } from "react";

type AuthFormHeaderProps = {
  title: string;
  description: string;
  badge?: ReactNode;
};

export function AuthFormHeader({
  title,
  description,
  badge,
}: AuthFormHeaderProps) {
  return (
    <div className="space-y-5 text-center sm:space-y-6">
      {badge ? (
        <div className="flex justify-center">
          {badge}
        </div>
      ) : null}
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-[2.2rem]">
          {title}
        </h1>
        <p className="mx-auto max-w-[40ch] text-sm leading-6 text-slate-500">
          {description}
        </p>
      </div>
    </div>
  );
}

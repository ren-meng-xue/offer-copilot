"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="zh-CN">
      <body>
        <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
          <section className="max-w-md text-center">
            <h1 className="text-2xl font-semibold">页面出现错误</h1>
            <p className="mt-3 text-sm text-muted-foreground">
              错误已记录，请刷新页面后重试。
            </p>
          </section>
        </main>
      </body>
    </html>
  );
}

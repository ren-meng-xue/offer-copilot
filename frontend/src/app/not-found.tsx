"use client";

import { DotLottieReact } from "@lottiefiles/dotlottie-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-white p-6">
      <DotLottieReact
        src="/error-404.lottie"
        autoplay
        loop
        className="w-full max-w-xl"
      />
    </main>
  );
}

"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

type NoKnowledgePromptProps = {
  message: string;
};

export function NoKnowledgePrompt({ message }: NoKnowledgePromptProps) {
  const router = useRouter();

  return (
    <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-800/50 dark:bg-amber-900/20">
      <p className="text-sm text-amber-900 dark:text-amber-300">{message}</p>
      <Button
        type="button"
        variant="outline"
        className="mt-3 bg-white dark:bg-transparent"
        onClick={() => router.push("/knowledge")}
      >
        去导入文档
      </Button>
    </div>
  );
}

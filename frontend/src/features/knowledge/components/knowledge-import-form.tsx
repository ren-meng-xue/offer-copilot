"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type KnowledgeImportFormProps = {
  isSubmitting: boolean;
  errorMessage: string | null;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  onSubmit: (payload: { source_url: string; name?: string }) => Promise<void>;
};

export function KnowledgeImportForm({
  isSubmitting,
  errorMessage,
  searchQuery,
  onSearchQueryChange,
  onSubmit,
}: KnowledgeImportFormProps) {
  const [sourceUrl, setSourceUrl] = useState("");
  const [name, setName] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedSourceUrl = sourceUrl.trim();
    const trimmedName = name.trim();

    if (!trimmedSourceUrl) {
      setLocalError("请输入文档 URL");
      return;
    }

    setLocalError(null);
    await onSubmit({
      source_url: trimmedSourceUrl,
      ...(trimmedName ? { name: trimmedName } : {}),
    });
    setSourceUrl("");
    setName("");
  };

  const visibleError = localError ?? errorMessage;

  return (
    <form
      onSubmit={handleSubmit}
      className="border-b border-slate-200 bg-white px-4 py-5 sm:px-6 lg:px-8"
    >
      <div className="max-w-5xl space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-950">Knowledge</h1>
            <p className="mt-1 text-sm text-slate-600">
              导入开发者文档 URL，索引完成后即可在 Chat 中引用回答。
            </p>
          </div>
          <div className="w-full max-w-sm space-y-2">
            <Label htmlFor="knowledge-search">搜索知识库</Label>
            <Input
              id="knowledge-search"
              value={searchQuery}
              placeholder="按名称或 URL 搜索"
              onChange={(event) => onSearchQueryChange(event.target.value)}
            />
          </div>
        </div>

        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-[minmax(0,1fr)_220px_auto] md:items-end">
          <div className="space-y-2">
            <Label htmlFor="knowledge-source-url">文档 URL</Label>
            <Input
              id="knowledge-source-url"
              type="url"
              value={sourceUrl}
              disabled={isSubmitting}
              placeholder="https://docs.example.com"
              onChange={(event) => setSourceUrl(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="knowledge-name">名称</Label>
            <Input
              id="knowledge-name"
              value={name}
              disabled={isSubmitting}
              placeholder="可选"
              onChange={(event) => setName(event.target.value)}
            />
          </div>

          <Button
            type="submit"
            size="lg"
            className="h-10 rounded-xl bg-violet-600 px-5 text-white hover:bg-violet-700"
            disabled={isSubmitting}
          >
            {isSubmitting ? "导入中..." : "导入文档"}
          </Button>
        </div>

        {visibleError ? (
          <p role="alert" className="text-sm text-rose-700">
            {visibleError}
          </p>
        ) : null}
      </div>
    </form>
  );
}

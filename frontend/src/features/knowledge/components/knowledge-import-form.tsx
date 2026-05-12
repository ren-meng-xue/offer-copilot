"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import type { ImportPayload } from "../hooks/use-knowledge-base";

type KnowledgeImportFormProps = {
  isSubmitting: boolean;
  errorMessage: string | null;
  onSubmit: (payload: ImportPayload) => Promise<void>;
};

export function KnowledgeImportForm({
  isSubmitting,
  errorMessage,
  onSubmit,
}: KnowledgeImportFormProps) {
  const [importMode, setImportMode] = useState<"url" | "file">("url");
  const [sourceUrl, setSourceUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = name.trim();

    if (importMode === "url") {
      const trimmedSourceUrl = sourceUrl.trim();
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
    } else {
      if (!file) {
        setLocalError("请选择要上传的文件");
        return;
      }
      setLocalError(null);
      await onSubmit({
        file,
        ...(trimmedName ? { name: trimmedName } : {}),
      });
      setFile(null);
    }
    setName("");
  };

  const visibleError = localError ?? errorMessage;

  const inputClass =
    "w-full rounded-xl border border-[rgba(148,163,184,0.32)] bg-white px-3 py-2 text-sm text-[#0f172a] outline-none placeholder:text-[#64748b] focus:border-[#2f6df6]/50 focus:ring-2 focus:ring-[#2f6df6]/20 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-[#212121] dark:text-[#ececec] dark:placeholder:text-[#8e8ea0]";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="inline-flex rounded-full bg-[#f2f2f2] p-1 dark:bg-[#1a1a1a]">
        {(["url", "file"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => setImportMode(mode)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all ${
              importMode === mode
                ? "bg-white text-[#0f172a] shadow-sm dark:bg-[#2f2f2f] dark:text-[#ececec]"
                : "text-[#64748b] hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:text-[#ececec]"
            }`}
          >
            {mode === "url" ? "URL 导入" : "文件上传"}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {importMode === "url" ? (
          <div className="space-y-1">
            <label
              htmlFor="knowledge-source-url"
              className="text-xs font-medium text-[#64748b] dark:text-[#8e8ea0]"
            >
              文档 URL
            </label>
            <input
              key="url-input"
              id="knowledge-source-url"
              type="url"
              className={inputClass}
              value={sourceUrl}
              disabled={isSubmitting}
              placeholder="https://docs.example.com"
              onChange={(e) => setSourceUrl(e.target.value)}
            />
          </div>
        ) : (
          <div className="space-y-1">
            <label
              htmlFor="knowledge-file"
              className="text-xs font-medium text-[#64748b] dark:text-[#8e8ea0]"
            >
              选择文件 (.md, .txt)
            </label>
            <input
              key="file-input"
              id="knowledge-file"
              type="file"
              accept=".md,.txt"
              disabled={isSubmitting}
              className={inputClass}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        )}

        <div className="space-y-1">
          <label
            htmlFor="knowledge-name"
            className="text-xs font-medium text-[#64748b] dark:text-[#8e8ea0]"
          >
            名称（可选）
          </label>
          <input
            id="knowledge-name"
            className={inputClass}
            value={name}
            disabled={isSubmitting}
            placeholder="留空则自动识别标题"
            onChange={(e) => setName(e.target.value)}
          />
        </div>
      </div>

      {visibleError ? (
        <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">
          {visibleError}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-xl bg-[#2f6df6] py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#1d5fe5] disabled:cursor-not-allowed disabled:opacity-50 dark:bg-[#4f8ef7] dark:hover:bg-[#3d7df5]"
      >
        {isSubmitting ? "处理中..." : importMode === "url" ? "导入文档" : "开始上传"}
      </button>
    </form>
  );
}

import { Bot } from "lucide-react";

import type { LocalChatMessage } from "../types";
import { CitationList } from "./citation-list";
import { NoKnowledgePrompt } from "./no-knowledge-prompt";

type MessageBubbleProps = {
  message: LocalChatMessage;
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <article className="flex justify-end" aria-label="用户消息">
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-[#2f6df6] px-4 py-3 text-sm text-white dark:bg-[#4f8ef7]">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </article>
    );
  }

  return (
    <article className="flex gap-3" aria-label="助手消息">
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-[#f2f2f2] dark:bg-[#2f2f2f]">
        <Bot className="size-4 text-[#2f6df6] dark:text-[#4f8ef7]" aria-hidden="true" />
      </div>
      <div className="flex-1 text-sm leading-relaxed text-[#0f172a] dark:text-[#ececec]">
        <p className="whitespace-pre-wrap break-words">
          {message.content ||
            (message.status === "assistant_draft" ? "正在生成..." : "")}
        </p>

        {message.errorCode === "missing_citations" ? (
          <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 p-2 text-rose-800 dark:border-rose-800/50 dark:bg-rose-900/20 dark:text-rose-400">
            未返回引用来源，此答案不能作为可信回答。
          </p>
        ) : null}

        {message.showImportAction ? (
          <NoKnowledgePrompt
            message={message.errorMessage ?? "请先导入相关技术文档。"}
          />
        ) : null}

        <CitationList citations={message.citations} />
      </div>
    </article>
  );
}

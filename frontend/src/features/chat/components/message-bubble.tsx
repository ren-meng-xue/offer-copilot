"use client";

import { useState, useCallback } from "react";
import { Bot, Sparkles, Copy, Check } from "lucide-react";
import { DotLottieReact } from "@lottiefiles/dotlottie-react";

import { Button } from "@/components/ui/button";
import type { LocalChatMessage } from "../types";
import { CitationList } from "./citation-list";
import { NoKnowledgePrompt } from "./no-knowledge-prompt";
import { RagTracePanel } from "./rag-trace-panel";

type MessageBubbleProps = {
  message: LocalChatMessage;
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const isStreaming = message.status === "assistant_draft";

  const handleCopy = useCallback(async () => {
    if (!message.content) return;
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  }, [message.content]);

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
        {isStreaming ? (
          <div className="relative flex size-full items-center justify-center overflow-hidden rounded-full">
            <DotLottieReact src="/loader-cat.lottie" loop autoplay />
          </div>
        ) : (
          <Bot
            className="size-4 text-[#2f6df6] dark:text-[#4f8ef7]"
            aria-hidden="true"
          />
        )}
      </div>
      <div className="flex-1 text-sm leading-relaxed text-[#0f172a] dark:text-[#ececec]">
        <div className="flex flex-col gap-1">
          {isAssistant && isStreaming && !message.content && (
            <div className="flex items-center gap-2 text-[#64748b] dark:text-[#8e8ea0]">
              <Sparkles className="size-3.5 animate-pulse text-[#2f6df6] dark:text-[#4f8ef7]" />
              <div className="flex items-center">
                <span>正在思考</span>
                <span className="flex">
                  <span className="animate-[bounce_1.4s_infinite] delay-0">
                    .
                  </span>
                  <span className="animate-[bounce_1.4s_infinite] delay-200">
                    .
                  </span>
                  <span className="animate-[bounce_1.4s_infinite] delay-400">
                    .
                  </span>
                </span>
              </div>
            </div>
          )}
          <p className="whitespace-pre-wrap break-words">{message.content}</p>

          {isAssistant && !isStreaming && message.content && (
            <div className="mt-1 flex items-center">
              <Button
                variant="ghost"
                size="icon-xs"
                className="text-[#64748b] hover:bg-[#f1f5f9] hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-[#2f2f2f] dark:hover:text-[#ececec]"
                onClick={handleCopy}
                title="复制内容"
              >
                {copied ? (
                  <Check className="size-3.5 text-emerald-500" />
                ) : (
                  <Copy className="size-3.5" />
                )}
              </Button>
              {copied && (
                <span className="ml-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 animate-in fade-in slide-in-from-left-1">
                  已复制
                </span>
              )}
            </div>
          )}
        </div>

        {message.errorCode === "missing_citations" &&
        !isStreaming &&
        message.content &&
        message.content.length > 20 ? (
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

        {message.traceEvents && message.traceEvents.length > 0 && (
          <RagTracePanel events={message.traceEvents} />
        )}
      </div>
    </article>
  );
}

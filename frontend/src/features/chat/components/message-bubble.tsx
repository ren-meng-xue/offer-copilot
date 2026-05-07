import type { LocalChatMessage } from "../types";
import { CitationList } from "./citation-list";
import { NoKnowledgePrompt } from "./no-knowledge-prompt";

type MessageBubbleProps = {
  message: LocalChatMessage;
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <article
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
      aria-label={isUser ? "用户消息" : "助手消息"}
    >
      <div
        className={`max-w-3xl rounded-lg px-4 py-3 text-sm leading-6 ${
          isUser
            ? "bg-slate-950 text-white"
            : "border border-slate-200 bg-white text-slate-900"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">
          {message.content ||
            (message.status === "assistant_draft" ? "正在生成..." : "")}
        </p>

        {message.errorCode === "missing_citations" ? (
          <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 p-2 text-rose-800">
            未返回引用来源，此答案不能作为可信回答。
          </p>
        ) : null}

        {message.showImportAction ? (
          <NoKnowledgePrompt
            message={message.errorMessage ?? "请先导入相关技术文档。"}
          />
        ) : null}

        {!isUser ? <CitationList citations={message.citations} /> : null}
      </div>
    </article>
  );
}

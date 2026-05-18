import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import type { LocalChatMessage } from "../types";
import { MessageBubble } from "./message-bubble";
import { cn } from "@/lib/utils";

type MessageListProps = {
  messages: LocalChatMessage[];
  isLoading: boolean;
  errorMessage: string | null;
  displayName?: string;
};

export function MessageList({
  messages,
  isLoading,
  errorMessage,
  displayName,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  useEffect(() => {
    // 只有在非加载状态且有消息时才滚动
    if (
      !isLoading &&
      messages.length > 0 &&
      bottomRef.current?.scrollIntoView
    ) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, isLoading]);

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } =
      scrollContainerRef.current;
    // 如果距离底部超过 200 像素，显示按钮
    const isFarFromBottom = scrollHeight - scrollTop - clientHeight > 200;
    setShowScrollButton(isFarFromBottom);
  };

  const scrollToBottom = () => {
    if (bottomRef.current?.scrollIntoView) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-[#64748b] dark:text-[#8e8ea0]">
        正在加载会话...
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-800/50 dark:bg-rose-900/20 dark:text-rose-400">
          {errorMessage}
        </div>
      </div>
    );
  }

  if (messages.length === 0) {
    const safeDisplayName = displayName?.trim() || "用户";

    return (
      <div className="flex flex-1 items-start justify-center px-6 pt-[calc(22vh+140px)]">
        <h1 className="text-center text-2xl font-medium tracking-tight text-[#64748b] dark:text-[#8e8ea0]">
          {`你好，${safeDisplayName}。准备好开始了吗？`}
        </h1>
      </div>
    );
  }

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden">
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="no-scrollbar flex-1 space-y-6 overflow-y-auto bg-[#fafafa] px-4 py-6 dark:bg-[#212121] sm:px-6 lg:px-8"
      >
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={bottomRef} className="h-px w-full" />
      </div>

      {/* 回到底部按钮 */}
      <button
        onClick={scrollToBottom}
        className={cn(
          "absolute bottom-2 left-1/2 -translate-x-1/2 flex size-8 items-center justify-center rounded-full border border-[rgba(148,163,184,0.24)] bg-white shadow-md transition-all duration-200 hover:bg-[#f8fafc] dark:border-[rgba(51,65,85,0.60)] dark:bg-[#2f2f2f] dark:hover:bg-[#3a3a3a]",
          showScrollButton
            ? "translate-y-0 opacity-100"
            : "translate-y-4 opacity-0 pointer-events-none",
        )}
        title="回到底部"
      >
        <ChevronDown className="size-4 text-[#64748b] dark:text-[#ececec]" />
      </button>
    </div>
  );
}

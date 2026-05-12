import type { LocalChatMessage } from "../types";
import { MessageBubble } from "./message-bubble";

type MessageListProps = {
  messages: LocalChatMessage[];
  isLoading: boolean;
  errorMessage: string | null;
};

export function MessageList({
  messages,
  isLoading,
  errorMessage,
}: MessageListProps) {
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
    return (
      <div className="flex flex-1 items-start justify-center px-6 pt-[calc(22vh+140px)]">
        <h1 className="text-center text-2xl font-medium tracking-tight text-[#64748b] dark:text-[#8e8ea0]">
          你好，雪宝。准备好开始了吗？
        </h1>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-6 overflow-y-auto bg-[#fafafa] px-4 py-6 dark:bg-[#212121] sm:px-6 lg:px-8">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  );
}

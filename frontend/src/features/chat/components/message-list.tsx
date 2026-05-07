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
      <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
        正在加载会话...
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {errorMessage}
        </div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-start justify-center px-6 pt-[calc(22vh+140px)]">
        <h1 className="text-center text-2xl font-medium tracking-tight text-slate-600">
          你好，雪宝。准备好开始了吗？
        </h1>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50/80 p-4 sm:p-6 lg:p-8">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  );
}

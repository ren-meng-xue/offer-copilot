"use client";

import type { KeyboardEvent } from "react";
import { forwardRef } from "react";
import { ArrowUp } from "lucide-react";

type ChatInputProps = {
  disabled: boolean;
  question: string;
  focusPulseToken: number;
  onQuestionChange: (question: string) => void;
  onSubmit: (question: string) => Promise<void>;
};

export const ChatInput = forwardRef<HTMLInputElement, ChatInputProps>(function ChatInput({
  disabled,
  question,
  onQuestionChange,
  onSubmit,
}: ChatInputProps, ref) {
  const trimmedQuestion = question.trim();
  const canSubmit = Boolean(trimmedQuestion) && !disabled;

  const submitQuestion = async () => {
    if (!canSubmit) {
      return;
    }

    await onSubmit(trimmedQuestion);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      if (event.nativeEvent.isComposing) {
        return;
      }
      event.preventDefault();
      void submitQuestion();
    }
  };

  return (
    <div className="border-t border-[rgba(148,163,184,0.24)] bg-[#fafafa] p-3 dark:border-[rgba(51,65,85,0.60)] dark:bg-[#212121]">
      <div className="mx-auto max-w-4xl">
        <label htmlFor="chat-question" className="sr-only">
          技术问题
        </label>
        <div className="flex items-center gap-2 rounded-2xl border border-[rgba(148,163,184,0.24)] bg-white px-4 py-3 shadow-md focus-within:ring-2 focus-within:ring-[#2f6df6]/20 dark:border-slate-700 dark:bg-[#2f2f2f]">
          <input
            ref={ref}
            id="chat-question"
            name="chat-question-no-history"
            value={question}
            maxLength={1000}
            disabled={disabled}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            placeholder="问我任何文档问题"
            onChange={(event) => onQuestionChange(event.target.value)}
            onKeyDown={handleKeyDown}
            className="min-w-0 flex-1 border-0 bg-transparent text-sm text-[#0f172a] outline-none placeholder:text-[#64748b] disabled:cursor-not-allowed disabled:opacity-50 dark:text-[#ececec] dark:placeholder:text-[#8e8ea0]"
          />
          <button
            type="button"
            aria-label="发送"
            title="发送 (Enter)"
            disabled={!canSubmit}
            onClick={() => void submitQuestion()}
            className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#2f6df6] text-white transition-colors hover:bg-[#1d5fe5] disabled:cursor-not-allowed disabled:opacity-40 dark:bg-[#4f8ef7] dark:hover:bg-[#3d7df5]"
          >
            <ArrowUp className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
});

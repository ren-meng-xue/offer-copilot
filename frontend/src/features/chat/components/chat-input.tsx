"use client";

import type { KeyboardEvent } from "react";
import { forwardRef } from "react";
import { ArrowUp, CornerDownLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

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
  focusPulseToken,
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
      event.preventDefault();
      void submitQuestion();
    }
  };

  return (
    <div className="border-t border-slate-200/80 bg-white/95 p-3 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="mx-auto max-w-4xl">
        <Label htmlFor="chat-question" className="sr-only">
          技术问题
        </Label>
        <div
          className="flex items-center gap-2 rounded-full border border-slate-300 bg-white py-1.5 pl-3 pr-2 shadow-sm focus-within:border-violet-300 focus-within:ring-2 focus-within:ring-violet-100 data-[pulse='true']:animate-pulse"
          data-pulse={focusPulseToken > 0 ? "true" : "false"}
        >
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
            className="h-8 min-w-0 flex-1 border-0 bg-transparent px-2 text-base text-slate-900 outline-none placeholder:text-slate-500 disabled:cursor-not-allowed disabled:text-slate-400"
          />
          <div className="group relative flex items-center">
            <Button
              type="button"
              size="icon"
              aria-label="发送"
              title="发送"
              disabled={!canSubmit}
              className="size-9 rounded-full bg-violet-500 text-white shadow-sm hover:bg-violet-600"
              onClick={() => void submitQuestion()}
            >
              <ArrowUp className="size-5" />
            </Button>
            <span className="pointer-events-none absolute -bottom-7 left-1/2 hidden -translate-x-1/2 items-center gap-1 rounded-md bg-black px-2 py-1 text-xs leading-none whitespace-nowrap text-white group-focus-within:flex group-hover:flex">
              发送提示
              <CornerDownLeft className="size-3.5" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
});

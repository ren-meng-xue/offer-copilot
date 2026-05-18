"use client";

import Link from "next/link";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ConversationListItem } from "@/services/qa";
import { cn } from "@/lib/utils";

type ConversationListProps = {
  conversations: ConversationListItem[];
  activeConversationId?: string;
  onNewConversation: () => void | Promise<void>;
  disableNewConversation?: boolean;
  onDeleteConversation: (conversationId: string) => Promise<void>;
  deletingConversationId?: string | null;
};

export function ConversationList({
  conversations,
  activeConversationId,
  onNewConversation,
  disableNewConversation = false,
  onDeleteConversation,
  deletingConversationId = null,
}: ConversationListProps) {
  const [pendingDeleteConversation, setPendingDeleteConversation] = useState<{
    convId: string;
    title: string;
  } | null>(null);

  return (
    <>
      <div className="px-2 pb-1 pt-2">
        <Button
          type="button"
          variant="ghost"
          className="w-full justify-start gap-2 text-sm font-medium text-[#64748b] hover:bg-white/60 hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-white/10 dark:hover:text-[#ececec]"
          disabled={disableNewConversation}
          onClick={() => void onNewConversation()}
        >
          <Plus className="size-4" />
          新建会话
        </Button>
      </div>
      <nav className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {conversations.length === 0 ? (
          <p className="px-2 py-3 text-xs text-[#64748b] dark:text-[#8e8ea0]">
            发送消息开始第一次对话
          </p>
        ) : (
          conversations.map((conversation) => {
            const isActive = conversation.conv_id === activeConversationId;

            return (
              <div
                key={conversation.conv_id}
                className={cn(
                  "group mb-0.5 flex items-center gap-1 rounded-lg pr-1 text-sm transition-colors",
                  isActive
                    ? "bg-white shadow-sm dark:bg-[#2f2f2f]"
                    : "hover:bg-white/60 dark:hover:bg-white/10",
                )}
              >
                <Link
                  href={`/chat/${conversation.conv_id}`}
                  className={cn(
                    "min-w-0 flex-1 rounded-lg px-3 py-2 text-sm",
                    isActive
                      ? "font-medium text-[#0f172a] dark:text-[#ececec]"
                      : "text-[#64748b] hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:text-[#ececec]",
                  )}
                >
                  <span className="block truncate">{conversation.title}</span>
                </Link>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0 opacity-0 transition-opacity hover:text-rose-600 group-hover:opacity-100 dark:hover:text-rose-400"
                  disabled={deletingConversationId === conversation.conv_id}
                  aria-label={`删除会话 ${conversation.title}`}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setPendingDeleteConversation({
                      convId: conversation.conv_id,
                      title: conversation.title ?? "",
                    });
                  }}
                >
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </Button>
              </div>
            );
          })
        )}
      </nav>
      {pendingDeleteConversation ? (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/30 p-4 backdrop-blur-[1px] dark:bg-black/50">
          <div className="w-full max-w-xs rounded-xl border border-slate-200 bg-white p-4 shadow-lg dark:border-slate-700 dark:bg-[#2f2f2f]">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-[#ececec]">
              删除会话？
            </h3>
            <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-[#8e8ea0]">
              将删除「{pendingDeleteConversation.title}」，删除后不可恢复。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setPendingDeleteConversation(null)}
              >
                取消
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={deletingConversationId === pendingDeleteConversation.convId}
                onClick={async () => {
                  const deletingId = pendingDeleteConversation.convId;
                  await onDeleteConversation(deletingId);
                  setPendingDeleteConversation(null);
                }}
              >
                删除
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

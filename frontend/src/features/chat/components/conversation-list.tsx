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
    <aside className="relative hidden w-72 shrink-0 border-r border-slate-200 bg-white md:flex md:flex-col">
      <div className="border-b border-slate-200 p-3">
        <Button
          type="button"
          className="w-full justify-start bg-violet-100 text-violet-700 shadow-sm hover:bg-violet-200 hover:text-violet-800"
          disabled={disableNewConversation}
          onClick={() => void onNewConversation()}
        >
          <Plus />
          新建会话
        </Button>
      </div>
      <nav className="min-h-0 flex-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <p className="px-2 py-3 text-sm text-slate-500">暂无会话</p>
        ) : (
          conversations.map((conversation) => {
            const isActive = conversation.conv_id === activeConversationId;

            return (
              <div
                key={conversation.conv_id}
                className={cn(
                  "group mb-1 flex items-center gap-1 rounded-md border-l-2 border-transparent pr-1 text-sm text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950",
                  isActive &&
                    "border-l-sky-500 bg-sky-50 text-sky-700 hover:bg-sky-100 hover:text-sky-800",
                )}
              >
                <Link
                  href={`/chat/${conversation.conv_id}`}
                  className={cn(
                    "min-w-0 flex-1 rounded-md px-3 py-2 text-slate-700 hover:text-slate-950",
                    isActive && "font-semibold text-sky-700 hover:text-sky-800",
                  )}
                >
                  <span className="block truncate">
                    {conversation.title}
                  </span>
                </Link>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "size-7 shrink-0 text-slate-400 hover:text-rose-600",
                    isActive && "text-sky-400 hover:text-rose-500",
                  )}
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
                  <Trash2 className="size-4" aria-hidden="true" />
                </Button>
              </div>
            );
          })
        )}
      </nav>
      {pendingDeleteConversation ? (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/30 p-4 backdrop-blur-[1px]">
          <div className="w-full max-w-xs rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
            <h3 className="text-sm font-semibold text-slate-900">删除会话？</h3>
            <p className="mt-1 text-sm leading-6 text-slate-600">
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
    </aside>
  );
}

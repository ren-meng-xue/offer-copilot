"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { getStoredCurrentUser } from "@/lib/session";
import { readSseStream } from "@/lib/stream";
import { listKnowledgeBases } from "@/services/knowledge";
import {
  askConversation,
  createConversation,
  getConversationMessages,
  type MessageItem,
} from "@/services/qa";

import {
  appendAssistantToken,
  attachCitations,
  markAssistantAborted,
  markAssistantDone,
  markAssistantError,
  startOptimisticExchange,
} from "../lib/chat-state";
import type { KnowledgeBaseListItem, LocalChatMessage } from "../types";
import { ChatInput } from "./chat-input";
import { MessageList } from "./message-list";

type DraftConversationCache = {
  conversationId: string;
  knowledgeBaseId: number;
};

type ChatPageProps = {
  conversationId?: string;
};

const messageCacheKey = "__offercopilot_chat_messages_cache__";
const draftConversationCacheKey = "__offercopilot_chat_draft_conversation__";

export function ChatPage({ conversationId }: ChatPageProps) {
  const router = useRouter();
  const draftConversationCache = readDraftConversationCache();
  const [messages, setMessages] = useState<LocalChatMessage[]>(
    () => readMessageCache(conversationId),
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(() =>
    conversationId ? readMessageCache(conversationId).length === 0 : false,
  );
  const [messageError, setMessageError] = useState<string | null>(null);
  const [questionDraft, setQuestionDraft] = useState("");
  const [focusPulseToken] = useState(0);
  const [displayName, setDisplayName] = useState("用户");
  const [readyKnowledgeBases, setReadyKnowledgeBases] = useState<KnowledgeBaseListItem[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<number | null>(
    () => draftConversationCache?.knowledgeBaseId ?? null,
  );
  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeClientIdRef = useRef<string | null>(null);
  const activeConversationIdRef = useRef<string | null>(null);

  const activeKnowledgeBaseId =
    conversationId && draftConversationCache?.conversationId === conversationId
      ? draftConversationCache.knowledgeBaseId
      : selectedKnowledgeBaseId;
  const activeKnowledgeBase = readyKnowledgeBases.find(
    (item) => item.knowledge_base_id === activeKnowledgeBaseId,
  );

  useEffect(() => {
    const user = getStoredCurrentUser();
    const resolvedDisplayName = user?.username?.trim() || user?.email?.trim() || "用户";
    setDisplayName(resolvedDisplayName);
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadKnowledgeBases = async () => {
      try {
        const result = await listKnowledgeBases();
        const readyItems = result.filter((item) => item.status === "done");
        if (!isMounted) {
          return;
        }
        setReadyKnowledgeBases(readyItems);
        setSelectedKnowledgeBaseId((current) => current ?? readyItems[0]?.knowledge_base_id ?? null);
      } catch {
        if (isMounted) {
          setReadyKnowledgeBases([]);
        }
      }
    };

    void loadKnowledgeBases();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setIsLoadingMessages(false);
      setMessageError(null);
      clearMessageCache();
      return;
    }

    let isMounted = true;
    
    const cachedMessages = readMessageCache(conversationId);
    if (cachedMessages.length === 0) {
      setIsLoadingMessages(true);
    }

    const loadMessages = async () => {
      try {
        const result = await getConversationMessages(conversationId);
        const mappedMessages = result.map((message) =>
          toLocalMessage(message, conversationId),
        );

        if (isMounted) {
          setMessages((current) => {
            if (current.length > 0 && mappedMessages.length === 0) {
              return current;
            }

            writeMessageCache(conversationId, mappedMessages);
            return mappedMessages;
          });
          setMessageError(null);

          const lastAiMessage = [...mappedMessages]
            .reverse()
            .find((m) => m.role === "assistant");
          if (lastAiMessage?.citations.length) {
            window.dispatchEvent(
              new CustomEvent("active-citations-updated", {
                detail: lastAiMessage.citations,
              }),
            );
          }
        }
      } catch (error) {
        if (isMounted) {
          setMessageError(
            error instanceof Error ? error.message : "会话加载失败",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingMessages(false);
        }
      }
    };

    void loadMessages();

    return () => {
      isMounted = false;
      if (activeConversationIdRef.current === conversationId) {
        abortControllerRef.current?.abort();
      }
      const clientId = activeClientIdRef.current;

      if (clientId && activeConversationIdRef.current === conversationId) {
        setMessages((current) => markAssistantAborted(current, clientId));
      }
    };
  }, [conversationId]);

  useEffect(() => {
    if (!conversationId && !selectedKnowledgeBaseId) {
      clearDraftConversationCache();
    }
  }, [conversationId, selectedKnowledgeBaseId]);

  useEffect(() => {
    if (!conversationId || conversationId !== draftConversationCache?.conversationId) {
      return;
    }

    const hasKnowledgeBase = readyKnowledgeBases.some(
      (item) => item.knowledge_base_id === draftConversationCache.knowledgeBaseId,
    );

    if (hasKnowledgeBase) {
      clearDraftConversationCache();
    }
  }, [conversationId, draftConversationCache, readyKnowledgeBases]);

  useEffect(() => {
    if (!isLoadingMessages && !isStreaming) {
      inputRef.current?.focus();
    }
  }, [conversationId, isLoadingMessages, isStreaming]);

  const handleSubmit = async (question: string) => {
    if (isStreaming) {
      return;
    }

    let targetConversationId = conversationId;
    const shouldNavigateAfterStream = !conversationId;

    try {
      if (!targetConversationId) {
        if (!selectedKnowledgeBaseId) {
          if (draftConversationCache?.conversationId) {
            clearDraftConversationCache();
          }
          setMessageError("请先导入并完成一个知识库，再开始问答");
          return;
        }
        const conversation = await createConversation(selectedKnowledgeBaseId);
        targetConversationId = conversation.conv_id;
        writeDraftConversationCache({
          conversationId: conversation.conv_id,
          knowledgeBaseId: selectedKnowledgeBaseId,
        });
        window.dispatchEvent(new CustomEvent("conversation-created"));
      }

      if (!targetConversationId) {
        throw new Error("会话创建失败");
      }

      const activeConversationId = targetConversationId;
      const clientId = createClientId();
      const optimisticMessages = startOptimisticExchange([], {
        conversationId: activeConversationId,
        question,
        clientId,
      });
      writeMessageCache(activeConversationId, optimisticMessages);
      setQuestionDraft("");
      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      activeClientIdRef.current = clientId;
      activeConversationIdRef.current = activeConversationId;

      setIsStreaming(true);
      setMessageError(null);
      setMessages(optimisticMessages);

      const response = await askConversation(
        activeConversationId,
        question,
        abortController.signal,
      );

      if (!response.ok) {
        throw new Error("发送失败，请稍后重试");
      }

      await readSseStream(response, (event) => {
        if (activeClientIdRef.current !== clientId) {
          return;
        }

        if (event.type === "token") {
          setMessages((current) =>
            {
              const next = appendAssistantToken(current, clientId, event.content);
              writeMessageCache(activeConversationId, next);
              return next;
            },
          );
        }

        if (event.type === "citations") {
          setMessages((current) =>
            {
              const next = attachCitations(current, clientId, event.data);
              writeMessageCache(activeConversationId, next);
              return next;
            },
          );
          window.dispatchEvent(
            new CustomEvent("active-citations-updated", { detail: event.data }),
          );
        }

        if (event.type === "done") {
          setMessages((current) => {
            const next = markAssistantDone(current, clientId);
            writeMessageCache(activeConversationId, next);
            return next;
          });
        }

        if (event.type === "error") {
          setMessages((current) => {
            const next = markAssistantError(current, clientId, {
              code: event.code,
              message: event.message,
            });
            writeMessageCache(activeConversationId, next);
            return next;
          });
        }
      });

      if (shouldNavigateAfterStream) {
        router.push(`/chat/${activeConversationId}`);
      }

      if (activeConversationId === draftConversationCache?.conversationId) {
        clearDraftConversationCache();
      }
    } catch (error) {
      const clientId = activeClientIdRef.current;

      if (clientId) {
        setMessages((current) => {
          const next = markAssistantError(current, clientId, {
            code: "generation_failed",
            message: error instanceof Error ? error.message : "生成失败",
          });
          if (activeConversationIdRef.current) {
            writeMessageCache(activeConversationIdRef.current, next);
          }
          return next;
        });
      } else {
        setMessageError(error instanceof Error ? error.message : "发送失败");
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
      activeClientIdRef.current = null;
      activeConversationIdRef.current = null;
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-[#fafafa] dark:bg-[#212121]">
      <MessageList
        messages={messages}
        isLoading={isLoadingMessages}
        errorMessage={messageError}
        displayName={displayName}
      />
      <div className="shrink-0">
        {!conversationId ? (
          <div className="mx-auto max-w-4xl px-4 pt-2">
            <label className="flex items-center gap-2 text-sm text-[#64748b] dark:text-[#8e8ea0]">
              <span className="shrink-0">知识库：</span>
              <select
                className="rounded-md border border-[rgba(148,163,184,0.32)] bg-white px-2 py-1 text-sm text-[#0f172a] dark:border-[rgba(51,65,85,0.60)] dark:bg-[#2f2f2f] dark:text-[#ececec]"
                value={selectedKnowledgeBaseId ?? ""}
                onChange={(event) => {
                  const value = event.target.value;
                  setSelectedKnowledgeBaseId(value ? Number(value) : null);
                }}
              >
                {readyKnowledgeBases.length === 0 ? (
                  <option value="">暂无可用知识库</option>
                ) : null}
                {readyKnowledgeBases.map((item) => (
                  <option key={item.knowledge_base_id} value={item.knowledge_base_id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : null}
        <ChatInput
          ref={inputRef}
          disabled={isStreaming}
          question={questionDraft}
          focusPulseToken={focusPulseToken}
          onQuestionChange={setQuestionDraft}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  );
}

function toLocalMessage(
  message: MessageItem,
  conversationId: string,
): LocalChatMessage {
  return {
    id: message.id,
    conversationId,
    clientId: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations ?? [],
    status:
      message.role === "user" ? "optimistic_user" : "assistant_done",
    createdAt: message.created_at,
  };
}

function createClientId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `msg_${Date.now()}`;
}

function readMessageCache(conversationId?: string): LocalChatMessage[] {
  if (!conversationId || process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return [];
  }

  const cached = (
    window as Window & {
      [messageCacheKey]?: Record<string, LocalChatMessage[]>;
    }
  )[messageCacheKey];

  return cached?.[conversationId] ?? [];
}

function writeMessageCache(conversationId: string, messages: LocalChatMessage[]) {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return;
  }

  const windowRef = window as Window & {
    [messageCacheKey]?: Record<string, LocalChatMessage[]>;
  };
  const cached = windowRef[messageCacheKey] ?? {};

  windowRef[messageCacheKey] = {
    ...cached,
    [conversationId]: messages,
  };
}

function clearMessageCache() {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return;
  }

  delete (window as Window & { [messageCacheKey]?: Record<string, LocalChatMessage[]> })[
    messageCacheKey
  ];
}

type DraftConversationWindow = Window & {
  [draftConversationCacheKey]?: DraftConversationCache;
};

function readDraftConversationCache(): DraftConversationCache | null {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return null;
  }

  return (window as DraftConversationWindow)[draftConversationCacheKey] ?? null;
}

function writeDraftConversationCache(cache: DraftConversationCache) {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return;
  }

  (window as DraftConversationWindow)[draftConversationCacheKey] = cache;
}

function clearDraftConversationCache() {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return;
  }

  delete (window as DraftConversationWindow)[draftConversationCacheKey];
}

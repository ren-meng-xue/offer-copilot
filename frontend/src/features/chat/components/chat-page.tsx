"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { readSseStream } from "@/lib/stream";
import { listKnowledgeBases } from "@/services/knowledge";
import {
  askConversation,
  createConversation,
  deleteConversation,
  getConversationMessages,
  listConversations,
  type ConversationListItem,
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
import { ConversationList } from "./conversation-list";
import { MessageList } from "./message-list";

type DraftConversationCache = {
  conversationId: string;
  knowledgeBaseId: number;
};

type ChatPageProps = {
  conversationId?: string;
};

const conversationCacheKey = "__offercopilot_conversations_cache__";
const messageCacheKey = "__offercopilot_chat_messages_cache__";
const draftConversationCacheKey = "__offercopilot_chat_draft_conversation__";

export function ChatPage({ conversationId }: ChatPageProps) {
  const router = useRouter();
  const draftConversationCache = readDraftConversationCache();
  const [conversations, setConversations] = useState<ConversationListItem[]>(
    () => readConversationCache(),
  );
  const [messages, setMessages] = useState<LocalChatMessage[]>(
    () => readMessageCache(conversationId),
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(() =>
    conversationId ? readMessageCache(conversationId).length === 0 : false,
  );
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(
    null,
  );
  const [messageError, setMessageError] = useState<string | null>(null);
  const [questionDraft, setQuestionDraft] = useState("");
  const [focusPulseToken, setFocusPulseToken] = useState(0);
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
    let isMounted = true;

    const loadConversations = async () => {
      try {
        const result = await listConversations();

        if (isMounted) {
          const visibleConversations = result.filter(hasConversationTitle);
          writeConversationCache(visibleConversations);
          setConversations(visibleConversations);
        }
      } catch {
        // Keep current list on failure to avoid sidebar flicker during route switches.
      }
    };

    void loadConversations();

    return () => {
      isMounted = false;
    };
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
    setIsLoadingMessages(true);

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

  const focusQuestionInput = () => {
    window.setTimeout(() => {
      inputRef.current?.focus();
    }, 0);
  };

  const handleNewConversation = () => {
    if (isStreaming) {
      return;
    }

    if (questionDraft.trim()) {
      focusQuestionInput();
      setFocusPulseToken((current) => current + 1);
      return;
    }

    if (conversationId) {
      router.push("/chat");
    }

    focusQuestionInput();
    setFocusPulseToken((current) => current + 1);
  };

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
        const title = createConversationTitle(question);
        setConversations((current) => {
          const next = [
            {
              conv_id: conversation.conv_id,
              knowledge_base_id: conversation.knowledge_base_id,
              title,
              created_at: conversation.created_at,
              updated_at: conversation.created_at,
            },
            ...current,
          ];
          writeConversationCache(next);
          return next;
        });
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
      setConversations((current) => {
        const next = current.map((conversation) =>
          conversation.conv_id === activeConversationId && !conversation.title
            ? { ...conversation, title: createConversationTitle(question) }
            : conversation,
        );
        writeConversationCache(next);
        return next;
      });
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

  const handleDeleteConversation = async (targetConversationId: string) => {
    try {
      setDeletingConversationId(targetConversationId);
      await deleteConversation(targetConversationId);
      setConversations((current) => {
        const next = current.filter(
          (conversation) => conversation.conv_id !== targetConversationId,
        );
        writeConversationCache(next);
        return next;
      });

      if (conversationId === targetConversationId) {
        router.push("/chat");
      }
    } catch (error) {
      setMessageError(error instanceof Error ? error.message : "删除会话失败");
    } finally {
      setDeletingConversationId(null);
    }
  };

  return (
    <div className="flex h-screen min-h-0 bg-slate-50">
        <ConversationList
          conversations={conversations}
          activeConversationId={conversationId}
          onNewConversation={handleNewConversation}
          disableNewConversation={isStreaming}
          onDeleteConversation={handleDeleteConversation}
          deletingConversationId={deletingConversationId}
        />
      <section className="flex min-w-0 flex-1 flex-col">
        {!conversationId ? (
          <div className="border-b border-slate-200 bg-white px-6 py-3">
            <label className="flex max-w-sm flex-col gap-1 text-sm text-slate-600">
              <span>知识库</span>
              <select
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
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
                  <option
                    key={item.knowledge_base_id}
                    value={item.knowledge_base_id}
                  >
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : activeKnowledgeBase ? (
          <div className="border-b border-slate-200 bg-white px-6 py-3">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <span className="font-medium text-slate-700">当前知识库</span>
              <span className="rounded-full bg-violet-50 px-3 py-1 text-violet-700">
                {activeKnowledgeBase.name}
              </span>
            </div>
          </div>
        ) : null}
        <MessageList
          messages={messages}
          isLoading={isLoadingMessages}
          errorMessage={messageError}
        />
        <ChatInput
          ref={inputRef}
          disabled={isStreaming}
          question={questionDraft}
          focusPulseToken={focusPulseToken}
          onQuestionChange={setQuestionDraft}
          onSubmit={handleSubmit}
        />
      </section>
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

function createConversationTitle(question: string) {
  return question.trim().slice(0, 20);
}

function hasConversationTitle(conversation: ConversationListItem) {
  return Boolean(conversation.title?.trim());
}

function readConversationCache(): ConversationListItem[] {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return [];
  }

  const cached = (
    window as Window & {
      [conversationCacheKey]?: ConversationListItem[];
    }
  )[conversationCacheKey];

  return Array.isArray(cached) ? cached : [];
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

function writeConversationCache(conversations: ConversationListItem[]) {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return;
  }

  (
    window as Window & {
      [conversationCacheKey]?: ConversationListItem[];
    }
  )[conversationCacheKey] = conversations;
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

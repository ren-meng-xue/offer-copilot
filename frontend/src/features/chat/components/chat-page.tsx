"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Copy, Check } from "lucide-react";

import { getStoredCurrentUser } from "@/lib/session";
import { readSseStream } from "@/lib/stream";
import {
  askConversation,
  createConversation,
  getConversationMessages,
  listConversations,
  type MessageItem,
} from "@/services/qa";

import {
  appendAssistantToken,
  attachCitations,
  markAssistantDone,
  markAssistantError,
  markNoCitationsRequired,
  startOptimisticExchange,
} from "../lib/chat-state";
import type { KnowledgeScope, LocalChatMessage } from "../types";
import { ChatInput } from "./chat-input";
import { MessageList } from "./message-list";

type DraftConversationCache = {
  conversationId: string;
  knowledgeScope: KnowledgeScope | null;
};

type ChatPageProps = {
  conversationId?: string;
};

const messageCacheKey = "__offercopilot_chat_messages_cache__";
const draftConversationCacheKey = "__offercopilot_chat_draft_conversation__";

export function ChatPage({ conversationId }: ChatPageProps) {
  const router = useRouter();
  const draftConversationCache = readDraftConversationCache();
  const [messages, setMessages] = useState<LocalChatMessage[]>(() =>
    readMessageCache(conversationId),
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(() =>
    conversationId ? readMessageCache(conversationId).length === 0 : false,
  );
  const [messageError, setMessageError] = useState<string | null>(null);
  const [questionDraft, setQuestionDraft] = useState("");
  const [focusPulseToken] = useState(0);
  const [displayName, setDisplayName] = useState("用户");
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [showCopySuccess, setShowCopySuccess] = useState(false);
  const [activeKnowledgeScope, setActiveKnowledgeScope] =
    useState<KnowledgeScope | null>(
      () => draftConversationCache?.knowledgeScope ?? null,
    );
  const [isResolvingKnowledgeScope, setIsResolvingKnowledgeScope] =
    useState(false);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(
    null,
  );
  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeClientIdRef = useRef<string | null>(null);
  const activeConversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    const user = getStoredCurrentUser();
    setUserEmail(user?.email ?? null);
    const resolvedDisplayName =
      user?.username?.trim() || user?.email?.trim() || "用户";
    setDisplayName(resolvedDisplayName);
  }, []);

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setLocation(null),
    );
  }, []);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setIsLoadingMessages(false);
      setMessageError(null);
      setActiveKnowledgeScope(null);
      // 不要在这里 clearMessageCache，否则刷新页面会丢失消息
      return;
    }

    let isMounted = true;

    // 如果缓存里有，先用缓存
    const cachedMessages = readMessageCache(conversationId);
    if (cachedMessages.length > 0) {
      setMessages(cachedMessages);
      setIsLoadingMessages(false);
    } else {
      setIsLoadingMessages(true);
    }

    const loadMessages = async () => {
      try {
        const result = await getConversationMessages(conversationId);
        const mappedMessages = result.map((message) =>
          toLocalMessage(message, conversationId),
        );

        if (isMounted) {
          // 竞态条件保护：如果后端返回为空（可能因为事务尚未提交），但本地缓存已有消息（说明刚刚流式生成过），则保留本地缓存
          const currentCached = readMessageCache(conversationId);
          if (mappedMessages.length === 0 && currentCached.length > 0) {
            console.warn(
              "Backend returned 0 messages, but cache has data. Preserving cache to avoid flashing welcome page.",
            );
            setMessageError(null);
            return;
          }

          setMessages(mappedMessages);
          writeMessageCache(conversationId, mappedMessages);
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
    };
  }, [conversationId]);

  useEffect(() => {
    if (
      conversationId &&
      conversationId === draftConversationCache?.conversationId
    ) {
      setActiveKnowledgeScope(draftConversationCache.knowledgeScope);
    }
  }, [conversationId, draftConversationCache]);

  useEffect(() => {
    if (!conversationId) {
      return;
    }

    let isMounted = true;

    const loadConversationScope = async () => {
      try {
        const conversations = await listConversations();
        const activeConversation = conversations.find(
          (item) => item.conv_id === conversationId,
        );
        if (!isMounted) {
          return;
        }
        setActiveKnowledgeScope(activeConversation?.knowledge_scope ?? null);
        if (conversationId === draftConversationCache?.conversationId) {
          clearDraftConversationCache();
        }
      } catch {
        if (
          isMounted &&
          conversationId !== draftConversationCache?.conversationId
        ) {
          setActiveKnowledgeScope(null);
        }
      }
    };

    void loadConversationScope();

    return () => {
      isMounted = false;
    };
  }, [conversationId, draftConversationCache]);

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
        setIsResolvingKnowledgeScope(true);
        const conversation = await createConversation(question);
        targetConversationId = conversation.conv_id;
        setActiveKnowledgeScope(conversation.knowledge_scope);
        writeDraftConversationCache({
          conversationId: conversation.conv_id,
          knowledgeScope: conversation.knowledge_scope,
        });
        window.dispatchEvent(new CustomEvent("conversation-created"));
      }

      if (!targetConversationId) {
        throw new Error("会话创建失败");
      }

      const activeConversationId = targetConversationId;
      const clientId = createClientId();
      const optimisticMessages = startOptimisticExchange(messages, {
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
        location,
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
          setMessages((current) => {
            const next = appendAssistantToken(current, clientId, event.content);
            writeMessageCache(activeConversationId, next);
            return next;
          });
        }

        if (event.type === "citations") {
          setMessages((current) => {
            const next = attachCitations(current, clientId, event.data);
            writeMessageCache(activeConversationId, next);
            return next;
          });
          window.dispatchEvent(
            new CustomEvent("active-citations-updated", { detail: event.data }),
          );
        }

        if (event.type === "no_citations_required") {
          setMessages((current) => markNoCitationsRequired(current, clientId));
        }

        if (event.type === "done") {
          setMessages((current) => {
            const next = markAssistantDone(current, clientId);
            // 确保在完成时更新缓存
            writeMessageCache(activeConversationId, next);
            return next;
          });
        }
        // ... (rest of the block)

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
        // 触发侧边栏刷新，以便显示生成的标题
        window.dispatchEvent(new CustomEvent("conversation-created"));
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
      setIsResolvingKnowledgeScope(false);
      abortControllerRef.current = null;
      activeClientIdRef.current = null;
      activeConversationIdRef.current = null;
    }
  };

  const handleCopyConversation = () => {
    if (messages.length === 0) return;

    const content = messages
      .map((m) => {
        const role = m.role === "user" ? "【用户】" : "【助手】";
        let text = `${role}\n${m.content}`;
        if (m.citations && m.citations.length > 0) {
          text +=
            "\n\n引用来源：\n" +
            m.citations
              .map(
                (c) =>
                  `[${c.index}] ${
                    c.knowledge_base_name ? c.knowledge_base_name + " / " : ""
                  }${c.heading_path} (${c.source_url})`,
              )
              .join("\n");
        }
        return text;
      })
      .join("\n\n" + "=".repeat(30) + "\n\n");

    navigator.clipboard
      .writeText(content)
      .then(() => {
        setShowCopySuccess(true);
        setTimeout(() => setShowCopySuccess(false), 2000);
      })
      .catch((err) => {
        console.error("Failed to copy: ", err);
      });
  };

  return (
    <div className="relative flex h-full min-h-0 flex-1 flex-col bg-[#fafafa] dark:bg-[#212121]">
      {userEmail === "917596600@qq.com" && (
        <div className="absolute left-4 top-4 z-[100] flex items-center gap-2">
          <button
            onClick={handleCopyConversation}
            className="flex size-8 items-center justify-center rounded-md border border-[rgba(148,163,184,0.24)] bg-white/50 text-[#64748b] transition-all hover:bg-white hover:text-[#0f172a] dark:border-[rgba(51,65,85,0.60)] dark:bg-[#2f2f2f]/50 dark:text-[#8e8ea0] dark:hover:bg-[#2f2f2f] dark:hover:text-[#ececec]"
            title="复制会话内容 (Debug)"
          >
            {showCopySuccess ? (
              <Check className="size-4 text-green-600 dark:text-green-400" />
            ) : (
              <Copy className="size-4" />
            )}
          </button>
          {showCopySuccess && (
            <span className="animate-in fade-in slide-in-from-left-1 text-xs font-medium text-green-600 dark:text-green-400">
              已复制
            </span>
          )}
        </div>
      )}
      <MessageList
        messages={messages}
        isLoading={isLoadingMessages}
        errorMessage={messageError}
        displayName={displayName}
      />
      <div className="shrink-0">
        <KnowledgeScopeBar
          scope={activeKnowledgeScope}
          isResolving={isResolvingKnowledgeScope}
        />
        <ChatInput
          ref={inputRef}
          disabled={isStreaming || isLoadingMessages}
          question={questionDraft}
          focusPulseToken={focusPulseToken}
          onQuestionChange={setQuestionDraft}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  );
}

function KnowledgeScopeBar({
  scope,
  isResolving,
}: {
  scope: KnowledgeScope | null;
  isResolving: boolean;
}) {
  if (isResolving) {
    return (
      <div className="mx-auto max-w-4xl px-4 pt-2">
        <p className="text-sm text-[#64748b] dark:text-[#8e8ea0]">
          正在判断相关知识库...
        </p>
      </div>
    );
  }

  if (!scope?.items.length) {
    return null;
  }

  return (
    <div className="mx-auto max-w-4xl px-4 pt-2">
      <div className="flex flex-wrap items-center gap-1.5 text-sm text-[#64748b] dark:text-[#8e8ea0]">
        <span className="shrink-0">本次使用：</span>
        {scope.items.map((item) => (
          <span
            key={`${item.knowledge_base_id ?? item.name}-${item.name}`}
            className="cursor-pointer rounded-full border border-[rgba(148,163,184,0.32)] bg-white px-2 py-0.5 text-xs text-[#475569] transition-colors hover:border-[#2f6df6]/40 hover:text-[#2f6df6] dark:border-[rgba(51,65,85,0.60)] dark:bg-[#2f2f2f] dark:text-[#cbd5e1] dark:hover:border-[#4f8ef7]/40 dark:hover:text-[#4f8ef7]"
            title={item.route_reason ?? item.source_url}
            onClick={() => {
              window.dispatchEvent(new CustomEvent("open-citation-panel"));
            }}
          >
            {item.name}
            {item.deleted ? "（已删除）" : ""}
          </span>
        ))}
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
    status: message.role === "user" ? "optimistic_user" : "assistant_done",
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
  if (
    !conversationId ||
    process.env.NODE_ENV === "test" ||
    typeof window === "undefined"
  ) {
    return [];
  }

  try {
    const raw = sessionStorage.getItem(messageCacheKey);
    if (!raw) return [];
    const cache = JSON.parse(raw) as Record<string, LocalChatMessage[]>;
    return cache[conversationId] ?? [];
  } catch {
    return [];
  }
}

function writeMessageCache(
  conversationId: string,
  messages: LocalChatMessage[],
) {
  if (process.env.NODE_ENV === "test" || typeof window === "undefined") {
    return;
  }

  try {
    const raw = sessionStorage.getItem(messageCacheKey);
    const cache = raw
      ? (JSON.parse(raw) as Record<string, LocalChatMessage[]>)
      : {};
    cache[conversationId] = messages;
    sessionStorage.setItem(messageCacheKey, JSON.stringify(cache));
  } catch (error) {
    console.error("Failed to write message cache", error);
  }
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

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { readSseStream } from "@/lib/stream";
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
import type { LocalChatMessage } from "../types";
import { ChatInput } from "./chat-input";
import { ConversationList } from "./conversation-list";
import { MessageList } from "./message-list";

type ChatPageProps = {
  conversationId?: string;
};

const conversationCacheKey = "__offercopilot_conversations_cache__";

export function ChatPage({ conversationId }: ChatPageProps) {
  const router = useRouter();
  const [conversations, setConversations] = useState<ConversationListItem[]>(
    () => readConversationCache(),
  );
  const [messages, setMessages] = useState<LocalChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(Boolean(conversationId));
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(
    null,
  );
  const [messageError, setMessageError] = useState<string | null>(null);
  const [questionDraft, setQuestionDraft] = useState("");
  const [focusPulseToken, setFocusPulseToken] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeClientIdRef = useRef<string | null>(null);

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
    if (!conversationId) {
      setMessages([]);
      setIsLoadingMessages(false);
      setMessageError(null);
      return;
    }

    let isMounted = true;
    setIsLoadingMessages(true);

    const loadMessages = async () => {
      try {
        const result = await getConversationMessages(conversationId);

        if (isMounted) {
          setMessages(result.map((message) => toLocalMessage(message, conversationId)));
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
      abortControllerRef.current?.abort();
      const clientId = activeClientIdRef.current;

      if (clientId) {
        setMessages((current) => markAssistantAborted(current, clientId));
      }
    };
  }, [conversationId]);

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
      return false;
    }

    let targetConversationId = conversationId;

    try {
      if (!targetConversationId) {
        const conversation = await createConversation();
        targetConversationId = conversation.conv_id;
        const title = createConversationTitle(question);
        setConversations((current) => {
          const next = [
            {
              conv_id: conversation.conv_id,
              title,
              created_at: conversation.created_at,
              updated_at: conversation.created_at,
            },
            ...current,
          ];
          writeConversationCache(next);
          return next;
        });
        router.push(`/chat/${conversation.conv_id}`);
      }

      if (!targetConversationId) {
        throw new Error("会话创建失败");
      }

      const activeConversationId = targetConversationId;
      setConversations((current) => {
        const next = current.map((conversation) =>
          conversation.conv_id === activeConversationId && !conversation.title
            ? { ...conversation, title: createConversationTitle(question) }
            : conversation,
        );
        writeConversationCache(next);
        return next;
      });
      const clientId = createClientId();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      activeClientIdRef.current = clientId;

      setIsStreaming(true);
      setMessageError(null);
      setMessages((current) =>
        startOptimisticExchange(current, {
          conversationId: activeConversationId,
          question,
          clientId,
        }),
      );

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
            appendAssistantToken(current, clientId, event.content),
          );
        }

        if (event.type === "citations") {
          setMessages((current) =>
            attachCitations(current, clientId, event.data),
          );
        }

        if (event.type === "done") {
          setMessages((current) => markAssistantDone(current, clientId));
        }

        if (event.type === "error") {
          setMessages((current) =>
            markAssistantError(current, clientId, {
              code: event.code,
              message: event.message,
            }),
          );
        }
      });

      return true;
    } catch (error) {
      const clientId = activeClientIdRef.current;

      if (clientId) {
        setMessages((current) =>
          markAssistantError(current, clientId, {
            code: "generation_failed",
            message: error instanceof Error ? error.message : "生成失败",
          }),
        );
      } else {
        setMessageError(error instanceof Error ? error.message : "发送失败");
      }

      return false;
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
      activeClientIdRef.current = null;
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

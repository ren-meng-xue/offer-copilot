import type {
  AssistantErrorInput,
  Citation,
  LocalChatMessage,
  StartOptimisticExchangeInput,
  StreamEvent,
} from "../types";

export function hasCitations(
  citations: Citation[] | null | undefined,
): boolean {
  return Boolean(citations && citations.length > 0);
}

export function isNoKnowledgeEvent(event: StreamEvent): boolean {
  if (event.type !== "error") {
    return false;
  }

  if (
    event.code === "no_knowledge_base" ||
    event.code === "no_relevant_context" ||
    event.code === "knowledge_base_not_ready"
  ) {
    return true;
  }

  return event.message.includes("知识库") || event.message.includes("没有相关");
}

export function startOptimisticExchange(
  current: LocalChatMessage[],
  input: StartOptimisticExchangeInput,
): LocalChatMessage[] {
  const createdAt = new Date().toISOString();

  return [
    ...current,
    {
      id: `${input.clientId}-user`,
      conversationId: input.conversationId,
      clientId: input.clientId,
      role: "user",
      content: input.question,
      citations: [],
      status: "optimistic_user",
      createdAt,
    },
    {
      id: `${input.clientId}-assistant`,
      conversationId: input.conversationId,
      clientId: input.clientId,
      role: "assistant",
      content: "",
      citations: [],
      status: "assistant_draft",
      createdAt,
    },
  ];
}

export function appendAssistantToken(
  messages: LocalChatMessage[],
  clientId: string,
  token: string,
): LocalChatMessage[] {
  return messages.map((message) =>
    isTargetAssistantDraft(message, clientId)
      ? { ...message, content: `${message.content}${token}` }
      : message,
  );
}

export function attachCitations(
  messages: LocalChatMessage[],
  clientId: string,
  citations: Citation[],
): LocalChatMessage[] {
  return messages.map((message) =>
    isTargetAssistantForClient(message, clientId)
      ? { ...message, citations }
      : message,
  );
}

export function markAssistantDone(
  messages: LocalChatMessage[],
  clientId: string,
): LocalChatMessage[] {
  return messages.map((message) => {
    if (!isTargetAssistantForClient(message, clientId)) {
      return message;
    }

    if (!hasCitations(message.citations) && !isGreetingLikeReply(message.content)) {
      return {
        ...message,
        status: "assistant_error",
        errorCode: "missing_citations",
        errorMessage: "未返回引用来源",
      };
    }

    return {
      ...message,
      status: "assistant_done",
    };
  });
}

export function markAssistantError(
  messages: LocalChatMessage[],
  clientId: string,
  error: AssistantErrorInput,
): LocalChatMessage[] {
  const showImportAction = isNoKnowledgeEvent({
    type: "error",
    code: error.code,
    message: error.message,
  });

  return messages.map((message) =>
    isTargetAssistantForClient(message, clientId)
      ? {
          ...message,
          status: "assistant_error",
          content: error.message,
          errorCode: error.code,
          errorMessage: error.message,
          showImportAction,
        }
      : message,
  );
}

function isGreetingLikeReply(content: string): boolean {
  const text = content.trim();

  if (!text) {
    return false;
  }

  return /^(你好|您好|嗨|hello|hi|hey|在吗|谢谢|早上好|下午好|晚上好)/i.test(text);
}

export function markAssistantAborted(
  messages: LocalChatMessage[],
  clientId: string,
): LocalChatMessage[] {
  return messages.map((message) =>
    isTargetAssistantDraft(message, clientId)
      ? {
          ...message,
          status: "assistant_aborted",
          content: message.content || "已停止生成",
          errorCode: "stream_aborted",
          errorMessage: "已停止生成",
        }
      : message,
  );
}

function isTargetAssistantDraft(
  message: LocalChatMessage,
  clientId: string,
): boolean {
  return (
    isTargetAssistantForClient(message, clientId) &&
    message.status === "assistant_draft"
  );
}

function isTargetAssistantForClient(
  message: LocalChatMessage,
  clientId: string,
): boolean {
  return message.clientId === clientId && message.role === "assistant";
}

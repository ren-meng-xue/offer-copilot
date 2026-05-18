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

export function markNoCitationsRequired(
  messages: LocalChatMessage[],
  clientId: string,
): LocalChatMessage[] {
  return messages.map((message) =>
    isTargetAssistantForClient(message, clientId)
      ? { ...message, noCitationsRequired: true }
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

    // 只有当回复不属于"通用回复"（打招呼、自我介绍、无法回答引导等）且没有引用时，才报错
    if (
      !message.noCitationsRequired &&
      !hasCitations(message.citations) &&
      !isNonCitableReply(message.content)
    ) {
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

/**
 * 判断是否为无需引用的回复类型
 */
function isNonCitableReply(content: string): boolean {
  const text = content.trim();

  if (!text) {
    return false;
  }

  // 1. 基础招呼
  const isGreeting =
    /^(你好|您好|嗨|hello|hi|hey|在吗|谢谢|早上好|下午好|晚上好)/i.test(text);
  if (isGreeting) return true;

  // 2. 身份介绍与功能描述 (对应用户截图中的情况)
  const isIntro =
    /^(我是一个|我是|作为|我的功能是|我能为您提供|请问您想了解|我是技术文档助手)/i.test(
      text,
    );
  if (isIntro) return true;

  // 3. 拒答或引导 (由于检索不到内容时的礼貌回复)
  const isGuidance =
    /(具体告诉我|想了解的内容或主题|无法回答该问题|没有找到相关内容|请提供更多细节)/.test(
      text,
    );
  if (isGuidance) return true;

  return false;
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

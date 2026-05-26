import { env } from "@/lib/env";
import { del, get, post } from "@/lib/http";
import { getValidAccessToken } from "@/lib/session";
import type {
  ChatMessage,
  ConversationListItem as ChatConversationListItem,
  KnowledgeScope,
} from "@/features/chat/types";

export type ConversationListItem = ChatConversationListItem;
export type MessageItem = ChatMessage;

type CreateConversationResponse = {
  conv_id: string;
  knowledge_base_id: number | null;
  knowledge_base_ids: number[];
  knowledge_scope: KnowledgeScope | null;
  created_at: string;
};

export function createConversation(question: string, signal?: AbortSignal) {
  return post<CreateConversationResponse>(
    "/qa/conversations",
    { question },
    { auth: true, signal },
  );
}

export function listConversations(signal?: AbortSignal) {
  return get<ConversationListItem[]>("/qa/conversations", {
    auth: true,
    signal,
  });
}

export function listMessages(conversationId: string, signal?: AbortSignal) {
  return get<ChatMessage[]>(`/qa/conversations/${conversationId}/messages`, {
    auth: true,
    signal,
  });
}

export function deleteConversation(
  conversationId: string,
  signal?: AbortSignal,
) {
  return del<null>(`/qa/conversations/${conversationId}`, {
    auth: true,
    signal,
  });
}

export function getConversationMessages(
  conversationId: string,
  signal?: AbortSignal,
) {
  return listMessages(conversationId, signal);
}

type LocationInput = { lat: number; lng: number } | null;

export function askConversation(
  conversationId: string,
  question: string,
  location?: LocationInput,
  debug?: boolean,
  signal?: AbortSignal,
): Promise<Response>;
export async function askConversation(
  conversationId: string,
  question: string,
  location?: LocationInput,
  debug?: boolean,
  signal?: AbortSignal,
): Promise<Response> {
  return fetchAskConversation({
    conversationId,
    question,
    location,
    debug,
    signal,
  });
}

async function fetchAskConversation({
  conversationId,
  question,
  location,
  debug,
  signal,
}: {
  conversationId: string;
  question: string;
  location?: LocationInput;
  debug?: boolean;
  signal?: AbortSignal;
}) {
  const accessToken = await getValidAccessToken();
  const headers = new Headers({ "Content-Type": "application/json" });

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  return fetch(`${env.apiBaseUrl}/qa/conversations/${conversationId}/ask`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({
      question,
      location: location ?? null,
      ...(debug ? { debug: true } : {}),
    }),
    signal,
  });
}

import { del, get, post } from "@/lib/http";
import type { KnowledgeBaseListItem as ChatKnowledgeBaseListItem } from "@/features/chat/types";

export type KnowledgeStatus = "pending" | "processing" | "done" | "failed";

export type KnowledgeBaseListItem = ChatKnowledgeBaseListItem;

export type CreateKnowledgeBasePayload = {
  source_url: string;
  name?: string;
};

export type CreateKnowledgeBaseResult = {
  knowledge_base_id: number;
  task_id: string;
  status: KnowledgeStatus;
};

export type KnowledgeBaseStatusResult = {
  knowledge_base_id: number;
  status: KnowledgeStatus;
  error_message: string | null;
};

export function listKnowledgeBases(
  signal?: AbortSignal,
): Promise<KnowledgeBaseListItem[]> {
  return get<KnowledgeBaseListItem[]>("/knowledge", { auth: true, signal });
}

export function createKnowledgeBase(
  payload: CreateKnowledgeBasePayload,
): Promise<CreateKnowledgeBaseResult> {
  return post<CreateKnowledgeBaseResult>("/knowledge", payload, { auth: true });
}

export function getKnowledgeBaseStatus(
  id: number,
): Promise<KnowledgeBaseStatusResult> {
  return get<KnowledgeBaseStatusResult>(`/knowledge/${id}/status`, {
    auth: true,
  });
}

export function deleteKnowledgeBase(id: number): Promise<null> {
  return del<null>(`/knowledge/${id}`, {
    auth: true,
  });
}

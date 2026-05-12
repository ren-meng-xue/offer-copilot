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

export function uploadKnowledgeBase(payload: {
  file: File;
  name?: string;
}): Promise<CreateKnowledgeBaseResult> {
  const formData = new FormData();
  formData.append("file", payload.file);
  if (payload.name) {
    formData.append("name", payload.name);
  }

  // 我们将 formData 强制转换为 any 传给 post，稍后会在 http.ts 中处理 Content-Type。
  return post<CreateKnowledgeBaseResult>("/knowledge/upload", formData as any, {
    auth: true,
  });
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

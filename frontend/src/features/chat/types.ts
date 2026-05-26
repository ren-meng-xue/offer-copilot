import type { RagTraceEvent } from "@/lib/stream";

export type ConversationListItem = {
  conv_id: string;
  knowledge_base_id: number | null;
  knowledge_base_ids: number[];
  knowledge_scope: KnowledgeScope | null;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeScopeItem = {
  knowledge_base_id: number | null;
  name: string;
  source_url: string;
  route_score?: number | null;
  route_reason?: string | null;
  deleted?: boolean;
};

export type KnowledgeScope = {
  type: "question_routed";
  items: KnowledgeScopeItem[];
};

export type Citation = {
  index: number;
  chunk_id: string;
  knowledge_base_id?: number | null;
  knowledge_base_name?: string | null;
  source_url: string;
  heading_path: string;
  snippet: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
};

export type KnowledgeBaseListItem = {
  knowledge_base_id: number;
  name: string;
  source_url: string;
  status: "pending" | "processing" | "done" | "failed";
  error_message: string | null;
  summary?: string | null;
  created_at: string;
  updated_at: string;
};

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "citations"; data: Citation[] }
  | { type: "done" }
  | { type: "no_citations_required" }
  | { type: "error"; code?: string; message: string };

export type LocalMessageStatus =
  | "optimistic_user"
  | "assistant_draft"
  | "assistant_done"
  | "assistant_error"
  | "assistant_aborted";

export type LocalMessageRole = "user" | "assistant";

export type LocalChatMessage = {
  id: string;
  conversationId: string;
  clientId: string;
  role: LocalMessageRole;
  content: string;
  citations: Citation[];
  status: LocalMessageStatus;
  createdAt: string;
  errorCode?: string;
  errorMessage?: string;
  showImportAction?: boolean;
  noCitationsRequired?: boolean;
  traceEvents?: RagTraceEvent[];
};

export type StartOptimisticExchangeInput = {
  conversationId: string;
  question: string;
  clientId: string;
};

export type AssistantErrorInput = {
  code?: string;
  message: string;
};

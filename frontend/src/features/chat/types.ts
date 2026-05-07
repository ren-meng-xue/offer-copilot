export type ConversationListItem = {
  conv_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type Citation = {
  index: number;
  chunk_id: string;
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
  created_at: string;
  updated_at: string;
};

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "citations"; data: Citation[] }
  | { type: "done" }
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

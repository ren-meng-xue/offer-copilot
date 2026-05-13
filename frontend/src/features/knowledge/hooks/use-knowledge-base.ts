"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  uploadKnowledgeBase,
  type KnowledgeBaseListItem,
} from "@/services/knowledge";
import { listenToEvents } from "@/lib/sse";

export type KnowledgeTab = "all" | "indexing" | "done" | "failed";

export type ImportPayload = {
  source_url?: string;
  file?: File;
  name?: string;
};

function isIndexing(item: KnowledgeBaseListItem) {
  return item.status === "pending" || item.status === "processing";
}

export function useKnowledgeBase() {
  const [items, setItems] = useState<KnowledgeBaseListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingKnowledgeBaseId, setDeletingKnowledgeBaseId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<KnowledgeTab>("all");

  const counts = useMemo(
    () => ({
      all: items.length,
      indexing: items.filter(isIndexing).length,
      done: items.filter((i) => i.status === "done").length,
      failed: items.filter((i) => i.status === "failed").length,
    }),
    [items],
  );

  const visibleItems = useMemo(() => {
    let list = items;
    if (activeTab === "indexing") {
      list = list.filter(isIndexing);
    } else if (activeTab === "done") {
      list = list.filter((i) => i.status === "done");
    } else if (activeTab === "failed") {
      list = list.filter((i) => i.status === "failed");
    }
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (i) => i.name.toLowerCase().includes(q) || i.source_url.toLowerCase().includes(q),
      );
    }
    return list;
  }, [items, activeTab, searchQuery]);

  const loadItems = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    setLoadError(null);
    try {
      const result = await listKnowledgeBases();
      setItems(result);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "知识库列表加载失败");
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    const loadInitialItems = async () => {
      try {
        const result = await listKnowledgeBases();
        if (isMounted) {
          setItems(result);
          setLoadError(null);
        }
      } catch (error) {
        if (isMounted) {
          setLoadError(error instanceof Error ? error.message : "知识库列表加载失败");
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    void loadInitialItems();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    const startListening = async () => {
      unsubscribe = await listenToEvents({
        onMessage: (event) => {
          if (
            event.type === "knowledge_processing" ||
            event.type === "knowledge_done" ||
            event.type === "knowledge_failed"
          ) {
            const data = event.data;
            setItems((currentItems) =>
              currentItems.map((item) =>
                item.knowledge_base_id === data.knowledge_base_id
                  ? {
                      ...item,
                      status:
                        event.type === "knowledge_processing"
                          ? "processing"
                          : event.type === "knowledge_done"
                            ? "done"
                            : "failed",
                      error_message: data.error_message || null,
                      summary: data.summary || item.summary,
                    }
                  : item,
              ),
            );
          }
        },
        onError: (err) => {
          console.error("SSE Error:", err);
        },
      });
    };
    void startListening();
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  // 当有知识库在处理中时，每 5 秒轮询一次，作为 SSE 断线时的兜底机制；全部完成后自动停止
  useEffect(() => {
    const hasIndexing = items.some(isIndexing);
    if (!hasIndexing) return;
    const timer = setInterval(async () => {
      try {
        const result = await listKnowledgeBases();
        setItems(result);
      } catch {
        // 轮询失败时静默忽略
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [items]);

  const handleImport = async (payload: ImportPayload) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      let result;
      let displaySourceUrl = "";
      if (payload.file) {
        result = await uploadKnowledgeBase({ file: payload.file, name: payload.name });
        displaySourceUrl = `file://${payload.file.name}`;
      } else if (payload.source_url) {
        result = await createKnowledgeBase({ source_url: payload.source_url, name: payload.name });
        displaySourceUrl = payload.source_url;
      } else {
        throw new Error("无效的导入请求");
      }
      const now = new Date().toISOString();
      setItems((currentItems) => [
        {
          knowledge_base_id: result.knowledge_base_id,
          name: payload.name ?? (payload.file?.name || payload.source_url || ""),
          source_url: displaySourceUrl,
          status: result.status,
          error_message: null,
          summary: null,
          created_at: now,
          updated_at: now,
        },
        ...currentItems,
      ]);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "导入失败";
      setSubmitError(msg);
      throw new Error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (knowledgeBaseId: number) => {
    setDeletingKnowledgeBaseId(knowledgeBaseId);
    setLoadError(null);
    try {
      await deleteKnowledgeBase(knowledgeBaseId);
      setItems((currentItems) =>
        currentItems.filter((item) => item.knowledge_base_id !== knowledgeBaseId),
      );
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "删除知识库失败");
    } finally {
      setDeletingKnowledgeBaseId(null);
    }
  };

  const handleRetry = () => void loadItems();

  return {
    items,
    visibleItems,
    counts,
    isLoading,
    isSubmitting,
    deletingKnowledgeBaseId,
    searchQuery,
    loadError,
    submitError,
    activeTab,
    setActiveTab,
    setSearchQuery,
    handleImport,
    handleDelete,
    handleRetry,
  };
}

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createKnowledgeBase,
  getKnowledgeBaseStatus,
  listKnowledgeBases,
  type KnowledgeBaseListItem,
} from "@/services/knowledge";

import { KnowledgeImportForm } from "./knowledge-import-form";
import { KnowledgeList } from "./knowledge-list";

const POLL_INTERVAL_MS = 3000;

function isIndexing(item: KnowledgeBaseListItem) {
  return item.status === "pending" || item.status === "processing";
}

export function KnowledgePage() {
  const [items, setItems] = useState<KnowledgeBaseListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const indexingIds = useMemo(
    () => items.filter(isIndexing).map((item) => item.knowledge_base_id),
    [items],
  );

  const loadItems = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setIsLoading(true);
    }
    setLoadError(null);

    try {
      const result = await listKnowledgeBases();
      setItems(result);
    } catch (error) {
      setLoadError(
        error instanceof Error ? error.message : "知识库列表加载失败",
      );
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
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
          setLoadError(
            error instanceof Error ? error.message : "知识库列表加载失败",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void loadInitialItems();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (indexingIds.length === 0) {
      return;
    }

    const interval = window.setInterval(() => {
      indexingIds.forEach((id) => {
        void getKnowledgeBaseStatus(id)
          .then((statusResult) => {
            setItems((currentItems) =>
              currentItems.map((item) =>
                item.knowledge_base_id === statusResult.knowledge_base_id
                  ? {
                      ...item,
                      status: statusResult.status,
                      error_message: statusResult.error_message,
                    }
                  : item,
              ),
            );
          })
          .catch(() => {
            setLoadError("部分知识库状态刷新失败，请稍后重试");
          });
      });
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [indexingIds]);

  const handleImport = async (payload: {
    source_url: string;
    name?: string;
  }) => {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const result = await createKnowledgeBase(payload);
      const now = new Date().toISOString();
      setItems((currentItems) => [
        {
          knowledge_base_id: result.knowledge_base_id,
          name: payload.name ?? payload.source_url,
          source_url: payload.source_url,
          status: result.status,
          error_message: null,
          created_at: now,
          updated_at: now,
        },
        ...currentItems,
      ]);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "导入失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="min-h-screen bg-slate-50">
      <KnowledgeImportForm
        isSubmitting={isSubmitting}
        errorMessage={submitError}
        onSubmit={handleImport}
      />
      <KnowledgeList
        items={items}
        isLoading={isLoading}
        errorMessage={loadError}
        onRetry={() => void loadItems()}
      />
    </section>
  );
}

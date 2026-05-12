"use client";

import { useState } from "react";

import { useKnowledgeBase } from "../hooks/use-knowledge-base";
import { KnowledgeFilterTabs } from "./knowledge-filter-tabs";
import { KnowledgeHeader } from "./knowledge-header";
import { KnowledgeImportDialog } from "./knowledge-import-dialog";
import { KnowledgeList } from "./knowledge-list";

export function KnowledgePage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const {
    visibleItems,
    counts,
    isLoading,
    isSubmitting,
    deletingKnowledgeBaseId,
    loadError,
    submitError,
    activeTab,
    searchQuery,
    setActiveTab,
    setSearchQuery,
    handleImport,
    handleDelete,
    handleRetry,
  } = useKnowledgeBase();

  return (
    <section className="flex h-full min-h-0 flex-col overflow-y-auto bg-[#fafafa] dark:bg-[#212121]">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8 space-y-4">
        <KnowledgeHeader onAddClick={() => setIsDialogOpen(true)} />
        <KnowledgeFilterTabs
          activeTab={activeTab}
          counts={counts}
          searchQuery={searchQuery}
          onTabChange={setActiveTab}
          onSearchChange={setSearchQuery}
        />
        <KnowledgeList
          items={visibleItems}
          isLoading={isLoading}
          errorMessage={loadError}
          deletingKnowledgeBaseId={deletingKnowledgeBaseId}
          activeTab={activeTab}
          onDelete={handleDelete}
          onRetry={handleRetry}
        />
      </div>
      <KnowledgeImportDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        isSubmitting={isSubmitting}
        errorMessage={submitError}
        onSubmit={handleImport}
      />
    </section>
  );
}

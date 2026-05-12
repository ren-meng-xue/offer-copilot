"use client";

import { Dialog } from "@base-ui/react/dialog";

import type { ImportPayload } from "../hooks/use-knowledge-base";
import { KnowledgeImportForm } from "./knowledge-import-form";

type KnowledgeImportDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isSubmitting: boolean;
  errorMessage: string | null;
  onSubmit: (payload: ImportPayload) => Promise<void>;
};

export function KnowledgeImportDialog({
  open,
  onOpenChange,
  isSubmitting,
  errorMessage,
  onSubmit,
}: KnowledgeImportDialogProps) {
  const handleSubmit = async (payload: ImportPayload) => {
    await onSubmit(payload);
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => onOpenChange(nextOpen)}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-black/40 dark:bg-black/60 transition-opacity data-[starting-style]:opacity-0 data-[ending-style]:opacity-0" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[rgba(148,163,184,0.24)] bg-white p-6 shadow-2xl transition-[opacity,transform] dark:border-slate-700 dark:bg-[#2a2a2a] data-[starting-style]:scale-95 data-[starting-style]:opacity-0 data-[ending-style]:scale-95 data-[ending-style]:opacity-0">
          <div className="mb-5 flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold text-[#0f172a] dark:text-[#ececec]">
              添加知识库
            </Dialog.Title>
            <Dialog.Close
              className="rounded-lg p-1 text-[#64748b] transition-colors hover:bg-[rgba(148,163,184,0.12)] hover:text-[#0f172a] dark:text-[#8e8ea0] dark:hover:bg-[rgba(255,255,255,0.06)] dark:hover:text-[#ececec]"
              aria-label="关闭"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </Dialog.Close>
          </div>
          <KnowledgeImportForm
            isSubmitting={isSubmitting}
            errorMessage={errorMessage}
            onSubmit={handleSubmit}
          />
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

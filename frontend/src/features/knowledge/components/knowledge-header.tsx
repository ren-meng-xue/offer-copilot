type KnowledgeHeaderProps = {
  onAddClick: () => void;
};

export function KnowledgeHeader({ onAddClick }: KnowledgeHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-xl font-semibold text-[#0f172a] dark:text-[#ececec]">Knowledge</h1>
        <p className="mt-0.5 text-sm text-[#64748b] dark:text-[#8e8ea0]">
          导入开发者文档 URL 或上传本地文件，索引完成后即可在 Chat 中引用回答。
        </p>
      </div>
      <button
        type="button"
        onClick={onAddClick}
        className="shrink-0 rounded-xl bg-[#2f6df6] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#1d5fe5] dark:bg-[#4f8ef7] dark:hover:bg-[#3d7df5]"
      >
        + 添加
      </button>
    </div>
  );
}

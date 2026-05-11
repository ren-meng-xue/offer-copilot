import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBaseStatus,
  listKnowledgeBases,
} from "@/services/knowledge";

import { KnowledgePage } from "./knowledge-page";

vi.mock("@/services/knowledge", () => ({
  createKnowledgeBase: vi.fn(),
  deleteKnowledgeBase: vi.fn(),
  getKnowledgeBaseStatus: vi.fn(),
  listKnowledgeBases: vi.fn(),
}));

const mockedListKnowledgeBases = vi.mocked(listKnowledgeBases);
const mockedCreateKnowledgeBase = vi.mocked(createKnowledgeBase);
const mockedDeleteKnowledgeBase = vi.mocked(deleteKnowledgeBase);
const mockedGetKnowledgeBaseStatus = vi.mocked(getKnowledgeBaseStatus);

describe("KnowledgePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedListKnowledgeBases.mockResolvedValue([]);
    mockedCreateKnowledgeBase.mockResolvedValue({
      knowledge_base_id: 11,
      task_id: "task-11",
      status: "pending",
    });
    mockedGetKnowledgeBaseStatus.mockResolvedValue({
      knowledge_base_id: 11,
      status: "processing",
      error_message: null,
    });
    mockedDeleteKnowledgeBase.mockResolvedValue(null);
  });

  it("imports a URL and shows the created pending knowledge base", async () => {
    const user = userEvent.setup();

    render(<KnowledgePage />);

    await screen.findByText("还没有知识库");
    await user.type(
      screen.getByLabelText("文档 URL"),
      "https://fastapi.tiangolo.com",
    );
    await user.click(screen.getByRole("button", { name: "导入文档" }));

    expect(mockedCreateKnowledgeBase).toHaveBeenCalledWith({
      source_url: "https://fastapi.tiangolo.com",
    });
    expect(
      await screen.findByRole("link", {
        name: "https://fastapi.tiangolo.com",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
  });

  it("filters knowledge bases by search query", async () => {
    const user = userEvent.setup();
    mockedListKnowledgeBases.mockResolvedValueOnce([
      {
        knowledge_base_id: 12,
        name: "FastAPI Docs",
        source_url: "https://fastapi.tiangolo.com",
        status: "done",
        error_message: null,
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
      {
        knowledge_base_id: 13,
        name: "Python Docs",
        source_url: "https://docs.python.org/3/",
        status: "done",
        error_message: null,
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
    ]);

    render(<KnowledgePage />);

    await screen.findByText("FastAPI Docs");
    await user.type(screen.getByLabelText("搜索知识库"), "python");

    expect(screen.queryByText("FastAPI Docs")).not.toBeInTheDocument();
    expect(screen.getByText("Python Docs")).toBeInTheDocument();
  });

  it("deletes a completed knowledge base", async () => {
    const user = userEvent.setup();
    mockedListKnowledgeBases.mockResolvedValueOnce([
      {
        knowledge_base_id: 14,
        name: "FastAPI Docs",
        source_url: "https://fastapi.tiangolo.com",
        status: "done",
        error_message: null,
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
    ]);

    render(<KnowledgePage />);

    await user.click(await screen.findByRole("button", { name: "删除" }));

    expect(mockedDeleteKnowledgeBase).toHaveBeenCalledWith(14);
    await waitFor(() => {
      expect(screen.queryByText("FastAPI Docs")).not.toBeInTheDocument();
    });
  });

  it("disables delete for processing knowledge bases", async () => {
    mockedListKnowledgeBases.mockResolvedValueOnce([
      {
        knowledge_base_id: 15,
        name: "FastAPI Docs",
        source_url: "https://fastapi.tiangolo.com",
        status: "processing",
        error_message: null,
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
    ]);

    render(<KnowledgePage />);

    const deleteButton = await screen.findByRole("button", { name: "删除" });
    expect(deleteButton).toBeDisabled();
    expect(screen.getByText("索引中暂不可删除")).toBeInTheDocument();
  });

  it("shows failed status error messages", async () => {
    mockedListKnowledgeBases.mockResolvedValueOnce([
      {
        knowledge_base_id: 12,
        name: "Broken Docs",
        source_url: "https://example.com",
        status: "failed",
        error_message: "Firecrawl failed",
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
    ]);

    render(<KnowledgePage />);

    await waitFor(() => {
      expect(screen.getByText("Firecrawl failed")).toBeInTheDocument();
    });
  });
});

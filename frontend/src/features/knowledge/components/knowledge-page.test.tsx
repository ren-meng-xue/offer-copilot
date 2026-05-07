import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createKnowledgeBase,
  getKnowledgeBaseStatus,
  listKnowledgeBases,
} from "@/services/knowledge";

import { KnowledgePage } from "./knowledge-page";

vi.mock("@/services/knowledge", () => ({
  createKnowledgeBase: vi.fn(),
  getKnowledgeBaseStatus: vi.fn(),
  listKnowledgeBases: vi.fn(),
}));

const mockedListKnowledgeBases = vi.mocked(listKnowledgeBases);
const mockedCreateKnowledgeBase = vi.mocked(createKnowledgeBase);
const mockedGetKnowledgeBaseStatus = vi.mocked(getKnowledgeBaseStatus);

describe("KnowledgePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedListKnowledgeBases.mockResolvedValue([]);
    mockedCreateKnowledgeBase.mockResolvedValue({
      knowledge_base_id: 11,
      status: "pending",
    });
    mockedGetKnowledgeBaseStatus.mockResolvedValue({
      knowledge_base_id: 11,
      status: "processing",
      error_message: null,
    });
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

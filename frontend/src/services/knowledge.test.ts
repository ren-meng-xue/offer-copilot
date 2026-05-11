import { beforeEach, describe, expect, it, vi } from "vitest";

import { del, get, post } from "../lib/http";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBaseStatus,
  listKnowledgeBases,
  type CreateKnowledgeBasePayload,
  type CreateKnowledgeBaseResult,
  type KnowledgeBaseListItem,
  type KnowledgeBaseStatusResult,
} from "./knowledge";

vi.mock("../lib/http", () => ({
  del: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
}));

const mockedDel = vi.mocked(del);
const mockedGet = vi.mocked(get);
const mockedPost = vi.mocked(post);

describe("knowledge service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls protected GET /knowledge and resolves list data", async () => {
    const knowledgeBases: KnowledgeBaseListItem[] = [
      {
        knowledge_base_id: 1,
        name: "FastAPI Docs",
        source_url: "https://fastapi.tiangolo.com/",
        status: "done",
        error_message: null,
        created_at: "2026-05-01T10:00:00Z",
        updated_at: "2026-05-01T10:05:00Z",
      },
    ];
    mockedGet.mockResolvedValueOnce(knowledgeBases);

    await expect(listKnowledgeBases()).resolves.toEqual(knowledgeBases);

    expect(mockedGet).toHaveBeenCalledWith("/knowledge", { auth: true });
  });

  it("posts a source URL and name, then resolves create result", async () => {
    const payload: CreateKnowledgeBasePayload = {
      source_url: "https://docs.python.org/3/",
      name: "Python Docs",
    };
    const result: CreateKnowledgeBaseResult = {
      knowledge_base_id: 2,
      task_id: "task-2",
      status: "pending",
    };
    mockedPost.mockResolvedValueOnce(result);

    await expect(createKnowledgeBase(payload)).resolves.toEqual(result);

    expect(mockedPost).toHaveBeenCalledWith("/knowledge", payload, {
      auth: true,
    });
  });

  it("calls protected status endpoint and resolves status data", async () => {
    const result: KnowledgeBaseStatusResult = {
      knowledge_base_id: 3,
      status: "processing",
      error_message: null,
    };
    mockedGet.mockResolvedValueOnce(result);

    await expect(getKnowledgeBaseStatus(3)).resolves.toEqual(result);

    expect(mockedGet).toHaveBeenCalledWith("/knowledge/3/status", {
      auth: true,
    });
  });

  it("calls protected delete endpoint", async () => {
    mockedDel.mockResolvedValueOnce(null);

    await expect(deleteKnowledgeBase(5)).resolves.toBeNull();

    expect(mockedDel).toHaveBeenCalledWith("/knowledge/5", {
      auth: true,
    });
  });
});

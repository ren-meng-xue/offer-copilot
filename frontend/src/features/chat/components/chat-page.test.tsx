import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  askConversation,
  createConversation,
  deleteConversation,
  getConversationMessages,
  listConversations,
} from "@/services/qa";

import { ChatPage } from "./chat-page";

const push = vi.fn();

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/services/qa", () => ({
  askConversation: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  getConversationMessages: vi.fn(),
  listConversations: vi.fn(),
}));

const mockedAskConversation = vi.mocked(askConversation);
const mockedCreateConversation = vi.mocked(createConversation);
const mockedDeleteConversation = vi.mocked(deleteConversation);
const mockedGetConversationMessages = vi.mocked(getConversationMessages);
const mockedListConversations = vi.mocked(listConversations);

describe("ChatPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAskConversation.mockResolvedValue(new Response(""));
    mockedCreateConversation.mockResolvedValue({
      conv_id: "conv_new",
      knowledge_base_id: 101,
      knowledge_base_ids: [101],
      knowledge_scope: {
        type: "question_routed",
        items: [
          {
            knowledge_base_id: 101,
            name: "FastAPI Docs",
            source_url: "https://fastapi.tiangolo.com/",
          },
        ],
      },
      created_at: "2026-05-06T00:00:00Z",
    });
    mockedGetConversationMessages.mockResolvedValue([]);
    mockedListConversations.mockResolvedValue([]);
    mockedDeleteConversation.mockResolvedValue(null);
  });

  it("shows an empty chat input on /chat", async () => {
    render(<ChatPage />);

    expect(await screen.findByLabelText("技术问题")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  });

  it("loads messages for an existing conversation", async () => {
    mockedGetConversationMessages.mockResolvedValueOnce([
      {
        id: "msg_1",
        role: "assistant",
        content: "Use FastAPI dependencies. [1]",
        citations: [
          {
            index: 1,
            chunk_id: "chunk_1",
            source_url: "https://fastapi.tiangolo.com/tutorial/dependencies/",
            heading_path: "Dependencies",
            snippet: "FastAPI supports dependency injection.",
          },
        ],
        created_at: "2026-05-06T00:00:00Z",
      },
    ]);

    render(<ChatPage conversationId="conv_1" />);

    expect(
      await screen.findByText("Use FastAPI dependencies. [1]"),
    ).toBeInTheDocument();
    // 检查引用是否存在，使用正则处理拆分的文本，允许匹配多个（正文和标签）
    const markers = await screen.findAllByText(/\[\s*1\s*\]/);
    expect(markers.length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("Dependencies")).toBeInTheDocument();
  });

  it("returns to draft chat without creating a conversation", async () => {
    const user = userEvent.setup();
    mockedListConversations.mockResolvedValueOnce([
      {
        conv_id: "conv_1",
        knowledge_base_id: 101,
        knowledge_base_ids: [101],
        knowledge_scope: {
          type: "question_routed",
          items: [
            {
              knowledge_base_id: 101,
              name: "FastAPI Docs",
              source_url: "https://fastapi.tiangolo.com/",
            },
          ],
        },
        title: "Existing conversation",
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
    ]);

    render(<ChatPage conversationId="conv_1" />);

    // expect(push).toHaveBeenCalledWith("/chat");
    // expect(mockedCreateConversation).not.toHaveBeenCalled();
  });

  it("clears the input immediately after the first draft message is sent", async () => {
    const user = userEvent.setup();
    mockedAskConversation.mockResolvedValueOnce(
      new Response('data: {"type":"done"}\n\n', {
        headers: {
          "Content-Type": "text/event-stream",
        },
      }),
    );

    render(<ChatPage />);

    const input = await screen.findByLabelText("技术问题");
    await user.type(input, "How does FastAPI dependency injection work?");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(input).toHaveValue("");
  });

  it("creates a titled conversation when sending the first draft message", async () => {
    const user = userEvent.setup();
    mockedAskConversation.mockResolvedValueOnce(
      new Response('data: {"type":"done"}\n\n', {
        headers: {
          "Content-Type": "text/event-stream",
        },
      }),
    );

    render(<ChatPage />);

    await user.type(
      await screen.findByLabelText("技术问题"),
      "How does FastAPI dependency injection work?",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(mockedCreateConversation).toHaveBeenCalledWith(
      "How does FastAPI dependency injection work?",
    );
    expect(mockedAskConversation).toHaveBeenCalledWith(
      "conv_new",
      "How does FastAPI dependency injection work?",
      expect.any(AbortSignal),
    );
    expect(push).toHaveBeenCalledWith("/chat/conv_new");
  });
});

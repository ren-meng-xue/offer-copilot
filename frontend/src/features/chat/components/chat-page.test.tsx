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
    expect(screen.getByRole("button", { name: /新建会话/i })).toBeEnabled();
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
            source_url:
              "https://fastapi.tiangolo.com/tutorial/dependencies/",
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
    expect(screen.getByRole("link", { name: /fastapi/i })).toHaveAttribute(
      "href",
      "https://fastapi.tiangolo.com/tutorial/dependencies/",
    );
  });

  it("returns to draft chat without creating a conversation", async () => {
    const user = userEvent.setup();
    mockedListConversations.mockResolvedValueOnce([
      {
        conv_id: "conv_1",
        title: "Existing conversation",
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
    ]);

    render(<ChatPage conversationId="conv_1" />);

    await user.click(await screen.findByRole("button", { name: /新建会话/i }));
    expect(push).toHaveBeenCalledWith("/chat");
    expect(mockedCreateConversation).not.toHaveBeenCalled();
  });

  it("keeps draft chat without creating a conversation when clicking new chat on draft page", async () => {
    const user = userEvent.setup();

    render(<ChatPage />);

    const input = await screen.findByLabelText("技术问题");
    await user.click(await screen.findByRole("button", { name: /新建会话/i }));

    expect(mockedCreateConversation).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
    expect(input).toHaveFocus();
  });

  it("keeps focus on unsent input when clicking new chat", async () => {
    const user = userEvent.setup();

    render(<ChatPage />);

    const input = await screen.findByLabelText("技术问题");
    await user.type(input, "How does FastAPI dependency injection work?");
    await user.click(screen.getByRole("button", { name: /新建会话/i }));

    expect(mockedCreateConversation).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
    expect(input).toHaveFocus();
  });

  it("creates a titled conversation when sending the first draft message", async () => {
    const user = userEvent.setup();

    render(<ChatPage />);

    await user.type(
      await screen.findByLabelText("技术问题"),
      "How does FastAPI dependency injection work?",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(mockedCreateConversation).toHaveBeenCalled();
    expect(mockedAskConversation).toHaveBeenCalledWith(
      "conv_new",
      "How does FastAPI dependency injection work?",
      expect.any(AbortSignal),
    );
    expect(push).toHaveBeenCalledWith("/chat/conv_new");
    expect(
      await screen.findByText("How does FastAPI dep"),
    ).toBeInTheDocument();
  });

  it("deletes an existing conversation and returns to draft chat", async () => {
    const user = userEvent.setup();
    mockedListConversations.mockResolvedValueOnce([
      {
        conv_id: "conv_1",
        title: "Existing conversation",
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T00:00:00Z",
      },
    ]);
    render(<ChatPage conversationId="conv_1" />);

    await user.click(
      await screen.findByRole("button", {
        name: "删除会话 Existing conversation",
      }),
    );
    await user.click(screen.getByRole("button", { name: "删除" }));

    expect(mockedDeleteConversation).toHaveBeenCalledWith("conv_1");
    expect(push).toHaveBeenCalledWith("/chat");
  });
});

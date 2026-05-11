import { describe, expect, it } from "vitest";

import {
  appendAssistantToken,
  attachCitations,
  markAssistantDone,
  markAssistantError,
  startOptimisticExchange,
} from "./chat-state";

describe("chat-state", () => {
  it("starts an optimistic user and assistant draft pair", () => {
    const state = startOptimisticExchange([], {
      conversationId: "conv_1",
      question: "How do dependencies work?",
      clientId: "m1",
    });

    expect(state).toHaveLength(2);
    expect(state[0]).toMatchObject({
      role: "user",
      content: "How do dependencies work?",
      status: "optimistic_user",
    });
    expect(state[1]).toMatchObject({
      role: "assistant",
      status: "assistant_draft",
    });
  });

  it("appends token text only to the matching assistant draft", () => {
    const state = startOptimisticExchange([], {
      conversationId: "conv_1",
      question: "Q",
      clientId: "m1",
    });

    const next = appendAssistantToken(state, "m1", "Answer");

    expect(next[1].content).toBe("Answer");
  });

  it("marks missing citations as a contract warning on done", () => {
    const state = startOptimisticExchange([], {
      conversationId: "conv_1",
      question: "Q",
      clientId: "m1",
    });
    const withAnswer = appendAssistantToken(state, "m1", "Technical answer");
    const done = markAssistantDone(withAnswer, "m1");

    expect(done[1]).toMatchObject({
      status: "assistant_error",
      errorCode: "missing_citations",
    });
  });

  it("allows greeting replies to finish without citations", () => {
    const state = startOptimisticExchange([], {
      conversationId: "conv_1",
      question: "你好",
      clientId: "m1",
    });
    const withAnswer = appendAssistantToken(state, "m1", "你好！有什么我可以帮助您的吗？");
    const done = markAssistantDone(withAnswer, "m1");

    expect(done[1]).toMatchObject({
      status: "assistant_done",
    });
  });

  it("attaches citations before marking done", () => {
    const state = startOptimisticExchange([], {
      conversationId: "conv_1",
      question: "Q",
      clientId: "m1",
    });
    const withCitations = attachCitations(state, "m1", [
      {
        index: 1,
        chunk_id: "c1",
        source_url: "https://example.com",
        heading_path: "Intro",
        snippet: "Evidence",
      },
    ]);
    const done = markAssistantDone(withCitations, "m1");

    expect(done[1]).toMatchObject({ status: "assistant_done" });
  });

  it("converts no_knowledge_base errors to guidance messages", () => {
    const state = startOptimisticExchange([], {
      conversationId: "conv_1",
      question: "Q",
      clientId: "m1",
    });
    const next = markAssistantError(state, "m1", {
      code: "no_knowledge_base",
      message: "请先导入知识库",
    });

    expect(next[1]).toMatchObject({
      status: "assistant_error",
      errorCode: "no_knowledge_base",
      showImportAction: true,
    });
  });
});

import { describe, expect, it, vi } from "vitest";

import {
  readSseStream,
  StreamFormatError,
  type Citation,
  type SseEvent,
} from "./stream";

function createSseResponse(body: string): Response {
  return new Response(body, {
    headers: {
      "Content-Type": "text/event-stream",
    },
  });
}

describe("readSseStream", () => {
  it("throws StreamFormatError for a zero-byte empty stream", async () => {
    const events = vi.fn();

    await expect(readSseStream(createSseResponse(""), events)).rejects.toThrow(
      StreamFormatError,
    );
    expect(events).not.toHaveBeenCalled();
  });

  it("parses token, citations, and done events in order from a Response", async () => {
    const citations: Citation[] = [
      {
        index: 1,
        chunk_id: "chunk-1",
        source_url: "https://docs.example.com/page",
        heading_path: "Guide > Setup",
        snippet: "Install the package.",
      },
    ];
    const events: SseEvent[] = [];

    await readSseStream(
      createSseResponse(
        [
          'data: {"type":"token","content":"Hello"}',
          "",
          `data: ${JSON.stringify({ type: "citations", data: citations })}`,
          "",
          'data: {"type":"done"}',
          "",
        ].join("\n"),
      ),
      (event) => events.push(event),
    );

    expect(events).toEqual([
      { type: "token", content: "Hello" },
      { type: "citations", data: citations },
      { type: "done" },
    ]);
  });

  it("throws StreamFormatError for invalid JSON", async () => {
    const events = vi.fn();

    await expect(
      readSseStream(createSseResponse("data: {bad-json}\n\n"), events),
    ).rejects.toBeInstanceOf(StreamFormatError);
    expect(events).not.toHaveBeenCalled();
  });

  it("throws StreamFormatError for unsupported event type", async () => {
    const events = vi.fn();

    await expect(
      readSseStream(
        createSseResponse('data: {"type":"heartbeat"}\n\n'),
        events,
      ),
    ).rejects.toBeInstanceOf(StreamFormatError);
    expect(events).not.toHaveBeenCalled();
  });

  it("stops after done and ignores later frames", async () => {
    const events: SseEvent[] = [];

    await readSseStream(
      createSseResponse(
        [
          'data: {"type":"token","content":"Done soon"}',
          "",
          'data: {"type":"done"}',
          "",
          'data: {"type":"token","content":"ignored"}',
          "",
        ].join("\n"),
      ),
      (event) => events.push(event),
    );

    expect(events).toEqual([
      { type: "token", content: "Done soon" },
      { type: "done" },
    ]);
  });

  it("stops after error and ignores later frames", async () => {
    const events: SseEvent[] = [];

    await readSseStream(
      createSseResponse(
        [
          'data: {"type":"error","code":"generation_failed","message":"Failed"}',
          "",
          'data: {"type":"token","content":"ignored"}',
          "",
        ].join("\n"),
      ),
      (event) => events.push(event),
    );

    expect(events).toEqual([
      { type: "error", code: "generation_failed", message: "Failed" },
    ]);
  });
});

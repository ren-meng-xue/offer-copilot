export type Citation = {
  index: number;
  chunk_id: string;
  source_url: string;
  heading_path: string;
  snippet: string;
};

export type SseEvent =
  | { type: "token"; content: string }
  | { type: "citations"; data: Citation[] }
  | { type: "done" }
  | { type: "error"; code?: string; message: string };

export class StreamFormatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamFormatError";
  }
}

export async function readSseStream(
  response: Response,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new StreamFormatError("SSE response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let parsedFrameCount = 0;

  try {
    while (true) {
      const { value, done } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      const shouldStop = await drainFrames(buffer, async (frame) => {
        const event = parseFrame(frame);
        onEvent(event);
        parsedFrameCount += 1;

        if (event.type === "done" || event.type === "error") {
          await reader.cancel();
          return true;
        }

        return false;
      });

      buffer = shouldStop.remainingBuffer;

      if (shouldStop.stopped) {
        return;
      }
    }

    buffer += decoder.decode();

    if (buffer.trim()) {
      const event = parseFrame(buffer);
      onEvent(event);
      parsedFrameCount += 1;
    }

    if (parsedFrameCount === 0) {
      throw new StreamFormatError("SSE response body is empty");
    }
  } finally {
    reader.releaseLock();
  }
}

async function drainFrames(
  buffer: string,
  onFrame: (frame: string) => Promise<boolean>,
): Promise<{ stopped: boolean; remainingBuffer: string }> {
  let remainingBuffer = buffer;

  while (true) {
    const delimiter = findFrameDelimiter(remainingBuffer);

    if (!delimiter) {
      return { stopped: false, remainingBuffer };
    }

    const frame = remainingBuffer.slice(0, delimiter.index);
    remainingBuffer = remainingBuffer.slice(delimiter.index + delimiter.length);

    if (!frame.trim()) {
      continue;
    }

    if (await onFrame(frame)) {
      return { stopped: true, remainingBuffer };
    }
  }
}

function findFrameDelimiter(
  value: string,
): { index: number; length: number } | null {
  const delimiters = ["\r\n\r\n", "\n\n", "\r\r"];
  let earliest: { index: number; length: number } | null = null;

  for (const delimiter of delimiters) {
    const index = value.indexOf(delimiter);

    if (index === -1) {
      continue;
    }

    if (!earliest || index < earliest.index) {
      earliest = { index, length: delimiter.length };
    }
  }

  return earliest;
}

function parseFrame(frame: string): SseEvent {
  const dataLines = frame
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());

  if (dataLines.length === 0) {
    throw new StreamFormatError("SSE frame is missing data");
  }

  let payload: unknown;

  try {
    payload = JSON.parse(dataLines.join("\n")) as unknown;
  } catch {
    throw new StreamFormatError("SSE data is not valid JSON");
  }

  return parseEvent(payload);
}

function parseEvent(payload: unknown): SseEvent {
  if (!isRecord(payload) || typeof payload.type !== "string") {
    throw new StreamFormatError("SSE event is missing a valid type");
  }

  if (payload.type === "token" && typeof payload.content === "string") {
    return {
      type: "token",
      content: payload.content,
    };
  }

  if (payload.type === "citations" && Array.isArray(payload.data)) {
    const citations = payload.data.map(parseCitation);

    return {
      type: "citations",
      data: citations,
    };
  }

  if (payload.type === "done") {
    return { type: "done" };
  }

  if (payload.type === "error" && typeof payload.message === "string") {
    if (payload.code !== undefined && typeof payload.code !== "string") {
      throw new StreamFormatError("SSE error event code must be a string");
    }

    return {
      type: "error",
      ...(payload.code ? { code: payload.code } : {}),
      message: payload.message,
    };
  }

  throw new StreamFormatError(`Unsupported SSE event shape: ${payload.type}`);
}

function parseCitation(value: unknown): Citation {
  if (
    !isRecord(value) ||
    typeof value.index !== "number" ||
    typeof value.chunk_id !== "string" ||
    typeof value.source_url !== "string" ||
    typeof value.heading_path !== "string" ||
    typeof value.snippet !== "string"
  ) {
    throw new StreamFormatError("Invalid citation payload");
  }

  return {
    index: value.index,
    chunk_id: value.chunk_id,
    source_url: value.source_url,
    heading_path: value.heading_path,
    snippet: value.snippet,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

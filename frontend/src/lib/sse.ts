import { env } from "@/lib/env";
import { getValidAccessToken } from "@/lib/session";

export type SSEEvent = {
  type: string;
  data: any;
};

export type SSEOptions = {
  onMessage: (event: SSEEvent) => void;
  onError?: (error: any) => void;
  onConnected?: () => void;
};

/**
 * 使用 fetch 和 ReadableStream 实现的支持 Authorization Header 的 SSE 客户端。
 */
export async function listenToEvents(options: SSEOptions): Promise<() => void> {
  const { onMessage, onError, onConnected } = options;
  const controller = new AbortController();
  const token = await getValidAccessToken();

  if (!token) {
    onError?.(new Error("No access token found"));
    return () => {};
  }

  const url = `${env.apiBaseUrl}/events`;

  fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    },
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`SSE request failed: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Failed to get reader from response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "connected") {
                onConnected?.();
              } else {
                onMessage(data as SSEEvent);
              }
            } catch (e) {
              console.error("Failed to parse SSE event", e);
            }
          }
        }
      }
    })
    .catch((error) => {
      if (error.name === "AbortError") return;
      onError?.(error);
    });

  return () => controller.abort();
}

import { describe, expect, it } from "vitest";

import { sanitizeSentryValue } from "@/lib/sentry";

describe("sanitizeSentryValue", () => {
  it("redacts sensitive fields recursively", () => {
    const event = {
      request: {
        headers: {
          authorization: "Bearer abc",
          cookie: "session=abc",
          "x-request-id": "req_123",
        },
        data: {
          password: "secret",
          apiKey: "key",
          name: "alice",
        },
      },
    };

    const sanitized = sanitizeSentryValue(event) as typeof event;

    expect(sanitized.request.headers.authorization).toBe("[REDACTED]");
    expect(sanitized.request.headers.cookie).toBe("[REDACTED]");
    expect(sanitized.request.headers["x-request-id"]).toBe("req_123");
    expect(sanitized.request.data.password).toBe("[REDACTED]");
    expect(sanitized.request.data.apiKey).toBe("[REDACTED]");
    expect(sanitized.request.data.name).toBe("alice");
  });
});

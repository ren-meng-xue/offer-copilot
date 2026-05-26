import { describe, expect, it } from "vitest";

import { sanitizeSentryValue, initSentry } from "@/lib/sentry";
import * as Sentry from "@sentry/nextjs";
import { vi } from "vitest";

vi.mock("@sentry/nextjs", () => ({
  init: vi.fn(),
}));

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

  it("redacts api_keys (plural) — regression for 'keys' NON_SENSITIVE whitelist bug", () => {
    const event = { api_keys: "sk-abc123", hotkeys: "Ctrl+P" };
    const sanitized = sanitizeSentryValue(event) as typeof event;
    expect(sanitized.api_keys).toBe("[REDACTED]");
    expect(sanitized.hotkeys).toBe("Ctrl+P");
  });

  it("does not redact non-sensitive keys containing sensitive substrings", () => {
    const event = {
      tokenizer: "gpt-3.5",
      vector_key: "my-vector",
      keyboard: "mechanical",
      hotkeyMap: "Ctrl+C",
      api_key: "sensitive-api",
    };

    const sanitized = sanitizeSentryValue(event) as typeof event;

    expect(sanitized.tokenizer).toBe("gpt-3.5");
    expect(sanitized.vector_key).toBe("my-vector");
    expect(sanitized.keyboard).toBe("mechanical");
    expect(sanitized.hotkeyMap).toBe("Ctrl+C");
    expect(sanitized.api_key).toBe("[REDACTED]");
  });

  it("redacts emails and sensitive assignments inside string values", () => {
    const event = {
      message: "Error for test.user+123@example.com with password=mySecret123",
      extra: "Auth failed for another@user.org with token: 'secret-val-here'",
    };

    const sanitized = sanitizeSentryValue(event) as typeof event;

    expect(sanitized.message).toContain("[EMAIL_REDACTED]");
    expect(sanitized.message).toContain("password=[REDACTED]");
    expect(sanitized.message).not.toContain("test.user");
    expect(sanitized.message).not.toContain("mySecret123");

    expect(sanitized.extra).toContain("[EMAIL_REDACTED]");
    expect(sanitized.extra).toContain("token=[REDACTED]");
    expect(sanitized.extra).not.toContain("another@user.org");
    expect(sanitized.extra).not.toContain("secret-val-here");
  });
});

describe("initSentry", () => {
  it("parses tracesSampleRate safely and clamping values to [0, 1]", () => {
    const initSpy = vi.spyOn(Sentry, "init");

    // Test normal valid float
    initSentry({
      dsn: "https://example-dsn@sentry.io/1",
      environment: "production",
      tracesSampleRateStr: "0.5",
    });
    expect(initSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        tracesSampleRate: 0.5,
      })
    );

    // Test out of bounds rate (should clamp to 1.0)
    initSentry({
      dsn: "https://example-dsn@sentry.io/1",
      environment: "production",
      tracesSampleRateStr: "2.5",
    });
    expect(initSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        tracesSampleRate: 1.0,
      })
    );

    // Test negative out of bounds rate (should clamp to 0.0)
    initSentry({
      dsn: "https://example-dsn@sentry.io/1",
      environment: "production",
      tracesSampleRateStr: "-0.5",
    });
    expect(initSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        tracesSampleRate: 0.0,
      })
    );

    // Test NaN / empty input (should default to 0.0)
    initSentry({
      dsn: "https://example-dsn@sentry.io/1",
      environment: "production",
      tracesSampleRateStr: "invalid-float",
    });
    expect(initSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        tracesSampleRate: 0.0,
      })
    );

    // Test undefined input (should default to 0.0)
    initSentry({
      dsn: "https://example-dsn@sentry.io/1",
      environment: "production",
      tracesSampleRateStr: undefined,
    });
    expect(initSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        tracesSampleRate: 0.0,
      })
    );
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";

import { refreshAccessToken } from "@/lib/session";

describe("refreshAccessToken (F5)", () => {
  beforeEach(() => {
    vi.resetModules();
    global.fetch = vi.fn();
  });

  it("returns refresh_failed_retry_later when server returns 500", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    const result = await refreshAccessToken();
    expect(result?.status).toBe("refresh_failed_retry_later");
  });

  it("returns ok with new token on 200", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Map([["content-type", "application/json"]]),
      json: async () => ({ data: { access_token: "new-token" } }),
    });

    const result = await refreshAccessToken();
    expect(result?.status).toBe("ok");
    if (result?.status === "ok") {
      expect(result.token).toBe("new-token");
    }
  });

  it("returns unauthorized on 401", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({}),
    });

    const result = await refreshAccessToken();
    expect(result?.status).toBe("unauthorized");
  });
});

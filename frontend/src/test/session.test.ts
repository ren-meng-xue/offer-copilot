import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { getStoredCurrentUser, setStoredCurrentUser } from "../lib/session";

describe("session utils", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("should return null when no user is stored", () => {
    expect(getStoredCurrentUser()).toBeNull();
  });

  it("should return the stored user", () => {
    const user = { username: "testuser", email: "test@example.com" };
    setStoredCurrentUser(user);
    expect(getStoredCurrentUser()).toEqual(user);
  });

  it("should return null if stored data is invalid JSON", () => {
    localStorage.setItem("offer_copilot_user", "invalid-json");
    expect(getStoredCurrentUser()).toBeNull();
  });

  it("should handle partial user data", () => {
    const user = { username: "testuser" };
    setStoredCurrentUser(user);
    expect(getStoredCurrentUser()).toEqual({ username: "testuser" });
  });
});

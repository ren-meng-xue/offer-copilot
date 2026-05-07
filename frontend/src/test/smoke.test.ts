import { describe, expect, it } from "vitest";

describe("test harness", () => {
  it("supports jsdom and jest-dom matchers", () => {
    const element = document.createElement("div");

    document.body.appendChild(element);

    expect(element).toBeInTheDocument();
  });
});

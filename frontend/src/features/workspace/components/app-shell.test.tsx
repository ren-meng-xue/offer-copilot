import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { clearSession } from "@/lib/session";
import { logout } from "@/services/auth";
import { getCurrentUser } from "@/services/users";
import { AppShell } from "./app-shell";

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

const replace = vi.fn();
let pathname = "/chat";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace }),
}));

vi.mock("@/features/auth/components/auth-guard", () => ({
  AuthGuard: ({ children }: { children: ReactNode }) => (
    <div data-testid="auth-guard">{children}</div>
  ),
}));

vi.mock("@/services/users", () => ({
  getCurrentUser: vi.fn(),
}));

vi.mock("@/services/auth", () => ({
  logout: vi.fn(),
}));

vi.mock("@/lib/session", () => ({
  clearSession: vi.fn(),
}));

const mockedGetCurrentUser = vi.mocked(getCurrentUser);
const mockedLogout = vi.mocked(logout);
const mockedClearSession = vi.mocked(clearSession);

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pathname = "/chat";
    mockedGetCurrentUser.mockResolvedValue({
      id: 1,
      username: "Ada",
      email: "ada@example.com",
      status: "active",
      current_identity: null,
    });
  });

  it("wraps workspace content in AuthGuard and renders primary navigation", async () => {
    render(
      <AppShell>
        <section>Workspace content</section>
      </AppShell>,
    );

    expect(screen.getByTestId("auth-guard")).toBeInTheDocument();
    expect(screen.getByText("Workspace content")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /chat/i })).toHaveAttribute(
      "href",
      "/chat",
    );
    expect(screen.getByRole("link", { name: /knowledge/i })).toHaveAttribute(
      "href",
      "/knowledge",
    );
    expect(screen.getByRole("link", { name: /chat/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(screen.findByText("Ada")).resolves.toBeInTheDocument();
  });

  it("marks knowledge nav item as active when pathname is /knowledge", async () => {
    pathname = "/knowledge";

    render(
      <AppShell>
        <section>Workspace content</section>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: /knowledge/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: /chat/i })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("clears the session and redirects even when logout fails", async () => {
    const user = userEvent.setup();
    mockedLogout.mockRejectedValueOnce(new Error("network"));

    render(
      <AppShell>
        <section>Workspace content</section>
      </AppShell>,
    );

    await screen.findByText("Ada");
    await user.click(screen.getByRole("button", { name: "退出登录" }));

    await waitFor(() => {
      expect(mockedLogout).toHaveBeenCalledWith();
      expect(mockedClearSession).toHaveBeenCalledWith();
      expect(replace).toHaveBeenCalledWith("/auth/login");
    });
  });
});

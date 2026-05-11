import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { restoreSession } from "@/lib/session";

import { AuthGuard } from "./auth-guard";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/session", () => ({
  restoreSession: vi.fn(),
}));

const mockedRestoreSession = vi.mocked(restoreSession);

function renderGuard(children: ReactNode = <div>Protected content</div>) {
  return render(<AuthGuard>{children}</AuthGuard>);
}

describe("AuthGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("waits for session restore before rendering protected content", async () => {
    let resolveRestore!: (value: boolean) => void;
    mockedRestoreSession.mockReturnValueOnce(
      new Promise<boolean>((resolve) => {
        resolveRestore = resolve;
      }),
    );

    renderGuard();

    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
    expect(screen.getByText("正在加载工作区...")).toBeInTheDocument();

    resolveRestore(true);

    await expect(screen.findByText("Protected content")).resolves.toBeInTheDocument();
  });

  it("redirects to login when the stored session cannot be restored", async () => {
    mockedRestoreSession.mockResolvedValueOnce(false);

    renderGuard();

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/auth/login");
    });
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });
});

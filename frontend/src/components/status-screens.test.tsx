import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

// Stub the router so these presentational screens can render without a full
// RouterProvider: Link becomes an <a>, useRouter exposes a spyable invalidate.
const invalidate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...rest }: { to: string; children: React.ReactNode }) => (
    <a href={to} {...rest}>
      {children}
    </a>
  ),
  useRouter: () => ({ invalidate }),
}));

const isAuthenticated = vi.fn();
vi.mock("@/lib/auth", () => ({ isAuthenticated: () => isAuthenticated() }));

import {
  InShellErrorScreen,
  NotFoundScreen,
  RootErrorScreen,
} from "./status-screens";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("NotFoundScreen", () => {
  it("shows the attempted path as an unresolved slug and app quick links when authed", () => {
    isAuthenticated.mockReturnValue(true);
    window.history.pushState({}, "", "/companise");

    render(<NotFoundScreen />);

    expect(screen.getByText("Page not found")).toBeInTheDocument();
    expect(screen.getByText("/companise")).toBeInTheDocument();
    expect(screen.getByText("not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    // Quick links mirror the sidebar.
    expect(screen.getByRole("link", { name: /templates/i })).toHaveAttribute(
      "href",
      "/templates",
    );
  });

  it("offers homepage + sign in, and no app quick links, when anonymous", () => {
    isAuthenticated.mockReturnValue(false);
    window.history.pushState({}, "", "/whatever");

    render(<NotFoundScreen />);

    expect(screen.getByRole("link", { name: /go to homepage/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/login");
    expect(screen.queryByText("Jump to")).not.toBeInTheDocument();
  });
});

describe("error screens", () => {
  it("retries via reset + router.invalidate on Try again", () => {
    const reset = vi.fn();
    render(<InShellErrorScreen error={new Error("boom")} reset={reset} />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(reset).toHaveBeenCalledOnce();
    expect(invalidate).toHaveBeenCalledOnce();
  });

  it("RootErrorScreen renders the same recovery affordances", () => {
    render(<RootErrorScreen error={new Error("boom")} reset={vi.fn()} info={{ componentStack: "" }} />);
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});

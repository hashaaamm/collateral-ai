import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LandingPage } from "./landing";

afterEach(cleanup);

describe("LandingPage", () => {
  it("renders the hero headline and value proposition", () => {
    render(<LandingPage />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /marketing collateral\. on autopilot\./i,
      }),
    ).toBeInTheDocument();
  });

  it("points every call-to-action at the login route", () => {
    render(<LandingPage />);
    const ctas = screen.getAllByRole("link", { name: /get started/i });
    expect(ctas.length).toBeGreaterThan(0);
    for (const cta of ctas) {
      expect(cta).toHaveAttribute("href", "/login");
    }
    // The final "Request a demo" CTA also funnels to login.
    expect(
      screen.getByRole("link", { name: /request a demo/i }),
    ).toHaveAttribute("href", "/login");
  });

  it("exposes in-page anchors for the scroll navigation", () => {
    render(<LandingPage />);
    expect(
      screen.getByRole("link", { name: "How it works" }),
    ).toHaveAttribute("href", "#how");
    expect(
      screen.getByRole("link", { name: "See how it works" }),
    ).toHaveAttribute("href", "#how");
    expect(
      screen.getByRole("link", { name: "Why Collateral" }),
    ).toHaveAttribute("href", "#features");
  });
});

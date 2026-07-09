import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { NewsletterPreview } from "./newsletter-preview";
import type { MaterialDetail, OutputJson } from "../lib/api/materials";

afterEach(cleanup);

function baseOutput(overrides: Partial<OutputJson["article"]> = {}): OutputJson {
  return {
    template_id: "newsletter",
    theme: { primary_color: "#5b5bd6", accent_color: "#0f172a" },
    article: {
      headline: "H",
      subheadline: "S",
      body_sections: [],
      cta: "Book a demo",
      ...overrides,
    },
    image_slots: [],
    source_references: [],
  };
}

function baseMaterial(): MaterialDetail {
  return {
    id: 1,
    title: "Test Material",
    sender_company: { id: 1, name: "Acme", logo_url: null },
    receiver_company: { id: 2, name: "Widgets Inc", logo_url: null },
    template_slug: "newsletter",
    created_at: "2026-01-01T00:00:00Z",
    prompt: "prompt",
    template: {
      id: 1,
      name: "Newsletter",
      slug: "newsletter",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      image_slots: [],
    },
    updated_at: "2026-01-01T00:00:00Z",
    sources: [],
  } as MaterialDetail;
}

describe("NewsletterPreview CTA", () => {
  it("renders a link when cta_url is present", () => {
    render(
      <NewsletterPreview
        material={baseMaterial()}
        output={baseOutput({ cta_url: "https://example.com/demo" })}
      />,
    );
    const link = screen.getByRole("link", { name: /book a demo/i });
    expect(link).toHaveAttribute("href", "https://example.com/demo");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("renders non-link text when cta_url is absent", () => {
    render(<NewsletterPreview material={baseMaterial()} output={baseOutput()} />);
    expect(screen.queryByRole("link", { name: /book a demo/i })).toBeNull();
    expect(screen.getByText(/book a demo/i)).toBeInTheDocument();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { createTemplate } from "./templates";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("createTemplate", () => {
  it("POSTs the template body", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({
      data: { id: 2, slug: "product_spotlight" },
      error: undefined,
    } as never);
    const body = {
      name: "Product Spotlight",
      constraints: {
        headline_max_words: 8,
        subheadline_max_words: 20,
        body_section_count: 2,
        body_section_max_words: 80,
        cta_max_words: 12,
      },
      image_slots: [],
      theme: { primary_color: "#112233", accent_color: "#abcdef" },
    };
    const created = await createTemplate(body);
    expect(post).toHaveBeenCalledWith("/api/templates/", { body });
    expect(created.slug).toBe("product_spotlight");
  });

  it("throws on error", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { name: ["required"] },
    } as never);
    await expect(createTemplate({} as never)).rejects.toBeTruthy();
  });
});

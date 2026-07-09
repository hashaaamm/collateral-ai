import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createMaterial,
  deleteMaterial,
  isGenerating,
  regenerateMaterial,
} from "./materials";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("isGenerating", () => {
  it("is true for queued and processing, false for terminal states", () => {
    expect(isGenerating({ generation_status: "queued" })).toBe(true);
    expect(isGenerating({ generation_status: "processing" })).toBe(true);
    expect(isGenerating({ generation_status: "completed" })).toBe(false);
    expect(isGenerating({ generation_status: "failed" })).toBe(false);
  });
});

describe("createMaterial", () => {
  it("POSTs and returns the detail payload", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({
      data: { id: 9, generation_status: "queued" },
      error: undefined,
    } as never);
    const body = {
      title: "T",
      sender_company: 1,
      receiver_company: 2,
      template: 3,
      prompt: "p",
    };
    const material = await createMaterial(body);
    expect(post).toHaveBeenCalledWith("/api/materials/", { body });
    expect(material.id).toBe(9);
  });

  it("throws the DRF error body so forms can show field errors", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { receiver_company: ["Sender and receiver must be different companies."] },
    } as never);
    await expect(
      createMaterial({
        title: "T",
        sender_company: 1,
        receiver_company: 1,
        template: 3,
        prompt: "p",
      }),
    ).rejects.toHaveProperty("receiver_company");
  });
});

describe("regenerateMaterial / deleteMaterial", () => {
  it("POSTs the regenerate action", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({
      data: { id: 9, generation_status: "queued" },
      error: undefined,
    } as never);
    await regenerateMaterial(9);
    expect(post).toHaveBeenCalledWith("/api/materials/{id}/regenerate/", {
      params: { path: { id: 9 } },
    });
  });

  it("DELETEs the material", async () => {
    const del = vi
      .spyOn(api, "DELETE")
      .mockResolvedValue({ data: undefined, error: undefined } as never);
    await deleteMaterial(9);
    expect(del).toHaveBeenCalledWith("/api/materials/{id}/", {
      params: { path: { id: 9 } },
    });
  });
});

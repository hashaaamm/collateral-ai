import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchDashboardStats } from "./dashboard";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("fetchDashboardStats", () => {
  it("GETs /api/dashboard/stats/ and returns the counts", async () => {
    const get = vi.spyOn(api, "GET").mockResolvedValue({
      data: {
        companies_count: 6,
        documents_processed: 18,
        documents_processing: 2,
        materials_generated: 11,
        materials_needs_review: 3,
      },
      error: undefined,
    } as never);

    const stats = await fetchDashboardStats();

    expect(get).toHaveBeenCalledWith("/api/dashboard/stats/", {});
    expect(stats).toEqual({
      companies_count: 6,
      documents_processed: 18,
      documents_processing: 2,
      materials_generated: 11,
      materials_needs_review: 3,
    });
  });

  it("throws when the request errors", async () => {
    vi.spyOn(api, "GET").mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
    } as never);

    await expect(fetchDashboardStats()).rejects.toBeDefined();
  });
});

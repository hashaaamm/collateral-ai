import { describe, expect, it } from "vitest";
import { recentPillStatus } from "./dashboard";

describe("recentPillStatus", () => {
  it.each([
    // generation checked first, then review (spec §3 order)
    ["queued", "pending", "processing"],
    ["processing", "pending", "processing"],
    ["failed", "pending", "failed"],
    ["completed", "pending", "needs_review"],
    ["completed", "approved", "completed"],
    ["completed", "rejected", "completed"],
  ])("(%s, %s) -> %s", (generation, review, expected) => {
    expect(
      recentPillStatus({ generation_status: generation, review_status: review }),
    ).toBe(expected);
  });
});

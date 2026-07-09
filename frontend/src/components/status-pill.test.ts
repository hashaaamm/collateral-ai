import { describe, expect, it } from "vitest";
import { materialPillStatus } from "./status-pill";

describe("materialPillStatus", () => {
  it.each([
    ["queued", "pending", "processing"],
    ["processing", "pending", "processing"],
    ["failed", "pending", "failed"],
    ["completed", "pending", "needs_review"],
    ["completed", "approved", "approved"],
    ["completed", "rejected", "rejected"],
  ])("(%s, %s) -> %s", (generation, review, expected) => {
    expect(
      materialPillStatus({ generation_status: generation, review_status: review }),
    ).toBe(expected);
  });
});

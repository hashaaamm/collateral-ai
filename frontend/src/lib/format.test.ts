import { describe, expect, it } from "vitest";
import { formatRelativeDay } from "./format";

const now = new Date("2026-07-08T12:00:00");

describe("formatRelativeDay", () => {
  it("returns Today for the same calendar day", () => {
    expect(formatRelativeDay("2026-07-08T09:00:00", now)).toBe("Today");
  });

  it("returns Yesterday for the previous calendar day", () => {
    expect(formatRelativeDay("2026-07-07T23:00:00", now)).toBe("Yesterday");
  });

  it("counts yesterday across a late-night boundary", () => {
    const lateNow = new Date("2026-07-08T01:00:00");
    expect(formatRelativeDay("2026-07-07T23:00:00", lateNow)).toBe("Yesterday");
  });

  it("returns N days ago for 2-6 days", () => {
    expect(formatRelativeDay("2026-07-06T10:00:00", now)).toBe("2 days ago");
    expect(formatRelativeDay("2026-07-02T10:00:00", now)).toBe("6 days ago");
  });

  it("returns Last week for 7-13 days", () => {
    expect(formatRelativeDay("2026-07-01T10:00:00", now)).toBe("Last week");
    expect(formatRelativeDay("2026-06-25T10:00:00", now)).toBe("Last week");
  });

  it("returns a short date for 14+ days", () => {
    expect(formatRelativeDay("2026-06-24T10:00:00", now)).toBe("24 Jun");
  });
});

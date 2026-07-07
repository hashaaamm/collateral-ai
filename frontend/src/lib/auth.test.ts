import { beforeEach, describe, expect, it } from "vitest";
import { clearToken, getToken, isAuthenticated, setToken } from "./auth";

describe("auth token store", () => {
  beforeEach(() => localStorage.clear());

  it("reports no token initially", () => {
    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("persists and reads back a token", () => {
    setToken("abc123");
    expect(getToken()).toBe("abc123");
    expect(isAuthenticated()).toBe(true);
  });

  it("clears a stored token", () => {
    setToken("abc123");
    clearToken();
    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });
});

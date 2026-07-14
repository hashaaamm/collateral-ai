import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { enforceSession } from "./client";
import { getToken, setToken } from "@/lib/auth";

// enforceSession may navigate via window.location.href. jsdom's real Location
// can't be assigned, so swap in a plain stub we can assert against.
const realLocation = window.location;

function stubLocation(pathname: string) {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname, href: pathname },
  });
}

function res(status: number) {
  return new Response(null, { status });
}

beforeEach(() => localStorage.clear());

afterEach(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: realLocation,
  });
  localStorage.clear();
});

describe("enforceSession", () => {
  it("clears the token and redirects to /login on 401 when logged in", () => {
    setToken("stale");
    stubLocation("/dashboard");

    enforceSession(res(401));

    expect(getToken()).toBeNull();
    expect(window.location.href).toBe("/login");
  });

  it("does nothing on 401 when there is no token", () => {
    stubLocation("/dashboard");

    enforceSession(res(401));

    expect(window.location.href).toBe("/dashboard");
  });

  it("does not redirect when already on /login (avoids a loop)", () => {
    setToken("stale");
    stubLocation("/login");

    enforceSession(res(401));

    // Token still cleared, but no navigation away from /login.
    expect(getToken()).toBeNull();
    expect(window.location.href).toBe("/login");
  });

  it("ignores non-401 responses even with a token present", () => {
    setToken("good");
    stubLocation("/dashboard");

    enforceSession(res(403));
    enforceSession(res(200));
    enforceSession(res(500));

    expect(getToken()).toBe("good");
    expect(window.location.href).toBe("/dashboard");
  });
});

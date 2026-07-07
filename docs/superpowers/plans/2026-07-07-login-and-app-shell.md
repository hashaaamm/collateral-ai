# Login Page + App Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pixel-matched login page that authenticates against the Django backend, plus a sidebar app shell wrapping five empty placeholder pages, guarded so only logged-in users reach them.

**Architecture:** React SPA (TanStack Router) split into three route groups: the existing top-nav "marketing" shell (`/`, `/about`, untouched), a standalone `/login`, and a guarded app-shell layout (sidebar) containing `/dashboard`, `/companies`, `/create`, `/materials`, `/templates`. Auth uses DRF token auth: the login form POSTs to `/api/auth-token/`, the returned token is stored in `localStorage`, an openapi-fetch middleware attaches it as `Authorization: Token <token>`, and route `beforeLoad` guards redirect based on token presence.

**Tech Stack:** React 19, TanStack Router + Query, openapi-fetch, react-hook-form + zod (`@hookform/resolvers`), Tailwind v4 (design tokens via `@theme`), shadcn (`Button`, `Input`), `@phosphor-icons/react`, `@fontsource/hanken-grotesk`. Tests: Vitest (+ jsdom) for pure logic.

## Global Constraints

- Package manager is **pnpm**; run all frontend commands from `frontend/`.
- Path alias `@/*` → `frontend/src/*` (already configured in `vite.config.ts` and `tsconfig.json`).
- TypeScript is **strict** with `noUnusedLocals` and `noUnusedParameters` — no unused imports/vars/params.
- **No raw hex in JSX.** Use the namespaced design tokens (Task 1). One-off values with no token (e.g. the login radial gradient, the logo-tile drop shadow, odd pixel sizes) use Tailwind arbitrary values (`bg-[...]`, `shadow-[...]`, `text-[13.5px]`).
- Design token names are **namespaced** (`brand`, `page`, `ink`, `hairline`, …) to avoid colliding with shadcn's reserved token names (`accent`, `secondary`, `muted`, `border`, `input`, `primary`, …). Do **not** redefine shadcn's `--color-*` tokens.
- Backend login field is literally named `username` but carries the **email** value (`USERNAME_FIELD = "email"`).
- Login token localStorage key: `collateral_ai.token`.
- The prototype's "Authentication is mocked for the MVP…" info note is **omitted** (our auth is real).
- Every task ends with a commit. Do not push (branch `feat/login-page` is already checked out).
- All pixel values (colors, sizes, spacing) come from `docs/superpowers/specs/2026-07-07-login-and-app-shell-design.md` and the handoff README.

---

### Task 1: Dependencies, design tokens, and fonts

**Files:**
- Modify: `frontend/package.json` (dependencies)
- Modify: `frontend/src/index.css` (add `@theme` tokens + body font)
- Modify: `frontend/src/main.tsx` (import font weights)

**Interfaces:**
- Consumes: nothing.
- Produces: Tailwind utilities `bg-brand`, `hover:bg-brand-hover`, `bg-brand-soft`, `bg-brand-tint`, `text-brand`, `bg-page`, `bg-surface`, `bg-subtle`, `bg-rail`, `border-hairline`, `border-hairline-soft`, `border-field`, `hover:bg-nav-hover`, `text-ink`, `text-body`, `text-subtext`, `text-mute`, `text-faint`, `text-nav`, `shadow-login`, `font-sans`. Adds npm deps `@phosphor-icons/react`, `@fontsource/hanken-grotesk`, `@hookform/resolvers`.

- [ ] **Step 1: Install the runtime dependencies**

Run (from `frontend/`):
```bash
pnpm add @phosphor-icons/react @fontsource/hanken-grotesk @hookform/resolvers
```
Expected: the three packages appear under `dependencies` in `package.json` and `pnpm-lock.yaml` updates.

- [ ] **Step 2: Add the namespaced design-token block to `src/index.css`**

Insert this new block immediately **after** the existing `@import "tailwindcss";` line (before `@custom-variant`). It must not touch the existing `@theme inline` / `:root` shadcn blocks:

```css
/* Handoff design tokens (namespaced so they don't collide with shadcn's
   accent/secondary/muted/border/input token names). */
@theme {
  --font-sans: "Hanken Grotesk", system-ui, -apple-system, sans-serif;

  --color-brand: #5b5bd6;
  --color-brand-hover: #4f4fce;
  --color-brand-soft: #eef0fe;   /* nav active bg */
  --color-brand-tint: #eaeafb;   /* avatar tile bg */

  --color-page: #f6f6f8;
  --color-surface: #ffffff;
  --color-subtle: #fbfbfc;       /* input fill */
  --color-rail: #f7f7fb;         /* user card bg */

  --color-hairline: #ececef;         /* card / sidebar border */
  --color-hairline-soft: #eeeef4;    /* user card border */
  --color-field: #e4e4e9;            /* input border */
  --color-nav-hover: #f0f0f4;        /* nav item hover bg */

  --color-ink: #1a1a1e;          /* primary text */
  --color-body: #4a4a52;         /* form labels / body */
  --color-subtext: #77777f;      /* secondary text */
  --color-mute: #9a9aa5;         /* muted text / icons */
  --color-faint: #a8a8b0;        /* captions */
  --color-nav: #6b6b76;          /* inactive nav text */

  --shadow-login: 0 12px 40px -12px rgba(20, 20, 40, 0.12);
}
```

- [ ] **Step 3: Apply the UI font on `body`**

In `src/index.css`, in the existing `@layer base` block, add a `font-family` line to the `body` rule so it reads:

```css
  body {
    font-family: var(--font-sans);
    background-color: var(--background);
    color: var(--foreground);
  }
```

- [ ] **Step 4: Import the font weights in `src/main.tsx`**

Add these imports at the very top of `src/main.tsx` (before the existing imports):

```tsx
import "@fontsource/hanken-grotesk/400.css";
import "@fontsource/hanken-grotesk/500.css";
import "@fontsource/hanken-grotesk/600.css";
import "@fontsource/hanken-grotesk/700.css";
import "@fontsource/hanken-grotesk/800.css";
```

- [ ] **Step 5: Verify it typechecks and builds**

Run (from `frontend/`):
```bash
pnpm typecheck && pnpm build
```
Expected: both succeed with no errors (the build proves Tailwind compiles the new tokens and the font imports resolve).

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/src/index.css frontend/src/main.tsx
git commit -m "Add design tokens, Hanken Grotesk font, and login deps"
```

---

### Task 2: Auth token store (`src/lib/auth.ts`) — TDD

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/lib/auth.test.ts`
- Create: `frontend/vitest.config.ts`
- Modify: `frontend/package.json` (devDeps + `test` script)

**Interfaces:**
- Consumes: nothing.
- Produces: `getToken(): string | null`, `setToken(token: string): void`, `clearToken(): void`, `isAuthenticated(): boolean`. localStorage key `collateral_ai.token`.

- [ ] **Step 1: Install the test toolchain**

Run (from `frontend/`):
```bash
pnpm add -D vitest jsdom
```
Expected: `vitest` and `jsdom` appear under `devDependencies`.

- [ ] **Step 2: Create `frontend/vitest.config.ts`**

```ts
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  test: {
    environment: "jsdom",
  },
});
```

- [ ] **Step 3: Add the `test` script to `package.json`**

In `frontend/package.json`, add to `"scripts"`:
```json
    "test": "vitest run",
```

- [ ] **Step 4: Write the failing test — `frontend/src/lib/auth.test.ts`**

```ts
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
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `pnpm test`
Expected: FAIL — cannot resolve `./auth` (module does not exist yet).

- [ ] **Step 6: Implement `frontend/src/lib/auth.ts`**

```ts
/** Single source of truth for the DRF auth token in the browser. */
const TOKEN_KEY = "collateral_ai.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `pnpm test`
Expected: PASS — 3 tests green.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/vitest.config.ts frontend/src/lib/auth.ts frontend/src/lib/auth.test.ts
git commit -m "Add auth token store with Vitest coverage"
```

---

### Task 3: API auth middleware + login mutation + schema — TDD (schema)

**Files:**
- Modify: `frontend/src/lib/api/client.ts`
- Create: `frontend/src/lib/api/auth.ts`
- Create: `frontend/src/lib/api/auth.test.ts`

**Interfaces:**
- Consumes: `getToken`, `setToken` from `@/lib/auth`; `api` from `@/lib/api/client`; generated types from `@/lib/api/schema` (`AuthToken = { username: string; password: string; readonly token: string }`).
- Produces: `loginSchema` (zod object `{ email, password }`), `LoginValues = { email: string; password: string }`, `useLogin()` — a TanStack Query mutation whose `mutate(values, { onSuccess })` POSTs to `/api/auth-token/`, stores the token, and rejects with `Error("invalid_credentials")` on failure.

- [ ] **Step 1: Add the auth-header middleware to `frontend/src/lib/api/client.ts`**

Replace the entire file with:

```ts
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { getToken } from "@/lib/auth";

// Typed client generated from the backend OpenAPI schema (`pnpm gen:api`).
// Vite exposes build-time env as import.meta.env.VITE_*.
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  credentials: "include",
});

// Attach the DRF token to every request when the user is logged in.
const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set("Authorization", `Token ${token}`);
    return request;
  },
};

api.use(authMiddleware);
```

- [ ] **Step 2: Write the failing test — `frontend/src/lib/api/auth.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { loginSchema } from "./auth";

describe("loginSchema", () => {
  it("accepts a valid email and password", () => {
    expect(loginSchema.safeParse({ email: "a@b.com", password: "x" }).success).toBe(true);
  });

  it("rejects a malformed email", () => {
    expect(loginSchema.safeParse({ email: "not-an-email", password: "x" }).success).toBe(false);
  });

  it("rejects an empty password", () => {
    expect(loginSchema.safeParse({ email: "a@b.com", password: "" }).success).toBe(false);
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pnpm test`
Expected: FAIL — cannot resolve `./auth`.

- [ ] **Step 4: Implement `frontend/src/lib/api/auth.ts`**

```ts
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import type { components } from "./schema";
import { api } from "./client";
import { setToken } from "@/lib/auth";

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

export type LoginValues = z.infer<typeof loginSchema>;

/**
 * Log in via DRF's obtain_auth_token. The backend field is named `username`
 * but resolves against the email (USERNAME_FIELD = "email"). On success the
 * token is persisted; failure rejects so the form can show an inline error.
 */
export function useLogin() {
  return useMutation({
    mutationFn: async ({ email, password }: LoginValues) => {
      const { data, error } = await api.POST("/api/auth-token/", {
        // drf-spectacular lists the readonly `token` on the request body; we
        // only send username + password. AuthToken is assignable to this
        // narrower shape, so the cast is safe.
        body: { username: email, password } as components["schemas"]["AuthToken"],
      });
      if (error || !data) throw new Error("invalid_credentials");
      setToken(data.token);
      return data;
    },
  });
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pnpm test`
Expected: PASS — all schema tests green.

- [ ] **Step 6: Typecheck**

Run: `pnpm typecheck`
Expected: no errors (confirms the `AuthToken` body cast and middleware types are valid).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api/client.ts frontend/src/lib/api/auth.ts frontend/src/lib/api/auth.test.ts
git commit -m "Add auth header middleware and useLogin mutation"
```

---

### Task 4: Login page (`src/routes/login.tsx`) + shadcn Input

**Files:**
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/routes/login.tsx`

**Interfaces:**
- Consumes: `Button` from `@/components/ui/button`, `Input` from `@/components/ui/input`, `useLogin` / `loginSchema` / `LoginValues` from `@/lib/api/auth`, `useNavigate` from `@tanstack/react-router`, icons from `@phosphor-icons/react`.
- Produces: `LoginPage` (named export) — a self-contained full-screen login form. Navigates to `/dashboard` on success. Not yet routed (wired in Task 6).

- [ ] **Step 1: Create the shadcn `Input` primitive — `frontend/src/components/ui/input.tsx`**

```tsx
import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:border-destructive aria-invalid:ring-destructive/20",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
```

- [ ] **Step 2: Create the login page — `frontend/src/routes/login.tsx`**

The bordered field wrappers own the border/background/icon; the shadcn `Input` is stripped to a borderless field inside them (`border-0 bg-transparent shadow-none focus-visible:ring-0`).

```tsx
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  EnvelopeSimple,
  Eye,
  EyeSlash,
  LockSimple,
  Stack,
} from "@phosphor-icons/react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { loginSchema, useLogin, type LoginValues } from "@/lib/api/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => navigate({ to: "/dashboard" }),
    });
  });

  return (
    <div className="flex min-h-dvh items-center justify-center bg-[radial-gradient(120%_120%_at_50%_0%,#eeeefb_0%,#f6f6f8_55%)] p-6">
      <div className="w-full max-w-[400px]">
        {/* Logo lockup */}
        <div className="mb-[30px] flex items-center justify-center gap-[11px]">
          <div className="flex size-[34px] items-center justify-center rounded-[9px] bg-brand shadow-[0_4px_12px_rgba(91,91,214,0.35)]">
            <Stack weight="fill" size={19} className="text-white" />
          </div>
          <span className="text-[19px] font-bold tracking-[-0.02em] text-ink">
            Collateral AI
          </span>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-hairline bg-surface p-8 shadow-login">
          <h1 className="mb-1 text-[21px] font-bold tracking-[-0.02em] text-ink">
            Welcome back
          </h1>
          <p className="mb-6 text-sm text-subtext">
            Sign in to your marketing studio
          </p>

          <form onSubmit={onSubmit} noValidate>
            {/* Email */}
            <label
              htmlFor="email"
              className="mb-[7px] block text-[12.5px] font-semibold text-body"
            >
              Email
            </label>
            <div className="flex items-center gap-[9px] rounded-[10px] border border-field bg-subtle px-3">
              <EnvelopeSimple size={16} className="text-mute" />
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                className="h-auto border-0 bg-transparent px-0 py-[11px] text-sm shadow-none focus-visible:ring-0"
                {...register("email")}
              />
            </div>
            <p className="mt-1 min-h-[16px] text-xs text-destructive">
              {errors.email?.message ?? ""}
            </p>

            {/* Password */}
            <label
              htmlFor="password"
              className="mb-[7px] block text-[12.5px] font-semibold text-body"
            >
              Password
            </label>
            <div className="flex items-center gap-[9px] rounded-[10px] border border-field bg-subtle px-3">
              <LockSimple size={16} className="text-mute" />
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                className="h-auto border-0 bg-transparent px-0 py-[11px] text-sm shadow-none focus-visible:ring-0"
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="text-mute"
              >
                {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="mt-1 min-h-[16px] text-xs text-destructive">
              {errors.password?.message ?? ""}
            </p>

            {/* Server error */}
            {login.isError && (
              <p className="mb-3 text-sm text-destructive">
                Incorrect email or password
              </p>
            )}

            <Button
              type="submit"
              disabled={login.isPending}
              className="mt-1 flex h-auto w-full items-center justify-center gap-2 rounded-[10px] bg-brand py-3 text-[14.5px] font-semibold text-white hover:bg-brand-hover"
            >
              {login.isPending ? (
                "Signing in…"
              ) : (
                <>
                  Sign in <ArrowRight weight="bold" size={15} />
                </>
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck and lint**

Run (from `frontend/`): `pnpm typecheck && pnpm lint`
Expected: no errors (component compiles; no unused imports).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/input.tsx frontend/src/routes/login.tsx
git commit -m "Add pixel-matched login page and shadcn Input"
```

---

### Task 5: App shell + placeholder pages

**Files:**
- Create: `frontend/src/components/placeholder-page.tsx`
- Create: `frontend/src/components/app-shell.tsx`
- Create: `frontend/src/routes/dashboard.tsx`
- Create: `frontend/src/routes/companies.tsx`
- Create: `frontend/src/routes/create.tsx`
- Create: `frontend/src/routes/materials.tsx`
- Create: `frontend/src/routes/templates.tsx`

**Interfaces:**
- Consumes: `clearToken` from `@/lib/auth`, `useCurrentUser` from `@/lib/api/queries`, `Link` / `Outlet` / `useNavigate` from `@tanstack/react-router`, icons from `@phosphor-icons/react`.
- Produces: `AppShell` (named export, sidebar layout rendering `<Outlet/>`); `PlaceholderPage` (named export, `{ title: string }`); page components `DashboardPage`, `CompaniesPage`, `CreatePage`, `MaterialsPage`, `TemplatesPage` (named exports). All consumed by Task 6.

- [ ] **Step 1: Create the shared empty-state — `frontend/src/components/placeholder-page.tsx`**

```tsx
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <h1 className="text-[26px] font-bold tracking-[-0.03em] text-ink">
        {title}
      </h1>
      <div className="mt-6 rounded-2xl border border-dashed border-hairline bg-surface p-12 text-center text-sm text-mute">
        Coming soon
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create the five page components**

`frontend/src/routes/dashboard.tsx`:
```tsx
import { PlaceholderPage } from "@/components/placeholder-page";

export function DashboardPage() {
  return <PlaceholderPage title="Dashboard" />;
}
```

`frontend/src/routes/companies.tsx`:
```tsx
import { PlaceholderPage } from "@/components/placeholder-page";

export function CompaniesPage() {
  return <PlaceholderPage title="Companies" />;
}
```

`frontend/src/routes/create.tsx`:
```tsx
import { PlaceholderPage } from "@/components/placeholder-page";

export function CreatePage() {
  return <PlaceholderPage title="Create Material" />;
}
```

`frontend/src/routes/materials.tsx`:
```tsx
import { PlaceholderPage } from "@/components/placeholder-page";

export function MaterialsPage() {
  return <PlaceholderPage title="Marketing Requests" />;
}
```

`frontend/src/routes/templates.tsx`:
```tsx
import { PlaceholderPage } from "@/components/placeholder-page";

export function TemplatesPage() {
  return <PlaceholderPage title="Templates" />;
}
```

- [ ] **Step 3: Create the app shell — `frontend/src/components/app-shell.tsx`**

The nav list is data-driven; the active item uses TanStack Router `activeProps`. The user card reads `/api/users/me/` (via the existing `useCurrentUser`) for the name and derives initials, falling back gracefully when `name` is blank.

```tsx
import { Link, Outlet, useNavigate } from "@tanstack/react-router";
import {
  Buildings,
  Layout,
  ListChecks,
  MagicWand,
  SignOut,
  SquaresFour,
  Stack,
} from "@phosphor-icons/react";

import { useCurrentUser } from "@/lib/api/queries";
import { clearToken } from "@/lib/auth";

const NAV = [
  { to: "/dashboard", label: "Dashboard", Icon: SquaresFour },
  { to: "/companies", label: "Companies", Icon: Buildings },
  { to: "/create", label: "Create Material", Icon: MagicWand },
  { to: "/materials", label: "Marketing Requests", Icon: ListChecks },
  { to: "/templates", label: "Templates", Icon: Layout },
] as const;

const NAV_BASE =
  "flex items-center gap-[11px] rounded-[9px] px-[10px] py-[9px] text-[13.5px] font-medium";

function initials(name: string | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function AppShell() {
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const displayName = user?.name?.trim() ? user.name : "Account";

  function signOut() {
    clearToken();
    navigate({ to: "/login" });
  }

  return (
    <div className="flex min-h-dvh bg-page text-ink">
      <aside className="sticky top-0 flex h-dvh w-[236px] flex-none flex-col border-r border-hairline bg-surface">
        {/* Brand */}
        <div className="flex items-center gap-[10px] px-[18px] pb-[14px] pt-[18px]">
          <div className="flex size-[30px] items-center justify-center rounded-lg bg-brand">
            <Stack weight="fill" size={17} className="text-white" />
          </div>
          <span className="text-base font-bold tracking-[-0.02em]">
            Collateral AI
          </span>
          <span className="ml-auto rounded-[5px] border border-hairline px-[5px] py-[2px] text-[9.5px] font-semibold text-mute">
            MVP
          </span>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-[2px] px-3 py-[6px]">
          <div className="px-[10px] pb-[5px] pt-[10px] text-[10.5px] font-semibold uppercase tracking-[0.05em] text-faint">
            Workspace
          </div>
          {NAV.map(({ to, label, Icon }) => (
            // TanStack Router concatenates className with active/inactiveProps
            // className, so keep only shared classes here and only the
            // differing (state-specific) classes in the props below.
            <Link
              key={to}
              to={to}
              className={NAV_BASE}
              inactiveProps={{ className: "text-nav hover:bg-nav-hover" }}
              activeProps={{ className: "bg-brand-soft text-ink" }}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>

        {/* User card */}
        <div className="mt-auto p-3">
          <div className="rounded-xl border border-hairline-soft bg-rail p-3">
            <div className="flex items-center gap-[9px]">
              <div className="flex size-[30px] items-center justify-center rounded-lg bg-brand-tint text-[13px] font-bold text-brand">
                {initials(user?.name)}
              </div>
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold">
                  {displayName}
                </div>
                <div className="text-[11px] text-mute">Editor</div>
              </div>
              <button
                type="button"
                onClick={signOut}
                title="Sign out"
                aria-label="Sign out"
                className="ml-auto text-mute hover:text-brand"
              >
                <SignOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <main className="h-dvh flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Typecheck and lint**

Run (from `frontend/`): `pnpm typecheck && pnpm lint`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/placeholder-page.tsx frontend/src/components/app-shell.tsx frontend/src/routes/dashboard.tsx frontend/src/routes/companies.tsx frontend/src/routes/create.tsx frontend/src/routes/materials.tsx frontend/src/routes/templates.tsx
git commit -m "Add app shell sidebar and empty placeholder pages"
```

---

### Task 6: Router restructure, guards, and end-to-end verification

**Files:**
- Modify: `frontend/src/router.tsx` (full rewrite)

**Interfaces:**
- Consumes: `LoginPage`, `AppShell`, `DashboardPage`, `CompaniesPage`, `CreatePage`, `MaterialsPage`, `TemplatesPage`, `HomePage`, `AboutPage`, `isAuthenticated`.
- Produces: the wired route tree with guards. Terminal deliverable — the full flow works in the browser.

- [ ] **Step 1: Rewrite `frontend/src/router.tsx`**

```tsx
import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
  Outlet,
  Link,
} from "@tanstack/react-router";

import { isAuthenticated } from "@/lib/auth";
import { HomePage } from "@/routes/home";
import { AboutPage } from "@/routes/about";
import { LoginPage } from "@/routes/login";
import { AppShell } from "@/components/app-shell";
import { DashboardPage } from "@/routes/dashboard";
import { CompaniesPage } from "@/routes/companies";
import { CreatePage } from "@/routes/create";
import { MaterialsPage } from "@/routes/materials";
import { TemplatesPage } from "@/routes/templates";

/** Bare root — each group provides its own chrome (or none). */
const rootRoute = createRootRoute({ component: () => <Outlet /> });

/** Existing marketing shell (top nav) — unchanged public pages. */
const marketingRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "marketing",
  component: function MarketingLayout() {
    return (
      <div className="min-h-dvh bg-background text-foreground">
        <header className="border-b">
          <nav className="mx-auto flex max-w-3xl items-center gap-4 px-4 py-3 text-sm">
            <Link to="/" className="font-semibold [&.active]:underline">
              {"Collateral AI"}
            </Link>
            <Link to="/about" className="[&.active]:underline">
              About
            </Link>
          </nav>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">
          <Outlet />
        </main>
      </div>
    );
  },
});

const indexRoute = createRoute({
  getParentRoute: () => marketingRoute,
  path: "/",
  component: HomePage,
});

const aboutRoute = createRoute({
  getParentRoute: () => marketingRoute,
  path: "/about",
  component: AboutPage,
});

/** Standalone login. Logged-in users skip straight to the dashboard. */
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  beforeLoad: () => {
    if (isAuthenticated()) throw redirect({ to: "/dashboard" });
  },
  component: LoginPage,
});

/** Guarded app shell (sidebar). Anonymous users are sent to login. */
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: () => {
    if (!isAuthenticated()) throw redirect({ to: "/login" });
  },
  component: AppShell,
});

const dashboardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/dashboard",
  component: DashboardPage,
});
const companiesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies",
  component: CompaniesPage,
});
const createMaterialRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/create",
  component: CreatePage,
});
const materialsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/materials",
  component: MaterialsPage,
});
const templatesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/templates",
  component: TemplatesPage,
});

const routeTree = rootRoute.addChildren([
  marketingRoute.addChildren([indexRoute, aboutRoute]),
  loginRoute,
  appRoute.addChildren([
    dashboardRoute,
    companiesRoute,
    createMaterialRoute,
    materialsRoute,
    templatesRoute,
  ]),
]);

export const router = createRouter({ routeTree });

// Register the router instance for full type-safety across the app.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
```

- [ ] **Step 2: Typecheck, lint, and full test run**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm test && pnpm build`
Expected: all pass.

- [ ] **Step 3: Start the local stack**

Run (from repo root):
```bash
just up
```
Expected: `django` (`:8000`), `postgres`, and `frontend` (`:3000`) containers start. Tail logs with `just logs` if needed until the frontend prints its Vite URL and Django is serving.

- [ ] **Step 4: Create a test user**

Run (from repo root):
```bash
just createsuperuser
```
Enter an email (e.g. `editor@collate.ai`) and a password when prompted. (Token auth bypasses email verification, so a superuser is the quickest valid login.)

- [ ] **Step 5: Manual browser smoke test**

Open `http://localhost:3000/login` and verify each:
- [ ] The login page matches the design (centered card on the purple radial gradient, brand logo lockup, "Welcome back", email + password fields with leading icons, password eye-toggle works, purple "Sign in →" button).
- [ ] Submitting an **invalid** email format shows the inline field error; empty password shows its field error.
- [ ] Submitting **wrong** credentials shows "Incorrect email or password" and stays on `/login`.
- [ ] Submitting the **correct** credentials lands on `/dashboard` inside the sidebar shell; the user card shows the derived initials + name.
- [ ] Clicking each nav item (Companies, Create Material, Marketing Requests, Templates, Dashboard) routes to its "Coming soon" page and highlights that item (`bg-brand-soft`).
- [ ] Refreshing the browser on `/dashboard` keeps you authenticated (no bounce to login).
- [ ] Visiting `/login` while logged in redirects to `/dashboard`.
- [ ] Clicking the sidebar sign-out icon returns to `/login`; then manually visiting `/dashboard` redirects back to `/login`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/router.tsx
git commit -m "Wire login + guarded app-shell routes"
```

---

## Notes for the implementer

- If `pnpm gen:api` is ever re-run, the `AuthToken`/`User` schema types are regenerated; the `useLogin` body cast and `useCurrentUser` shape depend only on `username`/`password`/`token` and `name`, which are stable.
- The design's richer screens (real dashboard content, tables, wizard, result detail) and the mono font are intentionally **out of scope** — every non-login page is a placeholder here.

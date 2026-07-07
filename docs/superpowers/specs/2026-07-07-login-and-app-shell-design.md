# Login Page + App Shell — Design

Date: 2026-07-07
Status: Approved

## Goal

Implement a pixel-matched **login page** and the **sidebar app shell** from the
design handoff (`mvp-frontend-architecture/project/Collate.dc.html`). Only the
login page is wired to the backend; every other destination is an empty
placeholder page that lives inside the shell. No signup, no forgot-password, no
email-verification flow.

## Backend facts (already exist — do not change)

- Login: `POST /api/auth-token/` with body `{ "username": "<email>", "password": "<pw>" }`
  returns `{ "token": "<token>" }`. This is DRF's `obtain_auth_token`; the field
  is named `username` but the backend resolves it against the email field because
  `USERNAME_FIELD = "email"`.
- Authenticated requests send header `Authorization: Token <token>`.
- Current user: `GET /api/users/me/` → `{ "name": "...", "url": "..." }`.
- CORS already allows `http://localhost:3000` with credentials.
- DRF default permission is `IsAuthenticated`; auth classes are Session + Token.

## Frontend stack (already present)

React 19 + Vite, TanStack Router, TanStack Query, `openapi-fetch` typed client,
Tailwind v4, shadcn (`button`, `card`), `react-hook-form` + `zod` (installed,
currently unused).

New dependencies to add (per the handoff README's recommended stack):
- `@phosphor-icons/react` — tree-shaken per-icon imports (replaces the prototype's
  CDN icon web-font).
- `@fontsource/hanken-grotesk` — self-hosted UI font (weights 400/500/600/700/800).
- shadcn `input` component (via the shadcn CLI) for the login form fields.

(`@fontsource/jetbrains-mono` and other shadcn primitives — Tabs, Dialog, Avatar —
are deferred to the later data-heavy screens; not needed for login + shell.)

## Scope

1. Pixel-matched login page at `/login` (standalone, no sidebar).
2. Pixel-matched sidebar app shell wrapping all authenticated pages, including the
   bottom user card with a **Sign out** action.
3. Five empty placeholder pages, one per nav item, using the design's exact names:

   | Nav label          | Phosphor icon      | Route         |
   |--------------------|--------------------|---------------|
   | Dashboard          | `ph-squares-four`  | `/dashboard`  |
   | Companies          | `ph-buildings`     | `/companies`  |
   | Create Material    | `ph-magic-wand`    | `/create`     |
   | Marketing Requests | `ph-list-checks`   | `/materials`  |
   | Templates          | `ph-layout`        | `/templates`  |

   Each page body is an empty state: page title + a "Coming soon" placeholder.

Out of scope: signup, password reset, the design's real dashboard/companies/create
content, any backend changes.

## Auth flow

1. User enters email + password and submits.
2. Client calls `POST /api/auth-token/` with `{ username: <email>, password }`.
3. Success: save `token` to `localStorage` (key `collateral_ai.token`), then
   navigate to `/dashboard`.
4. Failure (400 / invalid credentials): show an inline error under the form
   ("Incorrect email or password"); no redirect. Network/other errors show a
   generic "Something went wrong" message.
5. The `openapi-fetch` client gets a request middleware that reads the token via
   `getToken()` and, when present, sets `Authorization: Token <token>` on every
   request.
6. Sign out clears the token and navigates to `/login`.

## Routing structure

The current router wraps every route in a top-nav shell. We split the tree:

- **Standalone (no chrome):** `/login`.
- **App shell layout** (sidebar) → `/dashboard`, `/companies`, `/create`,
  `/materials`, `/templates`. All guarded.
- **Existing top-nav shell** keeps `/` and `/about`, untouched.

Guards:
- App-shell routes: if `!isAuthenticated()`, redirect to `/login`.
- `/login`: if `isAuthenticated()`, redirect to `/dashboard`.

The active sidebar nav item is derived from the current route (TanStack Router
active-link matching).

## Components / files

- `src/lib/auth.ts` — token helpers: `getToken()`, `setToken(t)`, `clearToken()`,
  `isAuthenticated()`. Single source of truth for the localStorage key.
- `src/lib/api/client.ts` — add a request middleware that injects the
  `Authorization` header from `getToken()`.
- `src/lib/api/auth.ts` — `useLogin()` TanStack Query mutation calling
  `/api/auth-token/`. Reuse existing `useCurrentUser()` (`/api/users/me/`) for the
  sidebar user card.
- `src/routes/login.tsx` — pixel-matched login screen. Form via `react-hook-form`
  + `zod` (email format + non-empty password), using shadcn `Input` + `Button`
  (themed to the tokens) for the fields/submit. Local state for the password
  eye-toggle and submit/loading/error.
- `src/components/app-shell.tsx` — pixel-matched sidebar + `<Outlet/>`. Renders the
  logo + "MVP" badge, the "Workspace" nav list, and the bottom user card
  (name + derived initials from `/api/users/me/`; role label "Editor" as in the
  design; graceful fallback if `name` is blank) with the sign-out button.
- `src/routes/dashboard.tsx`, `companies.tsx`, `create.tsx`, `materials.tsx`,
  `templates.tsx` — empty placeholder pages (title + "Coming soon").
- `src/router.tsx` — restructured route tree (standalone vs app-shell vs existing
  top-nav) + the two guards.
- `src/index.css` — import `@fontsource/hanken-grotesk` weights, and adopt the
  handoff README's `@theme` token palette (the subset the login + shell need now,
  structured so the rest drops in later): `--font-sans`, `--color-accent` /
  `--color-accent-hover` / `--color-accent-soft` / `--color-accent-tint`,
  `--color-page`, `--color-surface`, `--color-rail`, `--color-border` /
  `--color-border-soft`, `--color-input`, `--color-ink` / `--color-body` /
  `--color-secondary` / `--color-muted` / `--color-faint`, and `--shadow-login`.
  Set `font-sans` + `bg-page text-ink` on the app root.

## Styling approach

Tailwind-token-first, using shadcn selectively. Both compose cleanly because
shadcn is itself Radix + Tailwind.

1. **Token layer (foundation):** adopt the handoff README's `@theme` palette in
   `index.css` (accent, surfaces, text ramp, shadows, font). Components reference
   named tokens (`bg-accent`, `text-ink`, `border-border`, `shadow-login`) — no raw
   hex in JSX.
2. **Bespoke layouts via Tailwind:** the login card, 236px sidebar, nav items, and
   user card are too custom to force through shadcn — build them with Tailwind
   utilities driven by the tokens. Odd pixel values (`13.5px`, `9px 10px`) use
   Tailwind arbitrary values where exactness matters.
3. **shadcn primitives where they help:** `Button` + `Input` for the login form,
   themed to the tokens. Richer shadcn primitives (Tabs/Card/Dialog/Avatar) are
   deferred to the later data-heavy screens, not used for login + shell.

The prototype's login "Authentication is mocked for the MVP…" info note is
**omitted** — our auth is real, so the note would be inaccurate.

## Visual fidelity (pixel-match)

Values taken directly from the handoff source.

Login:
- Full-screen centered layout, radial-gradient background
  `radial-gradient(120% 120% at 50% 0%, #eeeefb 0%, #f6f6f8 55%)`, 24px padding.
- Card: `max-width:400px`, white, `border:1px solid #ececef`, `border-radius:16px`,
  `padding:32px`, `box-shadow:0 12px 40px -12px rgba(20,20,40,.12)`.
- Logo lockup: 34px purple (`#5b5bd6`) rounded square with white `ph-fill ph-stack`
  icon + "Collateral AI" (19px/700).
- Heading "Welcome back" (21px/700), subtitle "Sign in to your marketing studio"
  (14px, `#77777f`).
- Fields: label 12.5px/600 `#4a4a52`; input row with leading Phosphor icon
  (`ph-envelope-simple`, `ph-lock-simple`), `border:1px solid #e4e4e9`,
  `border-radius:10px`, background `#fbfbfc`; password row has trailing eye toggle
  (`ph-eye` / `ph-eye-slash`).
- Button: full-width, `#5b5bd6` (hover `#4f4fce`), white, 14.5px/600,
  `border-radius:10px`, label "Sign in" + `ph-bold ph-arrow-right`.

App shell:
- Sidebar `width:236px`, white, `border-right:1px solid #ececef`, sticky full
  height.
- Header: 30px purple rounded square + `ph-fill ph-stack`, "Collateral AI"
  (16px/700), "MVP" badge (9.5px/600, `#9a9aa5`, bordered).
- Nav section label "Workspace" (10.5px/600 uppercase, `#a8a8b0`).
- Nav item base: flex, gap 11px, padding `9px 10px`, `border-radius:9px`,
  13.5px/500. Inactive: color `#6b6b76`, transparent. Active: color `#1a1a1e`,
  background `#eef0fe`. Hover (inactive): background `#f0f0f4`.
- Bottom user card: `#f7f7fb` panel, `border:1px solid #eeeef4`,
  `border-radius:12px`; 30px avatar (`#eaeafb` bg, `#5b5bd6` text) with initials,
  name (13px/600), role "Editor" (11px, `#9a9aa5`), and a sign-out icon button
  (`ph-sign-out`, `#9a9aa5`, hover `#5b5bd6`).
- Main content area: `flex:1`, `overflow-y:auto`, background `#f6f6f8`.

Fonts/icons: Hanken Grotesk via `@fontsource/hanken-grotesk`; Phosphor icons via
`@phosphor-icons/react` (per-icon imports, `weight="regular|bold|fill"` to match
each glyph). Icons needed for login + shell: `Stack` (fill), `EnvelopeSimple`,
`LockSimple`, `Eye` / `EyeSlash`, `ArrowRight` (bold), `SquaresFour`, `Buildings`,
`MagicWand`, `ListChecks`, `Layout`, `SignOut`, `Info`.

## Testing

Manual browser smoke test against the running local stack (frontend + backend):
- Valid credentials → lands on `/dashboard` with the sidebar shell.
- Invalid credentials → inline error, stays on `/login`.
- Refresh on an app-shell route → stays authenticated (token persisted).
- Visiting an app-shell route with no token → redirect to `/login`.
- Visiting `/login` with a token → redirect to `/dashboard`.
- Each nav item routes to its page and highlights as active.
- Sign out → clears token, returns to `/login`; app-shell routes no longer reachable.

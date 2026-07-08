# CODING AGENTS: READ THIS FIRST

This is a **handoff bundle** from Claude Design (claude.ai/design).

A user mocked up designs in HTML/CSS/JS using an AI design tool, then exported this bundle so a coding agent can implement the designs for real.

## What you should do — IMPORTANT

**Read `mvp-frontend-architecture/project/Collate.dc.html` in full.** The user had this file open when they triggered the handoff, so it's almost certainly the primary design they want built. Read it top to bottom — don't skim. Then **follow its imports**: open every file it pulls in (shared components, CSS, scripts) so you understand how the pieces fit together before you start implementing.

**If anything is ambiguous, ask the user to confirm before you start implementing.** It's much cheaper to clarify scope up front than to build the wrong thing.

## About the design files

The design medium is **HTML/CSS/JS** — these are prototypes, not production code. Your job is to **recreate them pixel-perfectly** in whatever technology makes sense for the target codebase (React, Vue, native, whatever fits). Match the visual output; don't copy the prototype's internal structure unless it happens to fit.

**Don't render these files in a browser or take screenshots unless the user asks you to.** Everything you need — dimensions, colors, layout rules — is spelled out in the source. Read the HTML and CSS directly; a screenshot won't tell you anything they don't.

## Bundle contents

- `mvp-frontend-architecture/README.md` — this file
- `mvp-frontend-architecture/project/` — the `MVP Frontend Architecture` project files (HTML prototypes, assets, components)


# Handoff: Collateral AI — GenAI Marketing Collateral Studio

## Overview
Collateral AI is the frontend for an automated B2B marketing-collateral pipeline. A user uploads
context PDFs for a **Sender** company (the one pitching) and a **Receiver** company (the
target), then generates a tailored, factually-grounded newsletter article. The system's core
output is a **structured JSON** that maps generated copy into a predefined layout template
while respecting constraints (word limits, image slots, theme colors). The UI makes that
pipeline legible: company context management, PDF processing status, a generation wizard, a
task dashboard, and a review screen that shows the human-readable preview, the raw layout JSON,
the grounding sources, and validation checks side by side.

This is the **frontend design only**. The backend (PDF ingestion, retrieval, LLM orchestration,
layout formatting, cloud architecture) is out of scope for this package.

## About the Design Files
The file in this bundle — `Collate.dc.html` — is a **design reference created in HTML**. It is a
prototype demonstrating intended look, layout, and interaction, **not production code to copy
directly**. It is authored in a proprietary "Design Component" format (a custom `<x-dc>` runtime
with inline styles and a small logic class) — do **not** try to ship or import this file.

Your task is to **recreate these designs in the target codebase's environment** using its
established patterns and libraries. **Build this with React + Tailwind CSS + shadcn/ui** — that
is the intended stack for this project, and the whole design was authored to map onto shadcn's
primitives. Two full sections below give you (1) the Tailwind theme config and (2) a
component-by-component **shadcn mapping** for every screen element, plus the exact CSS-variable
theme. Follow them: reach for the shadcn component named for each element rather than hand-rolling
buttons, tables, tabs, dialogs, selects, comboboxes, etc. Use a router (React Router / TanStack
Router) for the routes listed near the end. All visual values needed to rebuild pixel-perfectly
are documented below, so you should not need to open the HTML to read styles — but it's included
as a runnable visual reference.

> **TL;DR for the implementer:** scaffold with `npx shadcn@latest init`, add the components from
> the `npx shadcn add …` line in the shadcn section, paste in the theme variables, then build each
> screen using the mapping. Keep Phosphor icons (don't swap to lucide). Adjust the mapping only
> where your codebase already has an equivalent primitive.

## Fidelity
**High-fidelity (hifi).** Final colors, typography, spacing, and interaction states are all
specified. Recreate the UI pixel-perfectly using the codebase's libraries. The one deliberate
placeholder is imagery: image areas use striped placeholders with monospace filename labels
(e.g. `hero_image.png`, `acme_logo.svg`) — wire these to real asset slots.

---

## Global Layout & Shell

Two top-level states:
1. **Login** — full-screen centered card, no app chrome.
2. **App** — a fixed **236px sidebar** (left) + scrollable **main** content area.

### Sidebar (persistent, `width: 236px`, `background: #ffffff`, `border-right: 1px solid #ececef`, sticky full-height)
- **Top:** 30×30 logo tile (`border-radius: 8px`, `background: #5b5bd6`, white stack glyph) + wordmark "Collateral AI" (`16px / 700 / letter-spacing -0.02em`) + a small `MVP` pill (`9.5px / 600`, `#9a9aa5`, 1px border).
- **Nav** (`padding: 6px 12px`): a "WORKSPACE" caption (`10.5px / 600`, uppercase, letter-spacing `.05em`, `#a8a8b0`), then 5 nav items. Each nav item: `display:flex; gap:11px; padding:9px 10px; border-radius:9px; font:13.5px/500`. **Active** item: `color:#1a1a1e; background:#eef0fe`. **Inactive:** `color:#6b6b76; background:transparent`. **Hover** (inactive): `background:#f0f0f4`. Each has a Phosphor icon at 18px.
  - Dashboard (`squares-four`), Companies (`buildings`), Create Material (`magic-wand`), Marketing Requests (`list-checks`), Templates (`layout`).
- **Bottom (mt-auto):** user card in a `#f7f7fb` rounded box — 30×30 avatar tile `#eaeafb`/`#5b5bd6` initials "JP", name "Julie Plusquin" (`13px/600`), role "Editor" (`11px/#9a9aa5`), and a sign-out icon button (`sign-out`) that returns to Login.

### Main content
Scrollable, `height:100vh; overflow-y:auto`. Each screen wraps in a centered container
(`max-width` varies per screen: 1080px for lists/detail, 820px for the wizard, 1120px for the
result screen) with `padding: ~32px 40px 60px`.

---

## Screens / Views

### 1. Login
- **Purpose:** Sign in. Auth is mocked for the MVP.
- **Layout:** Full viewport, centered. Background: `radial-gradient(120% 120% at 50% 0%, #eeeefb 0%, #f6f6f8 55%)`. Content column `max-width: 400px`.
- **Components:**
  - Logo lockup (tile + "Collateral AI") centered above the card, `margin-bottom: 30px`.
  - Card: `background:#fff; border:1px solid #ececef; border-radius:16px; padding:32px; box-shadow:0 12px 40px -12px rgba(20,20,40,.12)`.
  - Heading "Welcome back" (`21px/700`), subtext "Sign in to your marketing studio" (`14px/#77777f`).
  - Two labeled inputs (Email prefilled `editor@collate.ai`, Password prefilled dots). Input wrapper: `border:1px solid #e4e4e9; border-radius:10px; background:#fbfbfc; padding:0 12px`, leading Phosphor icon (`envelope-simple`, `lock-simple`) in `#9a9aa5`; password has a trailing `eye` icon.
  - Primary button "Sign in" + `arrow-right`: full width, `background:#5b5bd6; color:#fff; 14.5px/600; padding:12px; border-radius:10px`. Hover `#4f4fce`. **Clicking it navigates to Dashboard.**
  - *(No auth/roles note — the card ends at the Sign in button. Auth is still mocked for the MVP; the architecture supports future admin/editor/reviewer roles, just not surfaced on this screen.)*

### 2. Dashboard (`/dashboard`)
- **Purpose:** Landing overview.
- **Layout:** `max-width:1080px`. Greeting block, then a 4-column stat grid (`gap:16px`), then a 2-column row (`1.6fr / 1fr`, `gap:20px`).
- **Components:**
  - Date eyebrow "Wednesday, July 6" (`13px/#9a9aa5`) + "Good morning, Julie" (`26px/700/-0.03em`).
  - **4 stat cards** (`background:#fff; border:1px solid #ececef; border-radius:14px; padding:18px`): each has a label (`12.5px/#77777f`) + Phosphor icon top-right (`#b7b7c0`), a big number (`27px/700`), and a delta line. Values: Companies **6** (+2 this week, green), Documents processed **18** (2 processing, muted), Materials generated **11** (+4 this week, green), Needs review **2** (Awaiting approval, amber `#b45309`).
  - **Recent materials card** (left): header "Recent materials" + "View all" link (→ Marketing Requests). A borderless table of 4 rows; each row: title (`13px/600`) + "Sender → Receiver" subline (`11.5px/#9a9aa5`) and a right-aligned status pill. Rows are clickable → Result Detail. Row hover `background:#fafafb`.
  - **Quick start card** (right): heading "Quick start" + one line of copy, then a "Create Material" primary button (→ wizard) + "Manage Companies" ghost button (→ Companies). *(No pipeline-health list — it was removed.)*

### 3. Companies (`/companies`)
- **Purpose:** Manage reusable company context.
- **Layout:** `max-width:1080px`. Header row (title + "Create Company" primary button → **Create Company** screen), a search+filter row, then a table card.
- **Components:**
  - Title "Companies" (`24px/700`) + subtitle "Reusable company context — profiles and documents shared across every generation."
  - Search input (full-width, `magnifying-glass` icon, placeholder "Search companies…") + "Industry" filter button (`funnel` icon, ghost style).
  - **Table** (`background:#fff; border:1px solid #ececef; border-radius:14px`): header row `background:#fbfbfc`, column captions `11px/600` uppercase `#a8a8b0`. Columns: **Company | Industry | Documents | Last updated | (chevron)**. Each Company cell = 32×32 colored initial tile + name (`600`). Rows clickable → Company Detail, hover `#fafafb`, trailing `caret-right`.
  - Rows: Acme AI (AI Software, 3 PDFs, Today, tile `#eaeafb`/`#5b5bd6`), DHL Logistics (Logistics, 5 PDFs, Yesterday, `#fdeede`/`#c2710c`), RetailCo (Retail, 2 PDFs, `#e6f6ee`/`#0f8a4d`), CloudSec (Cybersecurity, 4 PDFs, `#e9edfb`/`#3457c9`), NordFinance (Financial Services, 4 PDFs, `#f3eafc`/`#8b3ecc`).

### 3b. Create Company (`/companies/new`)
- **Purpose:** Add a new company profile. Reached from the "Create Company" button on the Companies screen.
- **Layout:** `max-width:760px`. Breadcrumb (Companies / New company), title "Create Company" (`24px/700`) + subtitle "Add a company profile. Upload documents next — the AI fills in the rest from them.", a single form card, then a right-aligned action footer.
- **Form card** (`background:#fff; border:1px solid #ececef; border-radius:16px; padding:26px`):
  - *Logo row* (top, divided below): 56×56 placeholder tile (`#f2f2f6`, `buildings` icon) + "Upload logo" ghost button + hint "SVG or PNG, at least 128×128".
  - *Field grid* (2-col, `gap:18px 20px`): **Company name** (required, `*` in `#dc4b3e`, placeholder "e.g. Acme AI"), **Website** (globe-prefixed input, placeholder "acme.ai"), **Industry** (select, "Select industry"), **Tone of voice** (select, "Professional"), **Description** (full-width textarea, 2 rows), **Products / services** (full-width input, "Comma-separated…"), **Brand colors** (two swatches `#5b5bd6`/`#0f172a` + a dashed `+` add-swatch button), **Target customers** (input). Inputs use `border:1px solid #e4e4e9; border-radius:10px; background:#fbfbfc`.
  - *AI hint strip* (bottom, `background:#f4f4fd; border:1px solid #e6e6fb`): `sparkle` icon + "Leave fields blank if unsure — after you upload documents, Collateral AI can auto-fill the profile and generate a company summary."
- **Footer:** "Cancel" ghost button (→ Companies) + "Create & upload documents" primary button with `arrow-right` (→ Company Detail, in production create then route to its Documents tab).

### 4. Company Detail (`/companies/:companyId`)
- **Purpose:** View/manage one company's profile, documents, and generation history.
- **Layout:** `max-width:1080px`. Breadcrumb (Companies / Acme AI), header block, tab bar, then tab content.
- **Header:** 56×56 rounded initial tile, name "Acme AI" (`23px/700`) + industry pill (`#eef0fe`/`#5b5bd6`), website link (`globe` icon "acme.ai"). Right side: "Upload Documents" ghost button + "Generate Material" primary button (→ wizard).
- **Tab bar:** underline tabs — **Overview / Documents / Generated Materials**. Active tab `color:#1a1a1e; border-bottom:2px solid #5b5bd6`; inactive `#8a8a92`.

  **Overview tab** — 2-col grid (`1.5fr / 1fr`):
  - *AI company summary card* (left, tinted `linear-gradient(180deg,#f6f6ff,#fbfbff); border:1px solid #e6e6fb`): `sparkle` icon + "AI company summary" + "Generated from 3 documents" chip + "Regenerate" link. Body paragraph describing Acme AI (`13.5px/1.65`).
  - *Company profile card* (left): 2-col field grid — Website, Industry, Description (full width), Products/services, Target customers, Tone of voice, Brand colors (3 swatches: `#5b5bd6`, `#0f172a`, `#f1f5f9`). Field labels `11px/600` uppercase `#a8a8b0`, values `13.5px/#2f2f38`.
  - *Right rail card:* "Logo" striped placeholder (`acme_logo.svg`) + "Context readiness" checklist (3 green items).

  **Documents tab:**
  - Dashed dropzone (`border:1px dashed #cfcfe4; background:#fafafe`): `upload-simple` tile, "Drop PDFs here or **browse**", "Text, images and tables are extracted automatically · max 50 MB".
  - Table columns: **File name | Type | Pages | Chunks | Tables | Images | Status | (actions)** (Pages/Chunks/Tables/Images center-aligned). File cell = red `file-pdf` icon + name + "Uploaded … · time" subline. **Actions column** (right, per row): an **open-in-new-tab** icon button (`arrow-square-out`, hover accent) and a **delete** icon button (`trash`, hover red). Open → fetch a signed GCS URL then open the PDF in a new tab; Delete → opens the confirm-delete dialog below. Rows: `company-profile.pdf` (Profile, 12/48/3/6, **Processed** green), `case-study.pdf` (Case Study, 8/—/—/—, **Processing** amber), `annual-report.pdf` (Report, —, **Failed** red). Unavailable numeric cells show "—" in `#9a9aa5`.
  - **Confirm-delete dialog** (`AlertDialog`): dimmed backdrop + centered card (`max-width:400px`, `radius:16px`) with a red trash icon chip, "Delete document?" title, a cascade warning ("*&lt;file&gt;* and all its extracted chunks, tables and images will be permanently removed. This can't be undone."), and Cancel / destructive Delete buttons. Backdrop or Cancel dismisses.

  **Generated Materials tab** — 2 columns:
  - *As Sender* (icon tile `#eef0fe`/`#5b5bd6`, `arrow-up-right`): "AI for Smarter Logistics" (→ DHL, Completed), "Predictive Demand Planning" (→ RetailCo, Processing).
  - *As Receiver* (icon tile `#f1eafe`/`#7c3aed`, `arrow-down-left`): "Secure AI Infrastructure" (CloudSec →, Needs Review).
  - Each is a clickable card (`border:1px solid #f0f0f2; border-radius:11px; padding:13px`), hover `border-color:#d8d8f2; background:#fbfbff`, → Result Detail.

### 5. Create Material (`/materials/new`)
- **Purpose:** 4-step wizard to configure and launch a generation.
- **Layout:** `max-width:820px`. Title + subtitle, a step indicator, a content card (`min-height:300px`), then Back/Continue footer.
- **Step indicator:** 4 numbered 30px circles connected by 2px lines. Completed/current circle `background:#5b5bd6; color:#fff`; future `#ececf0`/`#a8a8b0`. Completed steps show a `check` glyph instead of the number. Connector turns `#5b5bd6` once passed. Labels under each: Companies, Template, Prompt, Generate.
- **Step 1 — Select companies:** two **search-based pickers** (Sender / Receiver) side by side — this replaced the earlier dropdowns for scalability. Each is a search `Input` (`magnifying-glass` icon, placeholder "Search companies…") above a bordered result list (`border:1px solid #ececef; border-radius:12px`). Each result row = avatar tile + name + "industry · N docs". The **selected** row has `background:#f4f4fd` + a `3px solid #5b5bd6` left border + a filled `check-circle` (`#5b5bd6`) on the right; other rows hover to `#fafafb`. Prefilled state: Sender search "Acme" with Acme AI selected (+ NordFinance listed); Receiver search "DHL" with DHL Logistics selected (+ RetailCo listed). Below, an info strip: "Acme AI is pitching to DHL Logistics — grounding will draw from both companies' documents."
- **Step 2 — Select template:** grid of template cards. **Newsletter Article** selected (`border:1.5px solid #5b5bd6`, checkmark badge top-right) with constraint list: Headline ≤10 words, Subheadline ≤22 words, Body 2 sections ≤80 words each, CTA ≤15 words, Hero image + sender logo. A second dashed "Brochure (Tri-fold)" card is disabled ("Coming soon", `opacity:.65`).
- **Step 3 — Campaign goal:** Prompt textarea (prefilled: "Generate a short B2B article about how Acme AI can help DHL improve warehouse efficiency and reduce manual planning."). Optional fields grid: **Tone** chips (Professional selected, + Friendly/Executive/Technical), **CTA style** chips (Soft selected / Direct), **Language** select (English). *(No Length field — it was removed.)* Selected chip: `#5b5bd6` text on `#eef0fe` with `#dcdcfb` border; unselected: `#77777f` with `#e6e6ea` border.
- **Step 4 — Review & generate:** summary rows (Sender, Receiver, Template, Tone/CTA, Grounding "8 documents across both companies"), then a full-width "**Generate Marketing Material**" primary button with `magic-wand` icon. **Clicking it navigates to Result Detail** (in production: create a task → show Processing → poll → open result).
- **Footer:** "Back" ghost button (decrements step, floored at 1) + "Continue" dark button (`background:#1a1a1e`, increments step; hidden on step 4).

### 6. Marketing Requests (`/materials`)
- **Purpose:** Task dashboard for all generation requests.
- **Layout:** `max-width:1080px`. Header (title + "New Request" primary button → wizard), a filter-chip row, then a table card.
- **Filter chips:** "All 11" (active: `#fff` on `#1a1a1e`), then Completed 6 / Processing 2 / Needs Review 2 / Failed 1 (inactive: `#55555e` on white, 1px border).
- **Table columns:** **Title | Sender | Receiver | Status | Created**. Rows clickable → Result Detail, hover `#fafafb`. Rows include every status so the badge system is visible (Completed, Processing, Needs Review, Failed, Draft).

### 7. Result Detail (`/materials/:materialId`) — ★ primary screen
- **Purpose:** Review a generated material: human preview, raw layout JSON, grounding sources, and validation.
- **Layout:** `max-width:1120px`. Breadcrumb, header row (title + status + action buttons), then a 2-col grid: **main tabbed panel (`1fr`) + right rail (`320px`)**, `gap:22px`, `align-items:start`.
- **Header:** title "AI for Smarter Logistics" (`23px/700`) + "Completed" pill; metadata line "**Acme AI** → **DHL Logistics** · newsletter_article_v1 · Generated today, 09:32". Actions: "Regenerate" (`arrows-clockwise`, ghost), "Edit prompt" (`pencil-simple`, ghost), "Mark approved" (`check`, green `#16a34a` filled button, hover `#128a3f`).
- **Main panel** (`background:#fff; border:1px solid #ececef; border-radius:16px`): a tab bar (Preview / Layout JSON / Sources) with a "Copy" link that appears only on the JSON tab. Active tab `color:#5b5bd6; border-bottom:2px solid #5b5bd6`.
  - **Preview tab:** rendered newsletter card (`max-width:460px`, centered, `box-shadow:0 8px 30px -12px …`): striped hero placeholder (`hero_image.png · 1200×630`) with a floating sender-logo chip (`acme_logo.svg`); body: eyebrow "ACME AI × DHL" (`11px/600`, uppercase, `#5b5bd6`), headline "Smarter Warehouses, Powered by AI" (`22px/700`), subheadline, two titled body sections ("The Challenge", "The Solution"), and a soft CTA strip "Book a 20-minute logistics AI assessment" (`calendar-check` icon).
  - **Layout JSON tab:** monospace (`JetBrains Mono, 12px/1.75`) pretty-printed JSON on `#fbfbfd`, horizontally scrollable. Syntax coloring: keys `#7c3aed`, strings `#15803d`, numbers `#b45309`, booleans `#0369a1`. Structure includes `template_id`, `theme`, `article` (headline, subheadline, `body_sections[]` with `title`/`text`/`word_count`, `cta`), `assets` (hero_image, sender_logo), `validation`.
  - **Sources tab:** intro line about grounding, then 2 columns — **Sender — Acme AI** (`arrow-up-right` badge) and **Receiver — DHL Logistics** (`arrow-down-left` badge). Each lists source cards: red `file-pdf` icon + filename + monospace page ref (e.g. `p.2`) + an **open-in-new-tab** icon button (`arrow-square-out`) that resolves a signed GCS URL and opens the PDF at the cited page in a new tab, then an italic quoted snippet. Files: product-brochure.pdf p.2, case-study.pdf p.4 / logistics-report.pdf p.5, warehouse-ops.pdf p.3.
- **Right rail** (3 stacked cards):
  - **Quality checks:** 4 rows, each green `check-circle` (17px) + label: JSON schema valid, Word limits passed, Image slots present, Sources attached.
  - **Constraint meters:** 4 progress meters — label + monospace "used / limit" + a 5px track (`#f0f0f2`) with a fill. Green fill (`#16a34a`) when comfortably under; amber fill (`#e0a83b`, label `#b45309`) when近 limit. Values: Headline 5/10 (50%), Subheadline 13/22 (59%), Body·Challenge 54/80 (68%, amber), Body·Solution 61/80 (76%, amber).
  - **Actions:** "Copy JSON" ghost button (`copy`) and a destructive **"Delete material"** button (`trash`, red) that opens a confirm-delete `AlertDialog` ("Delete material?" — removes generated content, layout JSON and source references; routes back to `/materials` on confirm).

### 8. Templates (`/templates`)
- **Purpose:** Show predefined publishing layouts and their constraints.
- **Layout:** `max-width:1080px`. Header row (title + subtitle on the left, **"New Template" primary button** on the right → Create Template), then a 2-col grid (`1.4fr / 1fr`).
- **Active template card** (left): header with `newspaper` icon tile, "Newsletter Article" + monospace id `newsletter_article_v1` + green "Active" pill. Body 2-col: *Field constraints* list (Headline ≤10, Subheadline ≤22, Body 2×≤80, CTA ≤15) + *Image slots* (Hero 1200×630, Sender logo SVG/PNG); *Theme colors* swatches (`primary #5b5bd6`, `accent #0f172a`) + a skeletal *Layout preview* built from grey bars.
- **Right column:** two disabled "Coming soon" template cards (Brochure Tri-fold, Email Campaign), `opacity:.7`, dashed border, note "same JSON contract".

### 8b. Create Template (`/templates/new`)
- **Purpose:** Author a custom publishing template — define its fields, word limits, image slots, and theme. Reached from the "New Template" button on the Templates screen.
- **Layout:** `max-width:1080px`. Breadcrumb (Templates / New template), title "Create Template" (`24px/700`) + subtitle "Define the fields, limits and image slots. Generated content is validated against these constraints.", then a 2-col grid (`1.5fr / 1fr`): builder column (left) + sticky live preview (right). A right-aligned Cancel / Save footer below.
- **Builder column** — four stacked cards (`background:#fff; border:1px solid #ececef; border-radius:16px; padding:20px`):
  - *Basics:* **Template name** (required), **Template ID** (read-only, lock icon, auto-slugified monospace e.g. `product_spotlight_v1` on a `#f4f4f6` field), **Description** (full-width input).
  - *Text fields:* a reorderable list of field rows. Each row: drag handle (`dots-six-vertical`), a type icon tile (`#eef0fe`/`#5b5bd6`), an editable **field name** input (`600`), a compact **word-limit** stepper (`≤ [N] words`), and a delete button (`trash`, hover → danger `#dc4b3e`). Below: a full-width dashed **"Add text field"** button (accent text). Sample rows: Headline ≤8, Subheadline ≤20, Body ≤90, CTA ≤12.
  - *Image slots:* same row pattern with a violet icon tile (`#f1eafe`/`#7c3aed`): editable **slot name** + a **spec** input (dimensions/format, e.g. `1200×630`, `SVG/PNG`) + delete. Dashed **"Add image slot"** button. Sample rows: Hero image, Sender logo.
  - *Theme colors:* Primary + Accent swatches, each with its hex in monospace.
- **Live preview column** (`position:sticky; top:26px`): a *Live layout preview* card — a skeletal render (striped "Hero image" block + grey title/body bars + an accent CTA block) that reflects the defined fields, plus summary chips ("4 text fields", "2 image slots"). Below it, a tinted *JSON contract* note: "This template compiles to the same layout-JSON schema every generation is validated against."
- **Footer:** "Cancel" ghost button + "Save template" primary button (`check` icon); both return to the Templates list.
- **Production notes:** persist the template (name, slug id, ordered fields with limits, image slots with specs, theme) and make it selectable in the Create Material wizard's Step 2. The builder should regenerate the ID slug from the name until first save, validate unique field names, and enforce the limits at generation/validation time.

---

## Interactions & Behavior
- **Navigation** is client-side. In production, map each screen to a route (see route list below). In the prototype it's a single `screen` state string driving conditional rendering.
- **Clickable → navigate:**
  - Sidebar items → their screens. Sign-out icon → Login.
  - Login "Sign in" → Dashboard.
  - Any table/list row with a Sender→Receiver material → Result Detail.
  - "Create Material" / "New Request" / "Generate Material" (company header) → wizard.
  - Company rows → Company Detail. Breadcrumbs → parent list.
  - Wizard "Generate Marketing Material" → Result Detail.
- **Tabs:** Company Detail (Overview/Documents/Generated Materials) and Result Detail (Preview/JSON/Sources) swap panel content via local state; active tab gets the underline treatment.
- **Wizard stepping:** Continue increments the step (max 4), Back decrements (min 1); the step indicator reflects done/current/future. Continue is hidden on the final step.
- **Hover states:** primary buttons darken to `#4f4fce`; dark button to `#333`; ghost buttons to `#f0f0f4`; approve button to `#128a3f`; table rows to `#fafafb`; list cards to `border #d8d8f2 / bg #fbfbff`; breadcrumb links to `#5b5bd6`.
- **Status pills** (reused everywhere): pill = `font 11.5px/600; padding 3px 9-10px; border-radius 20px`, icon + label:
  - Completed — text `#16a34a`, bg `#e7f6ed`, `check-circle` (fill)
  - Processing — text `#b45309`, bg `#fdf0dd`, `circle-notch`
  - Needs Review — text `#7c3aed`, bg `#f1eafe`, `flag` (fill)
  - Failed — text `#dc2626`, bg `#fbe9e9`, `x-circle` (fill)
  - Draft — text `#52525b`, bg `#f0f0f2`, `circle-half` (fill)

### Production behaviors to add (not in prototype)
- **Generate** should create a task, show a **Processing** state, and poll/subscribe until Completed → then reveal the result. The prototype jumps straight to a completed result.
- Real **PDF upload** with progress and the extraction pipeline states (Uploaded → Processing → Processed / Failed).
- **Company create** form (route `/companies/new`).
- "Copy JSON" / "Download JSON" / "Mark approved" / "Regenerate" / "Edit prompt" wired to real actions.

## State Management
Prototype state (per the logic class):
- `screen`: which top-level view is shown (`dashboard | companies | company | create | materials | result | templates | login`).
- `ctab`: Company Detail active tab (`overview | documents | genmat`).
- `rtab`: Result Detail active tab (`preview | json | sources`).
- `step`: wizard step (`1..4`).

In production replace `screen`/tab strings with the router. Data you'll need to fetch:
- Companies list + per-company profile, documents (with processing status + extracted counts), and generated-material history (as sender / as receiver).
- Materials/requests list (title, sender, receiver, status, created).
- A single material result: the layout JSON, the rendered preview fields, grounding sources (per doc + page + snippet), and validation results (schema, word limits, image slots, sources) + per-field constraint usage.

## Route Structure (recommended)
```
/login
/dashboard
/companies
/companies/new
/companies/:companyId        (tabs: overview | documents | materials)
/materials
/materials/new               (wizard steps 1–4)
/materials/:materialId       (tabs: preview | json | sources)
/templates
/templates/new               (custom template builder)
/templates/:templateId
```

## Design Tokens

### Colors
| Role | Hex |
|---|---|
| Accent / primary | `#5b5bd6` |
| Accent hover | `#4f4fce` |
| Accent soft bg | `#eef0fe` / `#eaeafb` / `#f4f4fd` |
| Accent soft border | `#e6e6fb` / `#dcdcfb` |
| Dark button | `#1a1a1e` (hover `#333`) |
| Page background | `#f6f6f8` |
| Surface / card | `#ffffff` |
| Subtle surface | `#fbfbfc` / `#fbfbfd` / `#f7f7fb` |
| Border | `#ececef` |
| Border (lighter, row) | `#f0f0f2` / `#f4f4f6` |
| Input border | `#e4e4e9` / `#e6e6ea` |
| Text primary | `#1a1a1e` |
| Text body | `#2f2f38` / `#3a3a42` / `#4a4a52` / `#55555e` |
| Text secondary | `#77777f` |
| Text muted | `#9a9aa5` |
| Text faint / captions | `#a8a8b0` / `#b7b7c0` |
| Success | `#16a34a` on `#e7f6ed` (approve btn hover `#128a3f`) |
| Warning / processing | `#b45309` on `#fdf0dd`; meter fill `#e0a83b` |
| Danger / failed | `#dc2626` on `#fbe9e9` (pdf icon `#dc4b3e`) |
| Review / violet | `#7c3aed` on `#f1eafe` |
| Draft / neutral | `#52525b` on `#f0f0f2` |
| JSON: key / string / number / bool | `#7c3aed` / `#15803d` / `#b45309` / `#0369a1` |
| Company avatar tints | `#eaeafb`·`#5b5bd6`, `#fdeede`·`#c2710c`, `#e6f6ee`·`#0f8a4d`, `#e9edfb`·`#3457c9`, `#f3eafc`·`#8b3ecc` |

### Typography
- **UI font:** "Hanken Grotesk" (Google Fonts), weights 400/500/600/700/800. Fallback `system-ui, -apple-system, sans-serif`.
- **Mono font:** "JetBrains Mono" (Google Fonts), 400/500/600 — used for JSON, ids, page refs, filenames, meter values.
- **Scale (size / weight / notes):** page title `24–26px / 700 / -0.03em`; screen H1 (detail) `23px / 700 / -0.02em`; card/section heading `14–16px / 600`; stat number `27px / 700`; body `13.5px`; secondary `12.5–13px`; small `11.5–12px`; caption/eyebrow `11px / 600 / uppercase / letter-spacing .04–.08em`; JSON `12px / 1.75`.

### Spacing & Radii
- Container padding: `~32px 40px 60px` (wizard `30px 40px`, detail `26px 40px`).
- Grid/flex gaps: `16px`–`22px` between cards; `6–11px` within components.
- **Radii:** cards `14–16px`; buttons/inputs `9–11px`; pills `20px`; nav items `9px`; small tiles/icons `6–9px`; avatars `8–13px`.
- **Shadows:** card float `0 8px 30px -12px rgba(20,20,40,.15)`; login card `0 12px 40px -12px rgba(20,20,40,.12)`; logo tile `0 4px 12px rgba(91,91,214,.35)`.
- Sidebar width `236px`. Result rail `320px`.

## Recommended Stack: React + Tailwind CSS
This design maps onto Tailwind cleanly — it's all standard flex/grid, spacing, borders, radii,
and a small color set. Build each screen as a React component tree styled with Tailwind
utilities. Define the custom palette/fonts once in the theme (below) so classes read like
`bg-accent hover:bg-accent-hover`, `text-success bg-success-soft`, `border-border`, `rounded-2xl`
— rather than scattering arbitrary `[#5b5bd6]` values. The Design Tokens tables above list every
value; the config below names them.

### Tailwind v4 (`@theme` in your CSS entry)
```css
@import "tailwindcss";

@theme {
  /* fonts */
  --font-sans: "Hanken Grotesk", system-ui, -apple-system, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  /* accent */
  --color-accent: #5b5bd6;
  --color-accent-hover: #4f4fce;
  --color-accent-soft: #eef0fe;   /* soft bg */
  --color-accent-tint: #eaeafb;   /* avatar/icon tile */
  --color-accent-wash: #f4f4fd;   /* info note bg */
  --color-accent-border: #e6e6fb;

  /* surfaces & structure */
  --color-page: #f6f6f8;
  --color-surface: #ffffff;
  --color-subtle: #fbfbfc;
  --color-rail: #f7f7fb;
  --color-border: #ececef;
  --color-border-soft: #f0f0f2;
  --color-border-row: #f4f4f6;
  --color-input: #e6e6ea;
  --color-dark: #1a1a1e;

  /* text */
  --color-ink: #1a1a1e;
  --color-body: #3a3a42;
  --color-secondary: #77777f;
  --color-muted: #9a9aa5;
  --color-faint: #a8a8b0;

  /* status: text / soft bg */
  --color-success: #16a34a;
  --color-success-soft: #e7f6ed;
  --color-warning: #b45309;
  --color-warning-soft: #fdf0dd;
  --color-warning-fill: #e0a83b;   /* constraint meter */
  --color-danger: #dc2626;
  --color-danger-soft: #fbe9e9;
  --color-review: #7c3aed;
  --color-review-soft: #f1eafe;
  --color-draft: #52525b;
  --color-draft-soft: #f0f0f2;

  /* JSON syntax */
  --color-json-key: #7c3aed;
  --color-json-string: #15803d;
  --color-json-number: #b45309;
  --color-json-bool: #0369a1;

  /* shadows */
  --shadow-card: 0 8px 30px -12px rgba(20,20,40,.15);
  --shadow-login: 0 12px 40px -12px rgba(20,20,40,.12);
}
```

### Tailwind v3 (`tailwind.config.js`)
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Hanken Grotesk"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        accent: { DEFAULT: "#5b5bd6", hover: "#4f4fce", soft: "#eef0fe", tint: "#eaeafb", wash: "#f4f4fd", border: "#e6e6fb" },
        page: "#f6f6f8", surface: "#ffffff", subtle: "#fbfbfc", rail: "#f7f7fb", dark: "#1a1a1e",
        border: { DEFAULT: "#ececef", soft: "#f0f0f2", row: "#f4f4f6", input: "#e6e6ea" },
        ink: "#1a1a1e", body: "#3a3a42", secondary: "#77777f", muted: "#9a9aa5", faint: "#a8a8b0",
        success: { DEFAULT: "#16a34a", soft: "#e7f6ed" },
        warning: { DEFAULT: "#b45309", soft: "#fdf0dd", fill: "#e0a83b" },
        danger: { DEFAULT: "#dc2626", soft: "#fbe9e9" },
        review: { DEFAULT: "#7c3aed", soft: "#f1eafe" },
        draft: { DEFAULT: "#52525b", soft: "#f0f0f2" },
      },
      boxShadow: {
        card: "0 8px 30px -12px rgba(20,20,40,.15)",
        login: "0 12px 40px -12px rgba(20,20,40,.12)",
      },
      borderRadius: { xl: "0.75rem", "2xl": "0.875rem", "3xl": "1rem" },
    },
  },
};
```

### Translation notes (design → Tailwind)
- **Fonts:** install `@fontsource/hanken-grotesk` + `@fontsource/jetbrains-mono` (or add a Google Fonts `<link>`), import the weights, then `font-sans` / `font-mono` apply the theme. Set `font-sans` + `bg-page text-ink` on `<body>`.
- **Odd pixel sizes** in this spec (e.g. `13.5px` body, `27px` stat number, `11.5px` labels) don't all land on Tailwind's default scale. Prefer the nearest step (`text-sm`, `text-3xl`) for consistency, or use arbitrary values (`text-[13.5px]`) where matching the comp exactly matters. Letter-spacing: `tracking-tight` / `-tracking-[.03em]`.
- **Radii map:** cards `rounded-2xl`/`rounded-3xl` (14–16px), buttons/inputs `rounded-[10px]`, pills `rounded-full`, nav items `rounded-[9px]`.
- **Reusable components** worth extracting (they repeat across screens): `<StatusPill status="completed|processing|needs_review|failed|draft">` (drives the icon + `text-*`/`bg-*-soft` pair), `<ConstraintMeter used limit>` (green under, `warning` when near), `<CompanyAvatar name tint>`, `<StatCard>`, `<NavItem active>`, and `<Tabs>` for the underline tab pattern on Company Detail + Result Detail.
- **Icons:** `@phosphor-icons/react` — import per-icon (`import { MagicWand } from "@phosphor-icons/react"`), pass `weight="fill"|"bold"|"regular"` to match the weight noted for each icon, and `size`/`className="text-accent"` for color.
- **JSON syntax coloring:** wrap tokens in `<span>`s using the `json-*` colors, or use a lightweight highlighter (Shiki/Prism) themed to those four colors.
- **Striped placeholders** (hero/logo areas): a `repeating-linear-gradient` utility via arbitrary bg value or a tiny CSS class — Tailwind has no built-in for this, so a small component/util is cleanest.

## Recommended UI Library: shadcn/ui (preferred)
The visual language of this design — neutral palette, hairline borders, soft rounded cards,
muted text hierarchy, understated hover states — is exactly the aesthetic **shadcn/ui** is built
around (Radix primitives + Tailwind). It's the fastest route to a polished, accessible build:
most screen elements map ~1:1 onto shadcn components, and you theme it via CSS variables (below)
instead of hand-building tabs, dialogs, comboboxes, etc.

shadcn/ui is copy-in, not a dependency — run `npx shadcn@latest init`, then
`npx shadcn@latest add <component>` for each primitive listed below. It still uses the Tailwind
theme from the previous section; wire the accent through shadcn's `--primary` variable so its
Button/Badge/Ring all pick it up.

### Theme variables (`globals.css`)
Map the design tokens onto shadcn's semantic variables (HSL triplets, no `hsl()` wrapper):
```css
:root {
  --background: 240 20% 97%;       /* page #f6f6f8 */
  --foreground: 240 6% 11%;        /* ink #1a1a1e */
  --card: 0 0% 100%;               /* #ffffff */
  --card-foreground: 240 6% 11%;
  --popover: 0 0% 100%;
  --popover-foreground: 240 6% 11%;
  --primary: 240 60% 60%;          /* accent #5b5bd6 */
  --primary-foreground: 0 0% 100%;
  --secondary: 240 20% 96%;        /* soft accent bg #eef0fe-ish */
  --secondary-foreground: 240 6% 11%;
  --muted: 240 14% 96%;            /* subtle surfaces */
  --muted-foreground: 240 4% 55%;  /* secondary text #77777f */
  --accent: 240 60% 97%;           /* hover wash #eef0fe */
  --accent-foreground: 240 60% 60%;
  --destructive: 0 72% 51%;        /* danger #dc2626 */
  --destructive-foreground: 0 0% 100%;
  --border: 240 9% 93%;            /* #ececef */
  --input: 240 9% 91%;             /* #e6e6ea */
  --ring: 240 60% 60%;             /* accent focus ring */
  --radius: 0.875rem;              /* cards 14px; buttons use calc(var(--radius) - 4px) */
}
```
Status colors (success/warning/review/draft) aren't part of shadcn's default variable set — keep
them as the named Tailwind colors from the config above and reference them in your `StatusPill`
and `ConstraintMeter` components.

### Component mapping (screen element → shadcn/ui)
- **Buttons** — `Button`. Variants: primary→`default` (themed via `--primary`), ghost/outline→`outline`, the dark "Continue"→custom `className="bg-dark text-white"`, "Mark approved"→custom `className="bg-success ..."`. Icon buttons→`Button size="icon" variant="ghost"`.
- **Cards** (stat cards, profile cards, rail cards, template card, login card) — `Card` + `CardHeader`/`CardContent`/`CardFooter`.
- **Sidebar** — shadcn `Sidebar` (from `add sidebar`) or a plain `<aside>` with `Button variant="ghost"` nav items; use the active `bg-accent-soft` treatment for the current route.
- **Tables** (Companies, Marketing Requests, Documents, Dashboard recent) — `Table` + `TableHeader/Row/Head/Cell`. Wrap clickable rows with an `onClick` + `cursor-pointer hover:bg-muted`.
- **Tabs** (Company Detail: Overview/Documents/Generated Materials; Result Detail: Preview/JSON/Sources) — `Tabs` + `TabsList`/`TabsTrigger`/`TabsContent`. Restyle the underline look (default shadcn is a pill list — override `TabsTrigger` with `data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none`).
- **Status pills** — `Badge` as the base; build a `StatusPill` wrapper that picks the icon + `text-*`/`bg-*-soft` pair per status (`completed | processing | needs_review | failed | draft`). Use `variant="secondary"` and override colors.
- **Industry / soft chips** (industry tag, tone/CTA chips) — `Badge variant="outline"`; selected chip gets `bg-accent-soft text-accent border-accent-border`.
- **Inputs & textareas** (login, search fields, Create Company form, prompt) — `Input`, `Textarea`, with `Label`.
- **Selects** (Industry, Tone, Language dropdowns) — `Select` (`SelectTrigger`/`SelectContent`/`SelectItem`).
- **Sender/Receiver search** (wizard Step 1) — this is the scalable search you asked for: use **`Command`** (`CommandInput`/`CommandList`/`CommandItem`) inline, or `Combobox` (Command inside `Popover`). Each `CommandItem` renders the avatar + name + "industry · N docs"; the selected item shows a `Check` and the `bg-accent-soft` highlight.
- **Wizard stepper** — no shadcn primitive; build a small `Stepper` component (numbered circles + connectors) using the tokens. Footer Back/Continue are `Button`s.
- **Template builder rows** (Create Template) — reorderable field/slot rows: `Input` for names, a small number stepper for word limits, `Button size="icon" variant="ghost"` for delete, and `dnd-kit` (or `framer-motion` Reorder) for drag handles. The "Add text field / image slot" is a dashed-outline `Button variant="outline"`.
- **Dropzone** (Documents upload, Create Company logo) — plain bordered-dashed `div`; pair with `react-dropzone` for real upload behavior.
- **Constraint meters** (Result rail) — `Progress`, or a custom bar; color the indicator green under limit / `warning` near it.
- **Quality checks / readiness lists** — plain flex rows with a filled `CheckCircle` icon (not a shadcn component).
- **Breadcrumbs** — `Breadcrumb` (`BreadcrumbList`/`BreadcrumbItem`/`BreadcrumbLink`).
- **Info / AI-hint callouts** (login note removed; Create Company hint, wizard grounding strip) — `Alert` + `AlertDescription`, or a plain tinted `div`.
- **Avatars** (company initials, user chip) — `Avatar` + `AvatarFallback` with the per-company tint classes; or a plain tinted `div` since these are always initials.
- **Toasts** (after Generate / Copy JSON / Mark approved) — `Sonner` (`add sonner`).
- **Confirm-delete dialogs** (document delete on Company → Documents; "Delete material" on Result Detail) — `AlertDialog` (`AlertDialogTrigger`/`AlertDialogContent`/`AlertDialogAction`/`AlertDialogCancel`). Red icon chip + title + cascade-warning body; the destructive action is a `Button variant="destructive"`. Material delete routes back to `/materials` on confirm.
- **Open-in-new-tab / view PDF** (Documents row action; each Sources card's page-ref) — an icon `Button size="icon" variant="ghost"` (`ArrowSquareOut`). On click, call the backend for a **signed GCS URL**, then `window.open(url, '_blank', 'noopener')`. For source citations, pass the page (e.g. `#page=4`) so the PDF opens at the cited page.
- **Icons** — shadcn examples use `lucide-react`. This design specifies **Phosphor** names; either keep `@phosphor-icons/react` (recommended, matches the spec's weights) or substitute the nearest `lucide` equivalent consistently.

### shadcn components to add
```
npx shadcn@latest add button card table tabs badge input textarea label \
  select command popover progress breadcrumb alert alert-dialog avatar dialog sonner separator
```

## Assets
- **Icons:** [Phosphor Icons](https://phosphoricons.com/) (`@phosphor-icons/web`), weights **regular / bold / fill**. Icon names referenced throughout this doc (e.g. `stack`, `buildings`, `magic-wand`, `check-circle`, `file-pdf`, `brackets-curly`, `link`). Use the React package `@phosphor-icons/react` in a React codebase.
- **Fonts:** Hanken Grotesk + JetBrains Mono via Google Fonts.
- **Images:** none shipped — all imagery is a striped placeholder with a monospace label. Provide real asset slots for: company logos, generated hero images, and the sender-logo overlay on the preview.
- No brand assets from any third party are used; the "Collateral AI" name/mark is a neutral placeholder you can rename.

## Files
- `Collate.dc.html` — the full interactive design reference (all screens, working navigation, tabs, and wizard). Open in a browser to see intended behavior. **Do not ship this file** — it uses a proprietary component runtime; recreate the designs natively per the spec above. *(Filename retains `Collate`; the product is branded "Collateral AI" in-app.)*

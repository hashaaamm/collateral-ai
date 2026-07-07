# Companies Enhancements (search + edit + delete) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add name search, edit, and delete to the existing Companies feature — full-CRUD backend API + frontend UI (search bar, edit page reusing a shared form, delete with a confirm dialog).

**Architecture:** Backend adds `UpdateModelMixin` + `DestroyModelMixin` + a `SearchFilter` to `CompanyViewSet`, plus a best-effort `gcs.delete_object` on destroy. Frontend adds `useUpdateCompany`/`useDeleteCompany` hooks and a `search` arg to `useCompanies`, refactors the create form into a shared `CompanyForm` used by both a create wrapper and a new edit page, adds a debounced search bar to the list, and Edit/Delete (shadcn AlertDialog) on the detail page.

**Tech Stack:** Django + DRF + drf-spectacular, pytest; React 19 + Vite, TanStack Router/Query, openapi-fetch, react-hook-form + zod, shadcn (`alert-dialog`), `@phosphor-icons/react`.

## Global Constraints

- Builds on the merged Companies feature; follow its patterns. Branch `feat/company-crud`; commit per task, no push.
- APIs require auth (DRF default `IsAuthenticated`; frontend attaches `Authorization: Token <token>`).
- Backend commands: `docker compose -f docker-compose.local.yml run --rm django <cmd>` from repo root `/Users/hashaam/dev/CollateralAI`. Frontend: `pnpm` from `frontend/`.
- Frontend TypeScript strict (`noUnusedLocals`/`noUnusedParameters`); no raw hex in JSX except dynamic `brand_colors` via `style`. Design tokens (`bg-brand`, `bg-brand-hover`, `text-ink`, `text-body`, `text-subtext`, `text-mute`, `text-faint`, `border-hairline`, `border-field`, `bg-subtle`, `bg-surface`, `text-destructive`, `bg-brand-soft`, `text-brand`). `pnpm lint` has ONE pre-existing button.tsx warning — not a finding; leave button.tsx alone.
- Edit = partial PATCH: send `logo` ONLY when a new logo is uploaded; omit it to keep the existing logo. Delete cleanup of the GCS object is best-effort (never blocks the row delete).
- Frontend pages verified by `pnpm typecheck && pnpm lint && pnpm build` (no local browser). No React Testing Library is set up — do not add it; the debounce hook is verified via typecheck/build, not a unit test.

---

### Task 1: Backend — full CRUD + name search + delete cleanup + tests + schema regen

**Files:**
- Modify: `backend/collateral_ai/companies/api/views.py`
- Modify: `backend/collateral_ai/companies/gcs.py`
- Modify: `backend/collateral_ai/companies/tests/api/test_views.py`
- Modify: `frontend/src/lib/api/schema.d.ts` (regenerated)

**Interfaces:**
- Consumes: existing `Company`, `CompanyFactory`, `companies.gcs`.
- Produces: `PATCH`/`PUT`/`DELETE /api/companies/{id}/`, `GET /api/companies/?search=<q>` (name icontains), `gcs.delete_object(object_path)`.

- [ ] **Step 1: Add `delete_object` to `backend/collateral_ai/companies/gcs.py`**

Append this function to the module:
```python
def delete_object(object_path: str) -> None:
    """Best-effort delete of a stored object; never raises."""
    try:
        _bucket().blob(object_path).delete()
    except Exception:  # noqa: BLE001 - deletion is best-effort
        pass
```

- [ ] **Step 2: Extend the viewset — `backend/collateral_ai/companies/api/views.py`**

Change the imports and the class to add update/destroy mixins, the search filter, and the destroy override. Replace the import block's mixin imports and add filters:
```python
from rest_framework import filters
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.mixins import DestroyModelMixin
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
```
Change the class declaration and add the filter config + `perform_destroy` (keep the existing `logo_upload_url` action and `ALLOWED_LOGO_TYPES` unchanged):
```python
class CompanyViewSet(
    RetrieveModelMixin,
    ListModelMixin,
    CreateModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def perform_destroy(self, instance):
        if instance.logo and gcs.is_configured():
            gcs.delete_object(instance.logo)
        instance.delete()
```

- [ ] **Step 3: Write the failing tests — append to `backend/collateral_ai/companies/tests/api/test_views.py`**

```python
def test_search_filters_by_name(auth_client):
    CompanyFactory(name="Acme AI")
    CompanyFactory(name="Globex")
    resp = auth_client.get("/api/companies/?search=acm")
    assert resp.status_code == HTTPStatus.OK
    names = [c["name"] for c in resp.json()]
    assert names == ["Acme AI"]


def test_search_empty_returns_all(auth_client):
    CompanyFactory(name="Acme AI")
    CompanyFactory(name="Globex")
    resp = auth_client.get("/api/companies/")
    assert len(resp.json()) == 2


def test_search_no_match_returns_empty(auth_client):
    CompanyFactory(name="Acme AI")
    resp = auth_client.get("/api/companies/?search=zzz")
    assert resp.json() == []


def test_patch_updates_name(auth_client):
    company = CompanyFactory(name="Old")
    resp = auth_client.patch(
        f"/api/companies/{company.pk}/", {"name": "New"}, format="json",
    )
    assert resp.status_code == HTTPStatus.OK
    company.refresh_from_db()
    assert company.name == "New"


def test_patch_without_logo_keeps_existing(auth_client):
    company = CompanyFactory(name="Keep", logo="media/companies/logos/x/a.png")
    auth_client.patch(f"/api/companies/{company.pk}/", {"name": "Keep2"}, format="json")
    company.refresh_from_db()
    assert company.logo == "media/companies/logos/x/a.png"


def test_delete_removes_company_and_cleans_logo(auth_client):
    company = CompanyFactory(logo="media/companies/logos/x/a.png")
    with mock.patch(
        "collateral_ai.companies.api.views.gcs.is_configured", return_value=True,
    ), mock.patch(
        "collateral_ai.companies.api.views.gcs.delete_object",
    ) as delete_object:
        resp = auth_client.delete(f"/api/companies/{company.pk}/")
    assert resp.status_code == HTTPStatus.NO_CONTENT
    assert not Company.objects.filter(pk=company.pk).exists()
    delete_object.assert_called_once_with("media/companies/logos/x/a.png")


def test_patch_and_delete_require_auth():
    company = CompanyFactory()
    assert APIClient().patch(f"/api/companies/{company.pk}/", {}, format="json").status_code == HTTPStatus.FORBIDDEN
    assert APIClient().delete(f"/api/companies/{company.pk}/").status_code == HTTPStatus.FORBIDDEN
```

- [ ] **Step 4: Run the tests**

Run: `docker compose -f docker-compose.local.yml run --rm django pytest collateral_ai/companies/tests/api/test_views.py -q`
Expected: PASS (the original 8 + these 7 = 15).

- [ ] **Step 5: Regenerate the frontend OpenAPI types**

Run:
```bash
docker compose -f docker-compose.local.yml run --rm django python manage.py spectacular --format openapi-json > /tmp/schema.json
cd frontend && pnpm exec openapi-typescript /tmp/schema.json -o src/lib/api/schema.d.ts
```
Expected: the `/api/companies/{id}/` path now has `patch` + `delete` operations, and `/api/companies/` GET gains a `search` query param. Verify: `grep -nE "PatchedCompany|\"search\"" frontend/src/lib/api/schema.d.ts | head` shows a `search` parameter and a `PatchedCompany` schema. Then `cd frontend && pnpm typecheck` passes.

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/companies/api/views.py backend/collateral_ai/companies/gcs.py backend/collateral_ai/companies/tests/api/test_views.py frontend/src/lib/api/schema.d.ts
git commit -m "Companies API: search + update + destroy (with GCS logo cleanup)"
```

---

### Task 2: Frontend hooks — search + update + delete

**Files:**
- Modify: `frontend/src/lib/api/companies.ts`

**Interfaces:**
- Consumes: `api`, generated `schema.d.ts` (now with `search` param + `PatchedCompany` + delete op).
- Produces: `useCompanies(search?: string)`; `useUpdateCompany(id: number)` (PATCH); `useDeleteCompany()` (DELETE). Existing `useCompany`, `useCreateCompany`, `requestUploadAndPut`, `Company` unchanged.

- [ ] **Step 1: Update `useCompanies` and add the two mutations**

In `frontend/src/lib/api/companies.ts`, replace the `useCompanies` function with the search-aware version:
```ts
export function useCompanies(search?: string) {
  const q = search?.trim() ?? "";
  return useQuery({
    queryKey: ["companies", { search: q }],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/companies/", {
        params: q ? { query: { search: q } } : {},
      });
      if (error) throw error;
      return data;
    },
  });
}
```
Add these two hooks (after `useCreateCompany`):
```ts
type CompanyWrite = {
  name?: string;
  website?: string;
  industry?: string;
  description?: string;
  brand_colors?: string[];
  logo?: string;
};

export function useUpdateCompany(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CompanyWrite) => {
      const { data, error } = await api.PATCH("/api/companies/{id}/", {
        params: { path: { id } },
        body: body as components["schemas"]["PatchedCompany"],
      });
      if (error || !data) throw new Error("update_failed");
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      qc.invalidateQueries({ queryKey: ["companies", id] });
    },
  });
}

export function useDeleteCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/companies/{id}/", {
        params: { path: { id } },
      });
      if (error) throw new Error("delete_failed");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}
```
Note: the `PatchedCompany` cast mirrors the existing `useCreateCompany` cast. If `pnpm typecheck` reports the schema named the partial-update body differently, change the cast target to the actual generated name (inspect `schema.d.ts`); if PATCH needs no cast, drop it.

- [ ] **Step 2: Verify**

Run (from `frontend/`): `pnpm typecheck && pnpm test`
Expected: no type errors; the existing `companies.test.ts` still passes (3 tests).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api/companies.ts
git commit -m "Add useUpdateCompany, useDeleteCompany, and search to useCompanies"
```

---

### Task 3: Frontend — debounced search bar on the list

**Files:**
- Create: `frontend/src/lib/use-debounced-value.ts`
- Modify: `frontend/src/routes/companies-list.tsx`

**Interfaces:**
- Consumes: `useCompanies(search)`, `useDebouncedValue`.
- Produces: `useDebouncedValue<T>(value, delayMs): T`.

- [ ] **Step 1: Create `frontend/src/lib/use-debounced-value.ts`**

```ts
import { useEffect, useState } from "react";

/** Returns `value` after it has stopped changing for `delayMs`. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
```

- [ ] **Step 2: Add the search bar to `frontend/src/routes/companies-list.tsx`**

Replace the file with:
```tsx
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Buildings, CaretRight, MagnifyingGlass, Plus } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import { useCompanies } from "@/lib/api/companies";
import { useDebouncedValue } from "@/lib/use-debounced-value";

export function CompaniesListPage() {
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const { data: companies, isLoading, isError } = useCompanies(debounced);

  return (
    <div className="mx-auto max-w-[1080px] px-10 pb-[60px] pt-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-[24px] font-bold tracking-[-0.03em] text-ink">Companies</h1>
          <p className="mt-1 text-sm text-subtext">
            Reusable company context shared across every generation.
          </p>
        </div>
        <Link
          to="/companies/new"
          className="flex items-center gap-[7px] rounded-[10px] bg-brand px-[15px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus weight="bold" size={14} />
          Create Company
        </Link>
      </div>

      <div className="mb-4 flex items-center gap-[9px] rounded-[10px] border border-field bg-surface px-3">
        <MagnifyingGlass size={16} className="text-faint" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search companies…"
          aria-label="Search companies"
          className="w-full bg-transparent py-[10px] text-[13.5px] text-ink outline-none placeholder:text-faint"
        />
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-surface">
        <div className="grid grid-cols-[2fr_1fr_1fr_auto] gap-4 border-b border-hairline bg-subtle px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-faint">
          <span>Company</span>
          <span>Industry</span>
          <span>Website</span>
          <span className="w-4" />
        </div>

        {isLoading && <div className="px-5 py-8 text-center text-sm text-mute">Loading…</div>}
        {isError && (
          <div className="px-5 py-8 text-center text-sm text-destructive">
            Couldn't load companies.
          </div>
        )}
        {companies?.length === 0 && (
          <div className="flex flex-col items-center gap-2 px-5 py-12 text-center">
            <Buildings size={28} className="text-faint" />
            <p className="text-sm text-mute">
              {debounced.trim() ? `No companies match “${debounced.trim()}”.` : "No companies yet."}
            </p>
          </div>
        )}
        {companies?.map((c) => (
          <Link
            key={c.id}
            to="/companies/$companyId"
            params={{ companyId: String(c.id) }}
            className="grid grid-cols-[2fr_1fr_1fr_auto] items-center gap-4 border-b border-hairline px-5 py-[14px] last:border-b-0 hover:bg-subtle"
          >
            <span className="flex items-center gap-3">
              <CompanyLogo name={c.name} logoUrl={c.logo_url} />
              <span className="text-[13.5px] font-semibold text-ink">{c.name}</span>
            </span>
            <span className="text-[13px] text-body">{c.industry || "—"}</span>
            <span className="truncate text-[13px] text-subtext">{c.website || "—"}</span>
            <CaretRight size={14} className="text-faint" />
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm build`
Expected: all pass (no new lint problems).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/use-debounced-value.ts frontend/src/routes/companies-list.tsx
git commit -m "Add debounced name search bar to the companies list"
```

---

### Task 4: Frontend — shared CompanyForm + create refactor + edit page + route

**Files:**
- Create: `frontend/src/components/company-form.tsx`
- Modify: `frontend/src/routes/create-company.tsx`
- Create: `frontend/src/routes/edit-company.tsx`
- Modify: `frontend/src/router.tsx`

**Interfaces:**
- Consumes: `requestUploadAndPut`, `useCreateCompany`, `useUpdateCompany`, `useCompany`, `Button`, `Input`, phosphor icons, react-hook-form + zod.
- Produces: `CompanyForm` (shared); `CreateCompanyPage` (unchanged export, now a thin wrapper); `EditCompanyPage` (new) at `/companies/$companyId/edit`.

- [ ] **Step 1: Create the shared form — `frontend/src/components/company-form.tsx`**

```tsx
import { useRef, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Buildings, Globe, Plus, UploadSimple, X } from "@phosphor-icons/react";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { requestUploadAndPut } from "@/lib/api/companies";

const schema = z.object({
  name: z.string().min(1, "Company name is required"),
  website: z.union([z.string().url("Enter a valid URL"), z.literal("")]).optional(),
  industry: z.string().optional(),
  description: z.string().optional(),
});
type Values = z.infer<typeof schema>;

const MAX_COLORS = 5;

export type CompanyFormPayload = {
  name: string;
  website?: string;
  industry?: string;
  description?: string;
  brand_colors: string[];
  logo?: string;
};

export type CompanyFormInitial = {
  name?: string;
  website?: string;
  industry?: string;
  description?: string;
  brand_colors?: string[];
  logoUrl?: string | null;
};

export function CompanyForm({
  initial,
  submitLabel,
  submitting,
  error,
  cancel,
  onSubmit,
}: {
  initial?: CompanyFormInitial;
  submitLabel: string;
  submitting: boolean;
  error: boolean;
  cancel: ReactNode;
  onSubmit: (payload: CompanyFormPayload) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);

  const [colors, setColors] = useState<string[]>(initial?.brand_colors ?? []);
  const [logoPath, setLogoPath] = useState<string>(""); // set only when a NEW logo is uploaded
  const [logoPreview, setLogoPreview] = useState<string>(initial?.logoUrl ?? "");
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "error" | "unavailable">(
    "idle",
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: initial?.name ?? "",
      website: initial?.website ?? "",
      industry: initial?.industry ?? "",
      description: initial?.description ?? "",
    },
  });

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadState("uploading");
    setLogoPreview(URL.createObjectURL(file));
    try {
      setLogoPath(await requestUploadAndPut(file));
      setUploadState("idle");
    } catch (err) {
      setLogoPath("");
      setUploadState(err instanceof Error && err.message === "upload_not_configured" ? "unavailable" : "error");
    }
  }

  const submit = handleSubmit((values) => {
    onSubmit({
      name: values.name,
      website: values.website || undefined,
      industry: values.industry || undefined,
      description: values.description || undefined,
      brand_colors: colors,
      logo: logoPath || undefined, // omitted when unchanged (keeps existing logo on edit)
    });
  });

  return (
    <form onSubmit={submit}>
      <div className="rounded-2xl border border-hairline bg-surface p-[26px]">
        <div className="mb-6 flex items-center gap-4 border-b border-hairline pb-[22px]">
          {logoPreview ? (
            <img src={logoPreview} alt="Logo preview" className="size-[56px] flex-none rounded-[13px] object-cover" />
          ) : (
            <div className="flex size-[56px] flex-none items-center justify-center rounded-[13px] bg-subtle text-faint">
              <Buildings size={24} />
            </div>
          )}
          <div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden onChange={onPickFile} aria-label="Upload company logo" />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploadState === "uploading"}
              className="flex items-center gap-[7px] rounded-[9px] border border-field bg-surface px-[13px] py-2 text-[12.5px] font-semibold text-body hover:bg-subtle disabled:opacity-60"
            >
              <UploadSimple size={14} />
              {uploadState === "uploading" ? "Uploading…" : "Upload logo"}
            </button>
            <div className="mt-[6px] text-[11.5px] text-faint" aria-live="polite">
              {uploadState === "error" && <span className="text-destructive">Upload failed. Try again.</span>}
              {uploadState === "unavailable" && "Logo upload isn't configured in this environment."}
              {uploadState !== "error" && uploadState !== "unavailable" && "SVG or PNG, at least 128×128"}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-[18px_20px]">
          <div>
            <label htmlFor="name" className="mb-2 block text-[12px] font-semibold text-body">
              Company name <span className="text-destructive">*</span>
            </label>
            <Input id="name" placeholder="e.g. Acme AI" className="rounded-[10px] border-field bg-subtle px-3 py-[11px] text-[13.5px]" {...register("name")} />
            {errors.name && <p className="mt-1 text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div>
            <label htmlFor="website" className="mb-2 block text-[12px] font-semibold text-body">Website</label>
            <div className="flex items-center gap-2 rounded-[10px] border border-field bg-subtle px-3">
              <Globe size={15} className="text-faint" />
              <Input id="website" placeholder="https://acme.ai" className="h-auto border-0 bg-transparent px-0 py-[11px] text-[13.5px] shadow-none focus-visible:ring-0" {...register("website")} />
            </div>
            {errors.website && <p className="mt-1 text-xs text-destructive">{errors.website.message}</p>}
          </div>
          <div>
            <label htmlFor="industry" className="mb-2 block text-[12px] font-semibold text-body">Industry</label>
            <Input id="industry" placeholder="e.g. AI Software" className="rounded-[10px] border-field bg-subtle px-3 py-[11px] text-[13.5px]" {...register("industry")} />
          </div>
          <div>
            <label className="mb-2 block text-[12px] font-semibold text-body">Brand colors</label>
            <div className="flex items-center gap-2">
              {colors.map((hex, i) => (
                <span key={i} className="relative">
                  <input
                    type="color"
                    value={hex}
                    onChange={(e) => setColors((c) => c.map((x, j) => (j === i ? e.target.value : x)))}
                    className="size-[34px] cursor-pointer rounded-lg border border-hairline"
                  />
                  <button type="button" onClick={() => setColors((c) => c.filter((_, j) => j !== i))} className="absolute -right-1 -top-1 rounded-full bg-surface text-mute" aria-label="Remove color">
                    <X size={12} />
                  </button>
                </span>
              ))}
              {colors.length < MAX_COLORS && (
                <button type="button" onClick={() => setColors((c) => [...c, "#5b5bd6"])} className="flex size-[34px] items-center justify-center rounded-lg border border-dashed border-field text-faint hover:bg-subtle" aria-label="Add color">
                  <Plus weight="bold" size={14} />
                </button>
              )}
            </div>
          </div>
          <div className="col-span-2">
            <label htmlFor="description" className="mb-2 block text-[12px] font-semibold text-body">Description</label>
            <textarea id="description" rows={2} placeholder="One line on what the company does." className="w-full resize-none rounded-[10px] border border-field bg-subtle px-3 py-[11px] text-[13.5px] leading-[1.55] text-ink outline-none" {...register("description")} />
          </div>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-destructive">Something went wrong. Please try again.</p>}

      <div className="mt-5 flex justify-end gap-[9px]">
        {cancel}
        <Button type="submit" disabled={submitting || uploadState === "uploading"} className="flex h-auto items-center gap-[7px] rounded-[10px] bg-brand px-[18px] py-[10px] text-[13.5px] font-semibold text-white hover:bg-brand-hover">
          {submitting ? "Saving…" : <>{submitLabel} <ArrowRight weight="bold" size={14} /></>}
        </Button>
      </div>
    </form>
  );
}
```

- [ ] **Step 2: Replace `frontend/src/routes/create-company.tsx` with a thin wrapper**

```tsx
import { Link, useNavigate } from "@tanstack/react-router";

import { CompanyForm } from "@/components/company-form";
import { useCreateCompany } from "@/lib/api/companies";

export function CreateCompanyPage() {
  const navigate = useNavigate();
  const create = useCreateCompany();

  return (
    <div className="mx-auto max-w-[760px] px-10 pb-[60px] pt-[26px]">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/companies" className="hover:text-brand">Companies</Link>
        <span>/</span>
        <span className="font-medium text-body">New company</span>
      </div>
      <h1 className="mb-1 text-[24px] font-bold tracking-[-0.03em] text-ink">Create Company</h1>
      <p className="mb-[26px] text-[13.5px] text-subtext">Add a company profile.</p>

      <CompanyForm
        submitLabel="Create Company"
        submitting={create.isPending}
        error={create.isError}
        cancel={
          <Link to="/companies" className="rounded-[10px] border border-field bg-surface px-4 py-[10px] text-[13.5px] font-semibold text-body hover:bg-subtle">
            Cancel
          </Link>
        }
        onSubmit={(payload) =>
          create.mutate(
            { ...payload, name: payload.name },
            { onSuccess: (c) => navigate({ to: "/companies/$companyId", params: { companyId: String(c.id) } }) },
          )
        }
      />
    </div>
  );
}
```

- [ ] **Step 3: Create the edit page — `frontend/src/routes/edit-company.tsx`**

```tsx
import { Link, useNavigate, useParams } from "@tanstack/react-router";

import { CompanyForm } from "@/components/company-form";
import { useCompany, useUpdateCompany } from "@/lib/api/companies";

export function EditCompanyPage() {
  const { companyId } = useParams({ from: "/app/companies/$companyId/edit" });
  const id = Number(companyId);
  const navigate = useNavigate();
  const { data: company, isLoading, isError } = useCompany(id);
  const update = useUpdateCompany(id);

  if (isLoading) {
    return <div className="mx-auto max-w-[760px] px-10 pt-8 text-sm text-mute">Loading…</div>;
  }
  if (isError || !company) {
    return (
      <div className="mx-auto max-w-[760px] px-10 pt-8">
        <p className="text-sm text-destructive">Company not found.</p>
        <Link to="/companies" className="mt-2 inline-block text-sm text-brand">Back to companies</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[760px] px-10 pb-[60px] pt-[26px]">
      <div className="mb-[18px] flex items-center gap-[7px] text-[12.5px] text-mute">
        <Link to="/companies" className="hover:text-brand">Companies</Link>
        <span>/</span>
        <Link to="/companies/$companyId" params={{ companyId }} className="hover:text-brand">{company.name}</Link>
        <span>/</span>
        <span className="font-medium text-body">Edit</span>
      </div>
      <h1 className="mb-[26px] text-[24px] font-bold tracking-[-0.03em] text-ink">Edit company</h1>

      <CompanyForm
        initial={{
          name: company.name,
          website: company.website ?? "",
          industry: company.industry ?? "",
          description: company.description ?? "",
          brand_colors: company.brand_colors ?? [],
          logoUrl: company.logo_url,
        }}
        submitLabel="Save changes"
        submitting={update.isPending}
        error={update.isError}
        cancel={
          <Link to="/companies/$companyId" params={{ companyId }} className="rounded-[10px] border border-field bg-surface px-4 py-[10px] text-[13.5px] font-semibold text-body hover:bg-subtle">
            Cancel
          </Link>
        }
        onSubmit={(payload) =>
          update.mutate(payload, {
            onSuccess: () => navigate({ to: "/companies/$companyId", params: { companyId } }),
          })
        }
      />
    </div>
  );
}
```

- [ ] **Step 4: Register the edit route in `frontend/src/router.tsx`**

Add the import next to the other company-route imports:
```tsx
import { EditCompanyPage } from "@/routes/edit-company";
```
Add the route (after `companyDetailRoute`):
```tsx
const companyEditRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies/$companyId/edit",
  component: EditCompanyPage,
});
```
Add `companyEditRoute` to the `appRoute.addChildren([...])` array (order doesn't matter — the `/edit` sub-path is more specific than `$companyId`).

- [ ] **Step 5: Verify**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm build`
Expected: all pass. If `useParams({ from: "/app/companies/$companyId/edit" })` errors, use the exact generated route id the compiler expects (typecheck enforces it — the app-shell layout route is mounted under `/app`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/company-form.tsx frontend/src/routes/create-company.tsx frontend/src/routes/edit-company.tsx frontend/src/router.tsx
git commit -m "Extract shared CompanyForm; add company edit page + route"
```

---

### Task 5: Frontend — Edit/Delete on the detail page (AlertDialog)

**Files:**
- Create: `frontend/src/components/ui/alert-dialog.tsx` (shadcn)
- Modify: `frontend/src/routes/company-detail.tsx`

**Interfaces:**
- Consumes: `useDeleteCompany`, shadcn `AlertDialog`, `Button`, `Link`/`useNavigate`, phosphor icons.
- Produces: Edit link + Delete button + confirm dialog on the detail page.

- [ ] **Step 1: Add the shadcn AlertDialog component**

Run (from `frontend/`): `pnpm dlx shadcn@latest add alert-dialog --yes`
Expected: creates `frontend/src/components/ui/alert-dialog.tsx` and adds the `radix-ui`/`@radix-ui/react-alert-dialog` dep if needed. If the CLI is non-interactive-unfriendly in this environment, hand-create the file from the shadcn "new-york" `alert-dialog` source (Radix AlertDialog primitives wrapped with the project's `cn` + tokens) — it must export `AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogFooter, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel`.

- [ ] **Step 2: Add Edit + Delete to `frontend/src/routes/company-detail.tsx`**

Update the imports:
```tsx
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { CaretRight, Globe, PencilSimple, Trash } from "@phosphor-icons/react";

import { CompanyLogo } from "@/components/company-logo";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useCompany, useDeleteCompany } from "@/lib/api/companies";
```
(Do NOT wrap the shadcn `Button` in `AlertDialogTrigger asChild` — the project's `Button` is a plain function component and the Radix ref hand-off is fragile. Style the `AlertDialogTrigger` directly, as below; it renders its own button.)
Add navigation + delete inside the component (after the existing `useParams`/`useCompany` lines):
```tsx
  const navigate = useNavigate();
  const del = useDeleteCompany();
```
In the header block, add the actions to the right of the name/industry. Replace the header `<div className="mb-6 flex items-center gap-4">…</div>` with a version that adds a right-aligned action group:
```tsx
      <div className="mb-6 flex items-center gap-4">
        <CompanyLogo name={company.name} logoUrl={company.logo_url} size={56} />
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.02em] text-ink">{company.name}</h1>
          <div className="mt-1 flex items-center gap-3">
            {company.industry && (
              <span className="rounded-full bg-brand-soft px-[10px] py-[3px] text-[11.5px] font-semibold text-brand">
                {company.industry}
              </span>
            )}
            {company.website && (
              <a href={company.website} target="_blank" rel="noreferrer" className="flex items-center gap-[6px] text-[12.5px] text-subtext hover:text-brand">
                <Globe size={14} />
                {company.website}
              </a>
            )}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-[9px]">
          <Link
            to="/companies/$companyId/edit"
            params={{ companyId: String(company.id) }}
            className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-body hover:bg-subtle"
          >
            <PencilSimple size={15} />
            Edit
          </Link>
          <AlertDialog>
            <AlertDialogTrigger className="flex items-center gap-[7px] rounded-[10px] border border-field bg-surface px-[14px] py-[9px] text-[13px] font-semibold text-destructive hover:bg-subtle">
              <Trash size={15} />
              Delete
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete {company.name}?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently removes the company and its logo. This can't be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() =>
                    del.mutate(company.id, { onSuccess: () => navigate({ to: "/companies" }) })
                  }
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
```

- [ ] **Step 3: Verify**

Run (from `frontend/`): `pnpm typecheck && pnpm lint && pnpm build`
Expected: all pass (no new lint problems). If `company.id` is typed `number`, `String(company.id)` for the route param is correct.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/alert-dialog.tsx frontend/src/routes/company-detail.tsx frontend/package.json frontend/pnpm-lock.yaml
git commit -m "Add Edit link and Delete (confirm dialog) to company detail"
```

---

## Post-implementation (controller)

After all tasks pass review:
1. Merge `feat/company-crud` → `main` and push → CD deploys backend + frontend. Run the prod migration only if a new migration was created (none expected — this feature adds no model fields).
2. Prod verify: search filters the list; open a company → Edit → change a field + re-upload the logo → save → detail reflects it; Delete → confirm dialog → company removed from the list.

## Notes for the implementer
- Backend `gcs.delete_object` is best-effort and mocked in tests (`companies.api.views.gcs.delete_object`).
- The `PatchedCompany` / create-body casts mirror the existing `useCreateCompany` pattern; adjust the cast target only if `pnpm typecheck` shows a different generated schema name.
- `CompanyForm` sends `logo` only when a new file was uploaded, so an edit that doesn't touch the logo omits it and the PATCH keeps the existing logo (verified by the backend `test_patch_without_logo_keeps_existing`).
- No React Testing Library is set up; frontend tasks are verified by typecheck/lint/build.

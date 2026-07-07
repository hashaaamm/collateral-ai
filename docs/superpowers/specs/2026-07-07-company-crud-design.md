# Companies enhancements — search, edit, delete — Design

Date: 2026-07-07
Status: Approved

## Goal

Extend the existing Companies feature with **name search**, **edit**, and **delete** —
backend API + frontend UI. One cohesive feature/branch (`feat/company-crud`) because all
three touch the same files (the companies ViewSet, `companies.ts`, the company pages). Runs
in parallel with the separate Documents branch.

## Constraints

- Builds on the merged Companies feature (`companies` app, `Company` model, `gcs.py` signing,
  `CompanyViewSet`, `companies-list.tsx`, `company-detail.tsx`, `create-company.tsx`,
  `companies.ts`). Follow those established patterns.
- All infra changes (none expected here) via Pulumi. APIs require auth (`IsAuthenticated`).
- Frontend TypeScript strict; no raw hex in JSX except dynamic `brand_colors` via `style`.
  Design tokens; `pnpm lint` has one pre-existing button.tsx warning (not a finding).
- Backend `uv`/pytest via the container (`docker compose -f docker-compose.local.yml run --rm django ...`);
  frontend `pnpm` from `frontend/`. Local frontend origin is `http://localhost:3001`.

## Out of scope

Bulk delete, edit history/audit, industry/website search, the Industry filter dropdown,
optimistic UI.

---

## Backend

### `CompanyViewSet` (in `backend/collateral_ai/companies/api/views.py`)
- Add `UpdateModelMixin` + `DestroyModelMixin` to the existing
  `RetrieveModelMixin, ListModelMixin, CreateModelMixin, GenericViewSet`. Full CRUD:
  `GET /api/companies/`, `POST`, `GET/PUT/PATCH/DELETE /api/companies/{id}/`.
- **Search:** `filter_backends = [rest_framework.filters.SearchFilter]`,
  `search_fields = ["name"]`. `GET /api/companies/?search=<q>` → case-insensitive partial
  (`icontains`) match on `name`; absent/empty → all. drf-spectacular auto-adds the `search`
  query param to the schema.
- **Delete cleanup:** override `perform_destroy(instance)` to best-effort delete the logo's
  GCS object before deleting the row:
  ```python
  def perform_destroy(self, instance):
      if instance.logo and gcs.is_configured():
          gcs.delete_object(instance.logo)  # best-effort; never blocks the delete
      instance.delete()
  ```
  `gcs.delete_object` swallows its own errors.

### `gcs.py` — add `delete_object`
```python
def delete_object(object_path: str) -> None:
    """Best-effort delete of a stored object; never raises."""
    try:
        _bucket().blob(object_path).delete()
    except Exception:  # noqa: BLE001 - deletion is best-effort
        pass
```

### Edit semantics
PATCH is partial: the frontend sends `logo` only when a **new** logo is uploaded. Omitting
`logo` leaves the existing value (the write-only `logo` field is simply not touched). No
serializer change needed.

### Tests (`backend/collateral_ai/companies/tests/api/test_views.py`, extend)
- Search: `?search=acm` matches "Acme AI" (case-insensitive, partial); no `search` returns all;
  non-matching `search` returns `[]`.
- Update: PATCH `name` updates it; PATCH `logo` updates it; PATCH without `logo` leaves the
  existing logo unchanged.
- Delete: DELETE removes the row (404 afterwards); when `logo` set + configured,
  `gcs.delete_object` is called (mock `companies.api.views.gcs.delete_object`); best-effort —
  a raising delete still removes the row.
- Auth: PATCH and DELETE return 403 unauthenticated.

---

## Frontend

### API hooks (`frontend/src/lib/api/companies.ts`)
- `useCompanies(search?: string)` — pass `?search=` via `params.query` when non-empty; query
  key `["companies", { search: search ?? "" }]`.
- `useUpdateCompany(id: number)` — PATCH `/api/companies/{id}/`; on success invalidate
  `["companies"]` and `["companies", id]`.
- `useDeleteCompany()` — DELETE `/api/companies/{id}/`; on success invalidate `["companies"]`.
- Regenerate OpenAPI types after the backend changes (adds `search` param + PATCH/DELETE ops).

### Shared form refactor
Extract the create form's body into a reusable `frontend/src/components/company-form.tsx`
`CompanyForm` component:
- Props: `initialValues` (name/website/industry/description/brand_colors/logoUrl), `submitLabel`,
  `pending`, `onSubmit(values, logoObjectPath | undefined)`. Owns the fields, brand-color inputs,
  and the logo-upload flow (`requestUploadAndPut`); shows the current logo (from `initialValues.logoUrl`)
  as the initial preview when editing.
- `frontend/src/routes/create-company.tsx` → thin wrapper: `CompanyForm` with empty initials +
  `useCreateCompany` → navigate to the new detail page. (Keeps export `CreateCompanyPage` + its route.)
- `frontend/src/routes/edit-company.tsx` (new) → `EditCompanyPage`: loads `useCompany(id)`,
  renders `CompanyForm` pre-filled, submits via `useUpdateCompany(id)` (sends `logo` only if a new
  one was uploaded) → navigate back to the detail page. Breadcrumb "Companies / <name> / Edit".

### Search bar (`companies-list.tsx`)
- A search input between the header and the table: leading magnifying-glass icon, placeholder
  "Search companies…", full-width, tokens/design-matched. Local state + **~300ms debounce**
  (a small `useDebouncedValue` hook in `frontend/src/lib/use-debounced-value.ts`) drives
  `useCompanies(debounced)`.
- Empty states: existing "No companies yet" when the unfiltered list is empty; a distinct
  "No companies match “<query>”" when a search returns nothing.

### Detail page (`company-detail.tsx`)
- Header actions: an **Edit** link (→ `/companies/$companyId/edit`) and a **Delete** button.
- Delete opens a shadcn **AlertDialog** ("Delete <name>? This can't be undone."); confirm calls
  `useDeleteCompany().mutate(id)` → on success navigate to `/companies`. Add the shadcn
  `alert-dialog` component (`pnpm dlx shadcn@latest add alert-dialog`), themed to tokens.

### Routes (`router.tsx`)
- Add `/companies/$companyId/edit` → `EditCompanyPage` under the guarded app-shell layout
  (child of `appRoute`, alongside the existing company routes). Static `/companies/new` and
  `/companies/$companyId` already exist; the `/edit` sub-path won't collide.

---

## Testing

- Backend pytest (extends the existing companies API tests) — search/update/delete/auth as above.
- Frontend: `useDebouncedValue` unit test; typecheck/lint/build green.
- Prod verify after deploy: search filters the list; edit a company (incl. changing the logo);
  delete a company (confirm dialog → row gone; logo object cleaned up).

## Sequencing

One branch, sequenced in the plan: backend (viewset CRUD + search + gcs.delete + tests + schema
regen) → frontend hooks → shared `CompanyForm` refactor + edit page → search bar → detail
edit/delete + AlertDialog → prod verify. Runs in parallel with the Documents branch.

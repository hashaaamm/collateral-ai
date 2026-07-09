# Company "Last updated" field — Design

**Date:** 2026-07-08
**Status:** Approved, ready for implementation planning

## Summary

Add a **Last updated** column to the companies list page. For each company the value
reflects the most recent of two events:

1. The company record itself being changed (name, industry, website, logo, etc.).
2. A document being added to that company.

The value is stored as a denormalized `last_activity_at` column on `Company`
(chosen approach — see Alternatives), exposed through the API as `last_updated`,
and rendered as relative time (`Today`, `Yesterday`, `N days ago`, `Last week`,
older → short date).

Scope is intentionally narrow: **only** the "Last updated" column is added. The
existing columns (Company · Industry · Website · caret) are kept; the design
bundle's "Documents" count column is **not** part of this work.

## Design reference

The company list screen in the `mvp-frontend-architecture` Claude Design bundle
(`mvp-frontend-architecture/project/Collate.dc.html`) shows a "Last updated"
column with relative-time values: `Today`, `Yesterday`, `2 days ago`,
`3 days ago`, `Last week`. This design drives the frontend vocabulary and format.
(The bundle also shows a "Documents" count column and drops "Website"; those are
out of scope here — Website is kept, no Documents column is added.)

## Current state

- **Model** `backend/collateral_ai/companies/models.py` — `Company` has only
  `created_at = DateTimeField(auto_now_add=True)`. No `updated_at` /
  `last_activity_at`.
- **Document** `backend/collateral_ai/documents/models.py` — `Document` has
  `company = ForeignKey("companies.Company", related_name="documents")`,
  `created_at (auto_now_add)`, `updated_at (auto_now)`, and a `status` field
  (`pending`/`processing`/`processed`/`failed`).
- **Serializer** `backend/collateral_ai/companies/api/serializers.py` —
  `CompanySerializer` exposes `id, name, website, industry, description,
  brand_colors, logo, logo_url, created_at`.
- **ViewSet** `backend/collateral_ai/companies/api/views.py` — `CompanyViewSet`,
  `queryset = Company.objects.all()`, `SearchFilter` on `name`.
- **API client** `frontend/src/lib/api/companies.ts` — `useCompanies(search?)`
  (TanStack Query, `GET /api/companies/`), `Company` type from generated
  `frontend/src/lib/api/schema.d.ts`.
- **List page** `frontend/src/routes/companies-list.tsx` — hand-rolled CSS-grid
  "table", grid template `grid-cols-[2fr_1fr_1fr_auto]`, columns Company (logo +
  name) · Industry · Website · caret.

## Approach

### Backend

**Model — `Company.last_activity_at`**

Add:

```python
last_activity_at = models.DateTimeField(auto_now=True)
```

`auto_now=True` bumps the column on every `company.save()`, which covers the
"company record changed" half automatically. No separate `updated_at` field is
needed.

**Document signal — the "document added" half**

A `post_save` receiver on `Document`:

```python
@receiver(post_save, sender=Document)
def bump_company_last_activity(sender, instance, created, **kwargs):
    if created:
        Company.objects.filter(pk=instance.company_id).update(
            last_activity_at=instance.created_at,
        )
```

- Uses `.update()` (not `.save()`) so it writes the column directly, bypasses
  `Company.auto_now`, and stays a single cheap query.
- Uses `instance.created_at` (set by `auto_now_add` before `post_save` fires) as
  the timestamp.
- Wired following the app's existing signal pattern (register in
  `documents/apps.py` `ready()` or a `documents/signals.py`, matching whatever
  convention already exists in the repo).

**Risk to verify during planning:** `post_save` does **not** fire for
`bulk_create`. Check the document-ingestion creation path
(`backend/collateral_ai/documents/`): if documents are ever created via
`bulk_create`, add an explicit company bump at that call site instead of relying
solely on the signal.

**Migrations**

1. Schema migration adding `last_activity_at`.
2. Data migration backfilling existing rows so the column is correct from day one
   rather than all set to `now()`:

   ```
   last_activity_at = max(company.created_at, latest document.created_at for that company)
   ```

   (For companies with no documents this is just `created_at`.)

**Serializer**

Expose read-only, mapped from the model field to the domain term:

```python
last_updated = serializers.DateTimeField(source="last_activity_at", read_only=True)
```

Add `last_updated` to `Meta.fields` and `read_only_fields`.

**OpenAPI schema**

Regenerate the backend OpenAPI schema and re-run the frontend type generation so
`frontend/src/lib/api/schema.d.ts` `Company` gains
`readonly last_updated: string` (date-time).

**Ordering:** unchanged (`Meta.ordering = ["-created_at"]`). Out of scope.
Note: the denormalized column makes ordering/sorting by `last_activity_at` cheap
and indexable if desired later.

### Frontend

**Relative-time helper**

New `formatRelativeDay(iso: string): string` (co-located with other list/date
utilities, following existing conventions):

| Condition (calendar-day based, local time) | Output      |
| ------------------------------------------ | ----------- |
| Same calendar day as today                 | `Today`     |
| Previous calendar day                      | `Yesterday` |
| 2–6 days ago                               | `N days ago`|
| 7–13 days ago                              | `Last week` |
| 14+ days ago                               | short date, e.g. `12 Jun` |

Boundaries are by calendar day, not raw 24h deltas (so 11pm yesterday → 1am today
reads as `Yesterday`, not `Today`).

**List page — `companies-list.tsx`**

- Widen the grid template from `grid-cols-[2fr_1fr_1fr_auto]` to
  `grid-cols-[2fr_1fr_1fr_1fr_auto]` on both the header row and the data rows.
- Add a "Last updated" header cell after "Website".
- Add a data cell rendering `formatRelativeDay(c.last_updated)`, styled like the
  other muted secondary cells (e.g. `text-inkMuted` / matching existing token).

## Alternatives considered

- **A — Queryset annotation** (`Greatest(updated_at, MAX(documents.created_at))`
  computed per request). Decoupled, always accurate, no denormalization, but adds
  a join+group-by per list read and the annotation must be present wherever the
  field is serialized. Rejected in favor of B.
- **C — Touch-on-create only** (`Company.updated_at` + `Document` create calls
  `company.save(update_fields=["updated_at"])`). Single field but puts a
  `save()` side effect in the document write path. Rejected in favor of B.
- **B — Denormalized `last_activity_at` (chosen).** Real column bumped by
  company `auto_now` and a document `post_save` signal. Cheap sortable/indexable
  reads; cost is signal wiring, a backfill migration, and the `bulk_create` caveat
  above.

## Testing

**Backend**

- New company, no documents → `last_updated == last_activity_at == created_at`.
- Add a document (via `.save()`) dated after the company → `last_updated` reflects
  the document's `created_at`.
- Edit the company after adding the document → `last_updated` bumps to the edit
  time (auto_now).
- Data-migration backfill: a company with an older `created_at` but a newer
  document ends up with `last_activity_at` == the document's `created_at`.

**Frontend**

- Unit tests for `formatRelativeDay` at each boundary: today, yesterday, 2 days
  ago, 6 days ago, 7 days ago (`Last week`), 14+ days ago (short date). Include
  the late-night calendar-boundary case.

## Out of scope

- The "Documents" count column from the design bundle.
- Removing the "Website" column.
- Changing list ordering / adding a sort control.

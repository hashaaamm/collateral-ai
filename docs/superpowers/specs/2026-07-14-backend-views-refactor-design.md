# Backend views refactor — thin views + services (AGENTS.md compliance)

**Date:** 2026-07-14
**Status:** Approved

## Problem

The five DRF API modules drifted from the house style that `backend/AGENTS.md` mandates
("views stay empty"; serializers validate and call services; `<app>/services.py` owns business
operations; domain errors mapped by a DRF exception handler; filter with django-filter).
Concretely:

1. **Validation bypassing serializers** — `documents` `create` and `companies`
   `logo-upload-url` hand-parse `request.data.get(...)`, build 400 responses manually, and
   assemble responses with dict-merges and `inline_serializer`.
2. **Business logic in views** — `materials` views carry worker-dispatch fallback logic
   (`_dispatch`) and the whole regenerate choreography (row locking, staleness policy,
   field resets); `documents` views orchestrate GCS + worker dispatch; GCS delete
   side-effects live in two `perform_destroy` overrides.
3. **Hand-rolled filtering** — `materials` `get_queryset` parses query params with a private
   `_int_param` helper and hand-declared OpenAPI parameters.

`users` and the `Template` ViewSet are already compliant and are not touched.

## Constraints (user-confirmed)

- **Wire-identical** for all success responses and status codes. OpenAPI **component names may
  change** (frontend regenerates its typed client with `pnpm gen:api`).
- Drivers: **consistent pattern for future apps** + **general code health**. No heavier
  architecture than AGENTS.md already prescribes (no selectors-everywhere, no
  APIView-per-operation).
- **django-filter approved** as a new dependency (`uv add`).

### Approved wire deviations (the only two)

1. **Invalid filter values**: `?sender=abc` on the materials list is silently ignored today
   (returns the full unfiltered list); with django-filter it becomes a **400**. Accepted as a
   bug fix.
2. **Hand-rolled 400 bodies**: `documents` `create` and `companies` `logo-upload-url` today
   return `{"detail": "<one combined sentence>"}` on bad input; with input serializers they
   return DRF-standard field-keyed errors (e.g. `{"content_type": ["…is not a valid
   choice."]}`), matching every other endpoint.

## Architecture — the recipe every endpoint follows

1. **View = wiring only**: queryset (+ `select_related`), `get_serializer_class`,
   `filterset_class`, permissions, `@extend_schema`. No `request.data.get()`, no
   transactions, no GCS/worker calls, no status-code branching on business state.
2. **Serializer = validation + shaping.** Write serializers' `create()`/`update()` call a
   service for anything beyond a trivial single-model save (per AGENTS.md). Response shapes
   get real named serializers; `inline_serializer` usage is removed.
3. **Service (`<app>/services.py`)** = plain functions performing one unit of business work,
   `@transaction.atomic` where appropriate, callable from serializers, viewset actions, and
   management commands. Services never touch `request`/`Response`.
4. **Domain errors**: new plain package `collateral_ai/core/` with `core/exceptions.py`
   defining `DomainError(Exception)` carrying `status_code` and `detail`. Concrete errors:
   - `StorageNotConfigured` → 503
   - `GenerationInProgress` → 409
   - `NoStoredFile` → 404

   A custom handler `config/exception_handler.py`, registered as
   `REST_FRAMEWORK["EXCEPTION_HANDLER"]`, renders any `DomainError` as `{"detail": ...}` with
   its status (byte-identical to today's bodies) and delegates everything else to DRF's
   default handler.
5. **Filtering**: `DjangoFilterBackend` + declarative `FilterSet` per list endpoint that
   filters. Filter params appear in the OpenAPI schema automatically.

**Call-shape rule:** ModelSerializer-backed creates/updates route through
`serializer.create()/update()` → service. Command-style endpoints (signed-URL issuance,
complete, regenerate) validate input with a serializer, then the **view calls the service
directly** — still zero business logic in the view.

## Per-app changes

### materials

- **New `materials/services.py`**
  - `create_material(**validated_data) -> MarketingMaterial` — create row → dispatch →
    return refreshed instance. Called from `MaterialCreateSerializer.create()`.
  - `dispatch_generation(material) -> None` — the current `_dispatch`: inner
    `transaction.atomic()` savepoint around `trigger_generation`, on failure mark row FAILED
    with the generic user-facing message (constant moves here) and log the real exception;
    on success persist `job_operation_name`.
  - `regenerate_material(material, *, prompt=None) -> MarketingMaterial` — locked re-fetch
    (`select_for_update`), active-and-not-stale check (`STALE_AFTER = 15 min` moves here),
    raises `GenerationInProgress`, applies optional new prompt, resets generation/review
    fields, deletes sources, dispatches, returns refreshed instance.
- **New `materials/api/filters.py`**: `MaterialFilter` — `company` as a method filter
  (sender OR receiver), `sender`/`receiver` as `NumberFilter`, `generation_status`/
  `review_status` as `CharFilter` (not `ChoiceFilter`, so an unknown status string still
  yields an empty list rather than a new 400). Deletes `LIST_FILTER_PARAMS`, `_int_param`,
  the `get_queryset` param parsing, and the `extend_schema_view` wrapper.
- **Views**: `create()` override remains only to render `MaterialDetailSerializer` at 201
  (wire compat): validate → `serializer.save()` → render. `regenerate` becomes: validate
  body → `services.regenerate_material(...)` → render detail at 202. `get_serializer_class`
  stays. `TemplateViewSet` unchanged.

### documents

- **New `documents/services.py`**
  - `create_document_with_upload_url(*, company_id, file_name, content_type)
    -> tuple[Document, str]` — raises `StorageNotConfigured`; creates the row, builds the
    object path, saves it, signs the upload URL. (ATOMIC_REQUESTS still guarantees no orphan
    PENDING row if signing raises.)
  - `start_processing(document) -> Document` — status → PROCESSING, clear error, call
    `trigger_processing`; on dispatch failure mark FAILED with the generic message; return
    refreshed instance.
  - `get_view_url(document) -> str` — raises `StorageNotConfigured` / `NoStoredFile`.
  - `delete_document(document) -> None` — GCS delete when configured + row delete.
- **Serializers**: `DocumentCreateSerializer` (`file_name` `CharField(max_length=255)`,
  `content_type` `ChoiceField(["application/pdf"])`), `DocumentWithUploadUrlSerializer`
  (`DocumentSerializer` + `upload_url`) for the 201 body, `DocumentViewUrlSerializer`
  (`{"url": ...}`). All `inline_serializer` blocks and the dict-merge removed.
- **Views**: `create` = validate input serializer → service → response serializer, 201.
  `complete` = `get_object` → `services.start_processing` → serializer, 202. `view_url` =
  `get_object` → `services.get_view_url` → serializer. `perform_destroy` →
  `services.delete_document`.

### companies

- **New `companies/services.py`**: `create_logo_upload_url(*, filename, content_type)
  -> tuple[str, str]` (raises `StorageNotConfigured`; returns `(upload_url, object_path)`),
  `delete_company(company)` (logo GCS cleanup + delete).
- **Serializers**: `LogoUploadUrlRequestSerializer` (`filename` `CharField`, `content_type`
  `ChoiceField` over the allowed image types — the allowed-types set moves out of the view),
  `LogoUploadUrlResponseSerializer`.
- **Views**: action = validate → service → response serializer; `perform_destroy` →
  `services.delete_company`.

### dashboard

- **New `dashboard/selectors.py`** (pure read → AGENTS.md's optional selectors slot):
  `get_dashboard_stats() -> dict` with the five aggregate counts. The `APIView` just renders
  it through `DashboardStatsSerializer`.

### users

- Untouched — already compliant.

## Testing

Per AGENTS.md: test the layers where the logic is.

- **Existing endpoint tests are the regression net** — they pin the HTTP contract and must
  pass unchanged, *except* tests pinning the two approved wire deviations (old 400 bodies,
  silently-ignored invalid filter params), which are updated deliberately and called out in
  the PR.
- **New unit tests for services** (direct calls, no HTTP): dispatch failure → FAILED row +
  generic message; regenerate 409-conflict vs stale-takeover paths; create-document
  path/URL assembly and unconfigured-storage error; delete cleanup calling GCS.
- No new endpoint tests beyond the deviation updates — coverage moves down a layer.

## Verification (in order)

1. `pytest -n auto --reuse-db` — full suite green.
2. `ruff` / pre-commit clean (PLC0415: imports at top of new modules; SLF001: no
   private-member access in tests — public service functions replace `_dispatch`).
3. Regenerate the OpenAPI schema and **diff it**: only component renames (inline → named
   serializers) and FilterSet-generated params replacing hand-declared ones may appear.
   Anything else is a refactor bug.
4. Local stack smoke from the **main checkout** (worktree has docker container-name
   collisions): create company → logo-upload URL → create material → regenerate.
5. Frontend `pnpm gen:api` — typed client compiles with only renamed types.

## Out of scope

- Contract improvements (error-shape redesign, status-code fixes) beyond the two approved
  deviations.
- Selectors beyond the dashboard; APIView-per-operation; repository patterns.
- Any change to `users`, `Template` endpoints, auth, permissions, or pagination.

# LangGraph + LangSmith Material Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-architect Worker 2 (material generation) as a cyclic LangGraph pipeline on a provider-swappable LangChain model layer, traced to LangSmith Cloud, with an offline eval harness for prompt-tuning and model-comparison.

**Architecture:** `_claim` (raw Django) → `build_generation_graph().invoke(state)` (LangGraph: retrieve → generate → validate ⇄ repair → END) → `_save_completed` (raw Django). The model call goes through a LangChain chat model bound to a per-template dynamic structured-output schema. LangSmith tracing is env-driven and no-op without keys. An offline eval module seeds a golden dataset and runs graded experiments.

**Tech Stack:** Django, LangGraph, LangChain (`langchain-google-vertexai`), LangSmith, Vertex AI Gemini (keyless ADC), pgvector, pytest.

## Global Constraints

- **No backward compatibility.** No feature flag, no dual path, no shims. `collateral_ai/materials/generation/llm.py` and `repair.py` are DELETED; the graph is the only path.
- **Must not break.** Existing API tests (`collateral_ai/materials/tests/api/test_material_views.py`) stay green; a real end-to-end generation run must produce a `COMPLETED` `MarketingMaterial` with `GenerationSource` rows.
- **Output contract unchanged.** The graph produces the same `output` dict and `context_snapshot` that `_save_completed` consumes today. DB statuses, `--force`/`--top-k` flags, and the API are identical.
- **Template model is named `Template`** (not `MaterialTemplate`), in `collateral_ai/materials/models.py`.
- **Lint gates:** ruff PLC0415 (no inline imports except the established lazy-import pattern for heavy libs) and SLF001 apply. Heavy libs (`google.genai`, `langchain_*`, `langgraph`) follow the existing lazy-import-inside-method pattern with `# noqa: PLC0415` where needed.
- **Lockfile gate:** after editing `pyproject.toml`, regenerate and commit `uv.lock` or CI blocks.
- **Tests run via:** `just pytest <args>` (wraps `docker compose run --rm django pytest`). In a worktree, container-name collisions with the main checkout can occur — stop the main stack first if needed.
- **DB tests** use `@pytest.mark.django_db`. Factories live in `collateral_ai/<app>/tests/factories.py`.

---

### Task 1: Add dependencies, settings, and LangSmith env forwarding

**Files:**
- Modify: `backend/pyproject.toml` (dependencies array)
- Modify: `backend/config/settings/base.py` (after the `MATERIAL_*` block ~line 358)
- Modify: `backend/collateral_ai/worker_jobs.py:24-32` (`_FORWARDED_ENV`)
- Test: `backend/collateral_ai/materials/tests/generation/test_config.py` (create)

**Interfaces:**
- Produces: settings `MATERIAL_LLM_PROVIDER: str` (default `"vertex"`), `MATERIAL_EVAL_JUDGE_MODEL: str`, `LANGSMITH_TRACING`/`LANGSMITH_API_KEY`/`LANGSMITH_PROJECT` read from env; `worker_jobs._FORWARDED_ENV` includes the three `LANGSMITH_*` names.

- [ ] **Step 1: Write the failing test**

Create `backend/collateral_ai/materials/tests/generation/__init__.py` (empty) and `backend/collateral_ai/materials/tests/generation/test_config.py`:

```python
from django.conf import settings

from collateral_ai.worker_jobs import _FORWARDED_ENV


def test_material_llm_provider_defaults_to_vertex():
    assert settings.MATERIAL_LLM_PROVIDER == "vertex"


def test_eval_judge_model_setting_present():
    assert settings.MATERIAL_EVAL_JUDGE_MODEL


def test_langsmith_env_forwarded_to_worker_pod():
    for name in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
        assert name in _FORWARDED_ENV


def test_langgraph_importable():
    import langgraph.graph  # noqa: F401
    import langchain_google_vertexai  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_config.py -v`
Expected: FAIL — `AttributeError: MATERIAL_LLM_PROVIDER` / `ModuleNotFoundError: langgraph`.

- [ ] **Step 3: Add dependencies**

In `backend/pyproject.toml`, add to the `dependencies` array (near `google-genai==1.28.0`):

```toml
  "langgraph==0.2.61",
  "langchain-google-vertexai==2.0.7",
  "langsmith==0.1.147",
```

(Use the latest compatible versions your resolver picks; pin exact resolved versions.)

- [ ] **Step 4: Regenerate the lockfile**

Run: `cd backend && uv lock`
Expected: `uv.lock` updated with the new packages.

- [ ] **Step 5: Add settings**

In `backend/config/settings/base.py`, after the `MATERIAL_MAX_REPAIR_ATTEMPTS` line:

```python
MATERIAL_LLM_PROVIDER = env("MATERIAL_LLM_PROVIDER", default="vertex")
MATERIAL_EVAL_JUDGE_MODEL = env("MATERIAL_EVAL_JUDGE_MODEL", default="gemini-2.5-flash")

# LangSmith tracing (no-op when LANGSMITH_TRACING is unset/false).
LANGSMITH_TRACING = env("LANGSMITH_TRACING", default="")
LANGSMITH_API_KEY = env("LANGSMITH_API_KEY", default="")
LANGSMITH_PROJECT = env("LANGSMITH_PROJECT", default="collateral-material-gen")
```

- [ ] **Step 6: Forward LangSmith env to the worker pod**

In `backend/collateral_ai/worker_jobs.py`, add to the `_FORWARDED_ENV` tuple:

```python
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `just pytest collateral_ai/materials/tests/generation/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/config/settings/base.py \
  backend/collateral_ai/worker_jobs.py \
  backend/collateral_ai/materials/tests/generation/
git commit -m "feat(materials): add langgraph/langsmith deps, settings, env forwarding"
```

---

### Task 2: Provider-swappable LangChain model layer (`model.py`)

**Files:**
- Create: `backend/collateral_ai/materials/generation/model.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_model.py` (create)

**Interfaces:**
- Consumes: settings `MATERIAL_LLM_PROVIDER`, `MATERIAL_LLM_MODEL`, `MATERIAL_GENERATION_TEMPERATURE`, `MATERIAL_GENERATION_MAX_OUTPUT_TOKENS`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`.
- Produces: `class GenerationModel` with `generate_structured(*, system_instruction: str, user_input: str, response_schema: dict) -> dict`. The `_build_chat_model()` method is separated so tests can patch it.

- [ ] **Step 1: Write the failing test**

Create `backend/collateral_ai/materials/tests/generation/test_model.py`:

```python
from unittest.mock import MagicMock

from collateral_ai.materials.generation.model import GenerationModel


def test_generate_structured_binds_schema_and_returns_dict(monkeypatch):
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {"article": {"headline": "Hi"}}
    fake_chat = MagicMock()
    fake_chat.with_structured_output.return_value = fake_structured

    model = GenerationModel()
    monkeypatch.setattr(model, "_build_chat_model", lambda: fake_chat)

    schema = {"type": "OBJECT", "properties": {}}
    result = model.generate_structured(
        system_instruction="sys",
        user_input="user",
        response_schema=schema,
    )

    assert result == {"article": {"headline": "Hi"}}
    fake_chat.with_structured_output.assert_called_once()
    # schema passed through (converted or raw — both acceptable)
    fake_structured.invoke.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError: ...generation.model`.

- [ ] **Step 3: Write the implementation**

Create `backend/collateral_ai/materials/generation/model.py`:

```python
"""Provider-swappable LangChain chat model for structured generation.

Default provider is Vertex AI Gemini (keyless ADC), same auth as
documents.processing.embeddings. Provider is selected by MATERIAL_LLM_PROVIDER
so the model can be swapped (e.g. Claude on Vertex, OpenAI) without touching the
graph.
"""

from __future__ import annotations

from django.conf import settings


class GenerationModel:
    def __init__(self) -> None:
        self.provider = settings.MATERIAL_LLM_PROVIDER
        self.model = settings.MATERIAL_LLM_MODEL
        self.temperature = float(settings.MATERIAL_GENERATION_TEMPERATURE)
        self.max_output_tokens = int(settings.MATERIAL_GENERATION_MAX_OUTPUT_TOKENS)

    def _build_chat_model(self):
        if self.provider == "vertex":
            from langchain_google_vertexai import ChatVertexAI  # noqa: PLC0415

            return ChatVertexAI(
                model=self.model,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.VERTEX_LOCATION,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                # Disable thinking so the full budget goes to JSON output.
                thinking_budget=0,
            )
        msg = f"Unsupported MATERIAL_LLM_PROVIDER: {self.provider}"
        raise ValueError(msg)

    def generate_structured(
        self,
        *,
        system_instruction: str,
        user_input: str,
        response_schema: dict,
    ) -> dict:
        from langchain_core.messages import HumanMessage  # noqa: PLC0415
        from langchain_core.messages import SystemMessage  # noqa: PLC0415

        chat = self._build_chat_model()
        structured = chat.with_structured_output(response_schema)
        result = structured.invoke(
            [
                SystemMessage(content=system_instruction),
                HumanMessage(content=user_input),
            ],
        )
        if not isinstance(result, dict):
            # with_structured_output may return a pydantic model; normalize.
            result = dict(result)
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `just pytest collateral_ai/materials/tests/generation/test_model.py -v`
Expected: PASS.

- [ ] **Step 5: Verify schema dialect against a real call (implementation-discovery step)**

Run a throwaway Django shell call (or the E2E in Task 8) once with a real Vertex schema. If `with_structured_output(response_schema)` raises a schema-dialect error, add this converter to `model.py` and pass `_to_json_schema(response_schema)`:

```python
_TYPE_MAP = {"OBJECT": "object", "STRING": "string", "ARRAY": "array",
             "INTEGER": "integer", "NUMBER": "number", "BOOLEAN": "boolean"}


def _to_json_schema(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "type" and isinstance(value, str):
                out[key] = _TYPE_MAP.get(value, value.lower())
            else:
                out[key] = _to_json_schema(value)
        return out
    if isinstance(node, list):
        return [_to_json_schema(item) for item in node]
    return node
```

Only add this if the raw dict is rejected. Re-run Task 2 tests after any change.

- [ ] **Step 6: Commit**

```bash
git add backend/collateral_ai/materials/generation/model.py \
  backend/collateral_ai/materials/tests/generation/test_model.py
git commit -m "feat(materials): provider-swappable LangChain generation model"
```

---

### Task 3: Dynamic-enum source_id schema hardening

**Files:**
- Modify: `backend/collateral_ai/materials/generation/schema.py:19-30` (`build_response_schema`)
- Test: `backend/collateral_ai/materials/tests/generation/test_schema.py` (create)

**Interfaces:**
- Produces: `build_response_schema(*, constraints: dict, image_slots: list[dict], allowed_source_ids: list[str] | None = None) -> dict`. When `allowed_source_ids` is non-empty, the `source_references.items.properties.source_id` gains `"enum": allowed_source_ids`.
- NOTE: callers in Task 4 (`generate`/`repair` nodes) must pass `allowed_source_ids=sorted(state["allowed_ids"])`.

- [ ] **Step 1: Write the failing test**

Create `backend/collateral_ai/materials/tests/generation/test_schema.py`:

```python
from collateral_ai.materials.generation.schema import build_response_schema


def test_source_id_constrained_to_allowed_enum():
    schema = build_response_schema(
        constraints={"body_section_count": 2},
        image_slots=[],
        allowed_source_ids=["SENDER_SOURCE_1", "RECEIVER_SOURCE_1"],
    )
    source_id = schema["properties"]["source_references"]["items"]["properties"][
        "source_id"
    ]
    assert source_id["enum"] == ["SENDER_SOURCE_1", "RECEIVER_SOURCE_1"]


def test_source_id_unconstrained_when_no_ids():
    schema = build_response_schema(
        constraints={"body_section_count": 2},
        image_slots=[],
        allowed_source_ids=[],
    )
    source_id = schema["properties"]["source_references"]["items"]["properties"][
        "source_id"
    ]
    assert "enum" not in source_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_schema.py -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'allowed_source_ids'`.

- [ ] **Step 3: Modify `build_response_schema`**

In `backend/collateral_ai/materials/generation/schema.py`, change the signature and the `source_id` property:

```python
def build_response_schema(
    *,
    constraints: dict,
    image_slots: list[dict],
    allowed_source_ids: list[str] | None = None,
) -> dict[str, Any]:
    section_count = int(constraints["body_section_count"])
    slot_ids = [slot["slot_id"] for slot in image_slots]
    slot_id_property: dict[str, Any] = {"type": "STRING"}
    if slot_ids:
        slot_id_property["enum"] = slot_ids
    source_id_property: dict[str, Any] = {"type": "STRING"}
    if allowed_source_ids:
        # Structurally prevent hallucinated citations (defense-in-depth with
        # OutputValidator's source check).
        source_id_property["enum"] = list(allowed_source_ids)
```

Then in the returned dict, replace the `source_references.items.properties.source_id` value `{"type": "STRING"}` with `source_id_property`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest collateral_ai/materials/tests/generation/test_schema.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/schema.py \
  backend/collateral_ai/materials/tests/generation/test_schema.py
git commit -m "feat(materials): constrain source_id to dynamic enum of retrieved ids"
```

---

### Task 4: The generation graph (`graph.py`)

**Files:**
- Create: `backend/collateral_ai/materials/generation/graph.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_graph.py` (create)

**Interfaces:**
- Consumes: `GenerationModel.generate_structured` (Task 2), `build_response_schema` (Task 3), `EmbeddingService`, `RetrievalService`, `OutputValidator`, prompt builders.
- Produces:
  - `GenerationState` (TypedDict).
  - `build_generation_graph(*, embedder, retriever, model, validator, max_repair_attempts) -> CompiledGraph` — a compiled LangGraph. Its `.invoke(initial_state)` returns the final state with keys `output`, `is_valid`, `validation_errors`, `attempts`, `context_snapshot`, `source_map`, `allowed_ids`.
  - Node functions are pure `(state) -> partial_state` closures over the injected services.

- [ ] **Step 1: Write the failing test (repair cycle behavior)**

Create `backend/collateral_ai/materials/tests/generation/test_graph.py`:

```python
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from collateral_ai.materials.generation.graph import build_generation_graph


@dataclass
class FakeChunk:
    source_id: str
    company_id: int = 1
    document_id: int = 1
    chunk_id: int = 1
    page_number: int = 1
    content: str = "fact text"
    relevance_score: float = 0.1
    source_role: str = "sender"

    def to_prompt_dict(self):
        return {"source_id": self.source_id, "content": self.content}


def _template():
    tmpl = MagicMock()
    tmpl.slug = "newsletter_article_v1"
    tmpl.theme = {"primary_color": "#000"}
    tmpl.constraints = {
        "headline_max_words": 10, "subheadline_max_words": 22,
        "body_section_count": 1, "body_section_max_words": 80, "cta_max_words": 15,
    }
    tmpl.image_slots = []
    return tmpl


def _material(tmpl):
    m = MagicMock()
    m.pk = 1
    m.sender_company_id = 1
    m.receiver_company_id = 2
    m.template = tmpl
    m.cta_link = ""
    return m


def _valid_output():
    return {
        "article": {
            "headline": "Short headline",
            "subheadline": "Sub",
            "body_sections": [{"title": "T", "text": "body text"}],
            "cta": "Act now",
        },
        "image_slots": [],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


def _initial_state(tmpl, material):
    return {
        "material_id": 1, "material": material, "template": tmpl, "top_k": 4,
        "attempts": 0,
    }


def _services(model):
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.0] * 768
    retriever = MagicMock()
    retriever.retrieve.side_effect = lambda **kw: [
        FakeChunk(source_id="SENDER_SOURCE_1")
    ] if kw["source_role"] == "sender" else [FakeChunk(source_id="RECEIVER_SOURCE_1",
                                                        source_role="receiver")]
    from collateral_ai.materials.generation.validation import OutputValidator
    return embedder, retriever, OutputValidator()


@pytest.mark.django_db
def test_graph_repairs_once_then_succeeds():
    tmpl, = (_template(),)
    material = _material(tmpl)
    model = MagicMock()
    invalid = {"article": {"headline": "x " * 40, "subheadline": "s",
                           "body_sections": [{"title": "T", "text": "b"}], "cta": "c"},
               "image_slots": [], "source_references": [
                   {"source_id": "SENDER_SOURCE_1", "used_fact": "f"}]}
    model.generate_structured.side_effect = [invalid, _valid_output()]
    embedder, retriever, validator = _services(model)

    graph = build_generation_graph(embedder=embedder, retriever=retriever,
                                    model=model, validator=validator,
                                    max_repair_attempts=2)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["is_valid"] is True
    assert final["attempts"] == 1
    assert model.generate_structured.call_count == 2


@pytest.mark.django_db
def test_graph_fails_after_max_attempts():
    tmpl = _template()
    material = _material(tmpl)
    model = MagicMock()
    invalid = {"article": {"headline": "x " * 40, "subheadline": "s",
                           "body_sections": [{"title": "T", "text": "b"}], "cta": "c"},
               "image_slots": [], "source_references": [
                   {"source_id": "SENDER_SOURCE_1", "used_fact": "f"}]}
    model.generate_structured.return_value = invalid
    embedder, retriever, validator = _services(model)

    graph = build_generation_graph(embedder=embedder, retriever=retriever,
                                   model=model, validator=validator,
                                   max_repair_attempts=2)
    final = graph.invoke(_initial_state(tmpl, material))

    assert final["is_valid"] is False
    assert final["attempts"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: ...generation.graph`.

- [ ] **Step 3: Write the graph implementation**

Create `backend/collateral_ai/materials/generation/graph.py`:

```python
"""LangGraph pipeline for material generation: retrieve → generate → validate ⇄ repair.

Nodes wrap the existing domain services (retrieval, validation, prompts). The
validate → repair → validate cycle replaces the imperative while-loop; the
conditional edge routes on is_valid and attempts.
"""

from __future__ import annotations

from typing import Any
from typing import TypedDict

from collateral_ai.materials.generation.prompts import REPAIR_SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_generation_payload
from collateral_ai.materials.generation.prompts import build_repair_payload
from collateral_ai.materials.generation.schema import build_response_schema
from collateral_ai.materials.statuses import SourceRole


class GenerationState(TypedDict, total=False):
    material_id: int
    material: Any
    template: Any
    top_k: int
    query_embedding: list[float]
    sender_chunks: list[Any]
    receiver_chunks: list[Any]
    source_map: dict[str, Any]
    allowed_ids: set[str]
    response_schema: dict
    output: dict
    validation_errors: list[dict]
    is_valid: bool
    attempts: int
    context_snapshot: dict


def _stamp(output: dict, template, material) -> dict:
    output["template_id"] = template.slug
    output["theme"] = dict(template.theme)
    if material.cta_link:
        output.setdefault("article", {})["cta_url"] = material.cta_link
    return output


def build_generation_graph(
    *,
    embedder,
    retriever,
    model,
    validator,
    max_repair_attempts: int,
):
    from langgraph.graph import END  # noqa: PLC0415
    from langgraph.graph import START  # noqa: PLC0415
    from langgraph.graph import StateGraph  # noqa: PLC0415

    def retrieve(state: GenerationState) -> dict:
        from collateral_ai.materials.generation.prompts import (  # noqa: PLC0415
            build_retrieval_query,
        )

        material = state["material"]
        top_k = state["top_k"]
        query_embedding = embedder.embed_query(build_retrieval_query(material))
        sender_chunks = retriever.retrieve(
            company_id=material.sender_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.SENDER,
            source_prefix="SENDER_SOURCE",
            top_k=top_k,
        )
        receiver_chunks = retriever.retrieve(
            company_id=material.receiver_company_id,
            query_embedding=query_embedding,
            source_role=SourceRole.RECEIVER,
            source_prefix="RECEIVER_SOURCE",
            top_k=top_k,
        )
        for role, chunks, company in (
            ("sender", sender_chunks, material.sender_company),
            ("receiver", receiver_chunks, material.receiver_company),
        ):
            if not chunks:
                msg = (
                    f"No processed document chunks for {role} company "
                    f"{company.name!r} — upload and process documents first."
                )
                raise ValueError(msg)
        source_map = {c.source_id: c for c in [*sender_chunks, *receiver_chunks]}
        allowed_ids = set(source_map)
        response_schema = build_response_schema(
            constraints=state["template"].constraints,
            image_slots=state["template"].image_slots,
            allowed_source_ids=sorted(allowed_ids),
        )
        context_snapshot = {
            "sender_context": [c.to_prompt_dict() for c in sender_chunks],
            "receiver_context": [c.to_prompt_dict() for c in receiver_chunks],
        }
        return {
            "query_embedding": query_embedding,
            "sender_chunks": sender_chunks,
            "receiver_chunks": receiver_chunks,
            "source_map": source_map,
            "allowed_ids": allowed_ids,
            "response_schema": response_schema,
            "context_snapshot": context_snapshot,
        }

    def generate(state: GenerationState) -> dict:
        output = model.generate_structured(
            system_instruction=SYSTEM_INSTRUCTION,
            user_input=build_generation_payload(
                material=state["material"],
                sender_chunks=state["sender_chunks"],
                receiver_chunks=state["receiver_chunks"],
            ),
            response_schema=state["response_schema"],
        )
        return {"output": _stamp(output, state["template"], state["material"])}

    def validate(state: GenerationState) -> dict:
        result = validator.validate(
            output=state["output"],
            constraints=state["template"].constraints,
            image_slots=state["template"].image_slots,
            allowed_source_ids=state["allowed_ids"],
        )
        return {"is_valid": result.is_valid, "validation_errors": result.errors}

    def repair(state: GenerationState) -> dict:
        output = model.generate_structured(
            system_instruction=REPAIR_SYSTEM_INSTRUCTION,
            user_input=build_repair_payload(
                output=state["output"],
                errors=state["validation_errors"],
                constraints=state["template"].constraints,
                image_slots=state["template"].image_slots,
                allowed_source_ids=sorted(state["allowed_ids"]),
            ),
            response_schema=state["response_schema"],
        )
        return {
            "output": _stamp(output, state["template"], state["material"]),
            "attempts": state["attempts"] + 1,
        }

    def route_after_validate(state: GenerationState) -> str:
        if state["is_valid"]:
            return END
        if state["attempts"] >= max_repair_attempts:
            return END
        return "repair"

    builder = StateGraph(GenerationState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("generate", generate)
    builder.add_node("validate", validate)
    builder.add_node("repair", repair)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "validate")
    builder.add_conditional_edges(
        "validate", route_after_validate, {"repair": "repair", END: END},
    )
    builder.add_edge("repair", "validate")
    return builder.compile()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest collateral_ai/materials/tests/generation/test_graph.py -v`
Expected: PASS (2 tests) — repair-once-then-succeed and fail-after-max.

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/graph.py \
  backend/collateral_ai/materials/tests/generation/test_graph.py
git commit -m "feat(materials): LangGraph generation pipeline with repair cycle"
```

---

### Task 5: Rewire service, delete `llm.py` and `repair.py`

**Files:**
- Modify: `backend/collateral_ai/materials/generation/service.py` (replace `_run_pipeline`, drop `_stamp`/`_validate`, update `__init__`)
- Delete: `backend/collateral_ai/materials/generation/llm.py`
- Delete: `backend/collateral_ai/materials/generation/repair.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_service.py` (create)

**Interfaces:**
- Consumes: `build_generation_graph` (Task 4), `GenerationModel` (Task 2), `EmbeddingService`, `RetrievalService`, `OutputValidator`.
- Produces: `MaterialGenerationService.generate(material_id, *, force=False, top_k=None) -> bool` — unchanged signature and DB side-effects (`_claim` / `_save_completed` unchanged).

- [ ] **Step 1: Write the failing test**

Create `backend/collateral_ai/materials/tests/generation/test_service.py`:

```python
from unittest.mock import MagicMock

import pytest

from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import GenerationSource
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.materials.statuses import GenerationStatus
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.documents.tests.factories import DocumentChunkFactory


def _valid_output():
    return {
        "article": {
            "headline": "Short headline", "subheadline": "Sub",
            "body_sections": [{"title": "T", "text": "body text"},
                              {"title": "T2", "text": "body text two"}],
            "cta": "Act now",
        },
        "image_slots": [
            {"slot_id": "hero_image", "description": "d", "source": "generated_placeholder"},
            {"slot_id": "sender_logo", "description": "d", "source": "sender"},
        ],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


@pytest.mark.django_db
def test_generate_completes_and_saves(monkeypatch):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    DocumentChunkFactory(company=material.sender_company)
    DocumentChunkFactory(company=material.receiver_company)

    fake_model = MagicMock()
    fake_model.generate_structured.return_value = _valid_output()
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.GenerationModel",
        lambda: fake_model,
    )
    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.0] * 768
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.EmbeddingService",
        lambda: fake_embedder,
    )

    result = MaterialGenerationService().generate(material.pk)

    assert result is True
    material.refresh_from_db()
    assert material.generation_status == GenerationStatus.COMPLETED
    assert material.output_json["article"]["headline"] == "Short headline"
    assert GenerationSource.objects.filter(material=material).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_service.py -v`
Expected: FAIL — `GenerationModel` not importable from `service`, or retrieval returns no chunks. (This test also depends on real retrieval via pgvector `CosineDistance`; the seeded chunks give it real rows to find.)

- [ ] **Step 3: Rewrite `service.py`**

Replace the imports of `GenerationClient`/`OutputRepairService` and the `_run_pipeline`/`_stamp`/`_validate` methods. New `__init__` and `_run_pipeline`:

```python
from collateral_ai.documents.processing.embeddings import EmbeddingService
from collateral_ai.materials.generation.graph import build_generation_graph
from collateral_ai.materials.generation.model import GenerationModel
from collateral_ai.materials.generation.retrieval import RetrievalService
from collateral_ai.materials.generation.validation import OutputValidator
```

```python
    def __init__(
        self,
        *,
        embedder: EmbeddingService | None = None,
        retriever: RetrievalService | None = None,
        model: GenerationModel | None = None,
    ) -> None:
        self.embedder = embedder or EmbeddingService()
        self.retriever = retriever or RetrievalService()
        self.model = model or GenerationModel()
        self.validator = OutputValidator()
        self.default_top_k = int(settings.MATERIAL_RETRIEVAL_TOP_K)
        self.max_repair_attempts = int(settings.MATERIAL_MAX_REPAIR_ATTEMPTS)
```

```python
    def _run_pipeline(self, material: MarketingMaterial, *, top_k: int) -> None:
        graph = build_generation_graph(
            embedder=self.embedder,
            retriever=self.retriever,
            model=self.model,
            validator=self.validator,
            max_repair_attempts=self.max_repair_attempts,
        )
        final = graph.invoke(
            {
                "material_id": material.pk,
                "material": material,
                "template": material.template,
                "top_k": top_k,
                "attempts": 0,
            },
        )
        output = final["output"]
        context_snapshot = final["context_snapshot"]
        source_map = final["source_map"]
        if not final["is_valid"]:
            MarketingMaterial.objects.filter(pk=material.pk).update(
                output_json=output,
                validation_result={
                    "is_valid": False,
                    "errors": final["validation_errors"],
                },
                retrieved_context=context_snapshot,
                updated_at=timezone.now(),
            )
            msg = f"Generated output failed validation: {final['validation_errors']}"
            raise ValueError(msg)

        result = self.validator.validate(
            output=output,
            constraints=material.template.constraints,
            image_slots=material.template.image_slots,
            allowed_source_ids=final["allowed_ids"],
        )
        self._save_completed(material, output, result, context_snapshot, source_map)
```

Keep `_claim` and `_save_completed` exactly as they are. Remove the now-unused `logger.warning` repair-loop code, `_stamp`, and `_validate`.

- [ ] **Step 4: Delete the dead modules**

```bash
git rm backend/collateral_ai/materials/generation/llm.py \
  backend/collateral_ai/materials/generation/repair.py
```

- [ ] **Step 5: Run the full generation test suite**

Run: `just pytest collateral_ai/materials/tests/ -v`
Expected: PASS — new service test passes; existing `test_material_views.py` still green.

- [ ] **Step 6: Grep for dangling references**

Run: `just pytest collateral_ai -q` and `grep -rn "generation.llm\|OutputRepairService\|GenerationClient" backend/collateral_ai`
Expected: no import errors; grep returns nothing.

- [ ] **Step 7: Commit**

```bash
git add -A backend/collateral_ai/materials/
git commit -m "feat(materials): wire service to LangGraph, remove llm.py/repair.py"
```

---

### Task 6: Eval evaluators (`eval/evaluators.py`)

**Files:**
- Create: `backend/collateral_ai/materials/generation/eval/__init__.py`
- Create: `backend/collateral_ai/materials/generation/eval/evaluators.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_evaluators.py` (create)

**Interfaces:**
- Produces:
  - `schema_valid(output: dict, template) -> bool`
  - `sources_grounded(output: dict, allowed_ids: set[str]) -> bool`
  - `counts_match(output: dict, template) -> bool`
  - `groundedness_judge(output: dict, context: dict, *, judge=None) -> float` — 0..1; `judge` is an injectable callable `(prompt: str) -> str` returning a numeric string; defaults to a Gemini judge built from `MATERIAL_EVAL_JUDGE_MODEL`.

- [ ] **Step 1: Write the failing test**

Create `backend/collateral_ai/materials/tests/generation/test_evaluators.py`:

```python
from collateral_ai.materials.generation.eval import evaluators


def _template():
    class T:
        constraints = {"body_section_count": 1}
        image_slots = []
    return T()


def _output():
    return {
        "article": {"headline": "h", "subheadline": "s",
                    "body_sections": [{"title": "t", "text": "x"}], "cta": "c"},
        "image_slots": [],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


def test_sources_grounded_true_when_all_allowed():
    assert evaluators.sources_grounded(_output(), {"SENDER_SOURCE_1"}) is True


def test_sources_grounded_false_when_hallucinated():
    assert evaluators.sources_grounded(_output(), {"OTHER"}) is False


def test_counts_match_true():
    assert evaluators.counts_match(_output(), _template()) is True


def test_groundedness_judge_parses_injected_score():
    score = evaluators.groundedness_judge(
        _output(), {"sender_context": [], "receiver_context": []},
        judge=lambda prompt: "0.75",
    )
    assert score == 0.75
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_evaluators.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

Create `backend/collateral_ai/materials/generation/eval/__init__.py` (empty), then `backend/collateral_ai/materials/generation/eval/evaluators.py`:

```python
"""Offline evaluators for material generation experiments.

Deterministic checks plus an LLM-as-judge groundedness score. Never run in the
live request path.
"""

from __future__ import annotations

import json

from django.conf import settings

from collateral_ai.materials.generation.validation import OutputValidator


def schema_valid(output: dict, template) -> bool:
    result = OutputValidator().validate(
        output=output,
        constraints=template.constraints,
        image_slots=template.image_slots,
        allowed_source_ids={
            ref.get("source_id") for ref in output.get("source_references", [])
        },
    )
    return result.is_valid


def sources_grounded(output: dict, allowed_ids: set[str]) -> bool:
    refs = output.get("source_references", [])
    if not refs:
        return False
    return all(ref.get("source_id") in allowed_ids for ref in refs)


def counts_match(output: dict, template) -> bool:
    expected = template.constraints["body_section_count"]
    sections = output.get("article", {}).get("body_sections", [])
    slots_ok = len(output.get("image_slots", [])) == len(template.image_slots)
    return len(sections) == expected and slots_ok


_JUDGE_PROMPT = """You grade groundedness of marketing copy against source context.
Return ONLY a number between 0 and 1 (1 = every used_fact is supported by the
cited context; 0 = fabricated). Output JSON: {{"score": <number>}}.

source_references: {refs}
sender_context: {sender}
receiver_context: {receiver}
"""


def _default_judge(prompt: str) -> str:
    from langchain_google_vertexai import ChatVertexAI  # noqa: PLC0415
    from langchain_core.messages import HumanMessage  # noqa: PLC0415

    chat = ChatVertexAI(
        model=settings.MATERIAL_EVAL_JUDGE_MODEL,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.VERTEX_LOCATION,
        temperature=0.0,
    )
    return chat.invoke([HumanMessage(content=prompt)]).content


def groundedness_judge(output: dict, context: dict, *, judge=None) -> float:
    judge = judge or _default_judge
    prompt = _JUDGE_PROMPT.format(
        refs=json.dumps(output.get("source_references", [])),
        sender=json.dumps(context.get("sender_context", [])),
        receiver=json.dumps(context.get("receiver_context", [])),
    )
    raw = judge(prompt).strip()
    try:
        return float(json.loads(raw)["score"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return float(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest collateral_ai/materials/tests/generation/test_evaluators.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/collateral_ai/materials/generation/eval/ \
  backend/collateral_ai/materials/tests/generation/test_evaluators.py
git commit -m "feat(materials): offline eval evaluators (deterministic + judge)"
```

---

### Task 7: Seed data + `seed_eval_dataset` command

**Files:**
- Create: `backend/collateral_ai/materials/generation/eval/seed.py`
- Create: `backend/collateral_ai/materials/generation/eval/datasets.py`
- Create: `backend/collateral_ai/materials/management/commands/seed_eval_dataset.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_seed.py` (create)

**Interfaces:**
- Consumes: factories (`MarketingMaterialFactory`, `TemplateFactory`, `DocumentChunkFactory`), models.
- Produces:
  - `seed.build_golden_materials() -> list[int]` — creates ~7 `MarketingMaterial` rows (varied templates + one sparse-context adversarial case) with sender/receiver `DocumentChunk`s, returns their ids. Idempotent-ish: safe to call in a test DB.
  - `datasets.push_examples(name: str, example_inputs: list[dict]) -> str` — creates/updates a LangSmith dataset, returns dataset id. Uses `langsmith.Client`.
  - management command `seed_eval_dataset --name material-gen-golden`.

- [ ] **Step 1: Write the failing test**

Create `backend/collateral_ai/materials/tests/generation/test_seed.py`:

```python
import pytest

from collateral_ai.materials.generation.eval import seed
from collateral_ai.materials.models import MarketingMaterial
from collateral_ai.documents.models import DocumentChunk


@pytest.mark.django_db
def test_build_golden_materials_creates_varied_examples():
    ids = seed.build_golden_materials()
    assert len(ids) >= 6
    materials = MarketingMaterial.objects.filter(pk__in=ids)
    assert materials.count() == len(ids)
    # every material's companies have at least one chunk (except the adversarial one)
    for material in materials:
        sender_chunks = DocumentChunk.objects.filter(company=material.sender_company)
        assert sender_chunks.exists() or "sparse" in material.title.lower()
    # at least two distinct templates for coverage
    template_ids = {m.template_id for m in materials}
    assert len(template_ids) >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_seed.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `seed.py`**

Create `backend/collateral_ai/materials/generation/eval/seed.py`:

```python
"""Self-generated golden examples for the material-gen eval dataset.

Builds varied templates (different section counts / image slots) plus an
adversarial sparse-context case. Uses the same factories the tests use.
"""

from __future__ import annotations

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.materials.tests.factories import TemplateFactory

_SENDER_FACTS = [
    "Acme ships a real-time fraud API with 40ms p99 latency.",
    "Acme's SOC2 Type II covers all data-plane services.",
    "Acme integrates with Stripe, Adyen, and Braintree out of the box.",
]
_RECEIVER_FACTS = [
    "Globex processes 2M card transactions per day across EMEA.",
    "Globex's current fraud tool has a 4% false-positive rate.",
    "Globex is expanding into APAC in the next fiscal year.",
]


def _template_two_sections():
    return TemplateFactory(name="Newsletter two sections")


def _template_three_sections_no_slots():
    return TemplateFactory(
        name="Longform three sections",
        constraints={
            "headline_max_words": 12, "subheadline_max_words": 24,
            "body_section_count": 3, "body_section_max_words": 90, "cta_max_words": 12,
        },
        image_slots=[],
    )


def _seed_chunks(company, facts):
    for i, fact in enumerate(facts, start=1):
        DocumentChunkFactory(company=company, content=fact, page_number=i)


def build_golden_materials() -> list[int]:
    ids: list[int] = []
    templates = [_template_two_sections(), _template_three_sections_no_slots()]

    for idx in range(6):
        template = templates[idx % len(templates)]
        sender = CompanyFactory(name=f"Acme {idx}")
        receiver = CompanyFactory(name=f"Globex {idx}")
        _seed_chunks(sender, _SENDER_FACTS)
        _seed_chunks(receiver, _RECEIVER_FACTS)
        material = MarketingMaterialFactory(
            title=f"Golden {idx}",
            sender_company=sender,
            receiver_company=receiver,
            template=template,
            prompt="Introduce our fraud API to the receiver's pain points.",
        )
        ids.append(material.pk)

    # Adversarial: sparse context (receiver has no chunks) to test grounding.
    sender = CompanyFactory(name="Acme sparse")
    receiver = CompanyFactory(name="Globex sparse")
    _seed_chunks(sender, _SENDER_FACTS[:1])
    material = MarketingMaterialFactory(
        title="Golden sparse adversarial",
        sender_company=sender,
        receiver_company=receiver,
        template=templates[0],
        prompt="Pitch with minimal context.",
    )
    ids.append(material.pk)
    return ids
```

- [ ] **Step 4: Write `datasets.py`**

Create `backend/collateral_ai/materials/generation/eval/datasets.py`:

```python
"""LangSmith dataset helpers for material-gen eval."""

from __future__ import annotations


def push_examples(name: str, example_inputs: list[dict]) -> str:
    from langsmith import Client  # noqa: PLC0415

    client = Client()
    if client.has_dataset(dataset_name=name):
        dataset = client.read_dataset(dataset_name=name)
    else:
        dataset = client.create_dataset(dataset_name=name)
    for example in example_inputs:
        client.create_example(inputs=example, dataset_id=dataset.id)
    return str(dataset.id)
```

- [ ] **Step 5: Write the management command**

Create `backend/collateral_ai/materials/management/commands/seed_eval_dataset.py`:

```python
from django.core.management.base import BaseCommand

from collateral_ai.materials.generation.eval import datasets
from collateral_ai.materials.generation.eval import seed


class Command(BaseCommand):
    help = "Seed golden materials and push their ids to a LangSmith dataset."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="material-gen-golden")

    def handle(self, *args, **options):
        ids = seed.build_golden_materials()
        self.stdout.write(f"Created {len(ids)} golden materials: {ids}")
        dataset_id = datasets.push_examples(
            options["name"],
            [{"material_id": mid} for mid in ids],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Pushed to LangSmith dataset {dataset_id}"),
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `just pytest collateral_ai/materials/tests/generation/test_seed.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/collateral_ai/materials/generation/eval/seed.py \
  backend/collateral_ai/materials/generation/eval/datasets.py \
  backend/collateral_ai/materials/management/commands/seed_eval_dataset.py \
  backend/collateral_ai/materials/tests/generation/test_seed.py
git commit -m "feat(materials): golden seed data + seed_eval_dataset command"
```

---

### Task 8: `run_eval` command + full verification gate

**Files:**
- Create: `backend/collateral_ai/materials/management/commands/run_eval.py`
- Test: `backend/collateral_ai/materials/tests/generation/test_run_eval.py` (create)

**Interfaces:**
- Consumes: `MaterialGenerationService` (to run the graph per example), evaluators (Task 6), `datasets` (Task 7).
- Produces: management command `run_eval --name material-gen-golden --label <str>` that runs the graph over each dataset example and evaluates it. `--label` defaults to the git short-SHA.

- [ ] **Step 1: Write the failing test (target function, model faked)**

Create `backend/collateral_ai/materials/tests/generation/test_run_eval.py`:

```python
from unittest.mock import MagicMock

import pytest

from collateral_ai.materials.management.commands import run_eval
from collateral_ai.materials.tests.factories import MarketingMaterialFactory
from collateral_ai.documents.tests.factories import DocumentChunkFactory
from collateral_ai.materials.statuses import GenerationStatus


def _valid_output():
    return {
        "article": {"headline": "Short", "subheadline": "Sub",
                    "body_sections": [{"title": "T", "text": "b"},
                                      {"title": "T2", "text": "b2"}], "cta": "Act"},
        "image_slots": [
            {"slot_id": "hero_image", "description": "d", "source": "generated_placeholder"},
            {"slot_id": "sender_logo", "description": "d", "source": "sender"}],
        "source_references": [{"source_id": "SENDER_SOURCE_1", "used_fact": "f"}],
    }


@pytest.mark.django_db
def test_evaluate_one_returns_scored_record(monkeypatch):
    material = MarketingMaterialFactory(generation_status=GenerationStatus.QUEUED)
    DocumentChunkFactory(company=material.sender_company)
    DocumentChunkFactory(company=material.receiver_company)

    fake_model = MagicMock()
    fake_model.generate_structured.return_value = _valid_output()
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.GenerationModel",
        lambda: fake_model)
    monkeypatch.setattr(
        "collateral_ai.materials.generation.service.EmbeddingService",
        lambda: _fake_embedder())

    record = run_eval.evaluate_one(material.pk, judge=lambda prompt: "0.9")

    assert record["schema_valid"] is True
    assert record["sources_grounded"] is True
    assert record["groundedness"] == 0.9


def _fake_embedder():
    e = MagicMock()
    e.embed_query.return_value = [0.0] * 768
    return e
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just pytest collateral_ai/materials/tests/generation/test_run_eval.py -v`
Expected: FAIL — `evaluate_one` not defined.

- [ ] **Step 3: Write the command**

Create `backend/collateral_ai/materials/management/commands/run_eval.py`:

```python
"""Offline eval runner: run the generation graph over the golden dataset and grade.

Not part of the live path. Uploads a named experiment to LangSmith when tracing
is configured; always prints local aggregate scores.
"""

from __future__ import annotations

import subprocess

from django.core.management.base import BaseCommand

from collateral_ai.materials.generation.eval import evaluators
from collateral_ai.materials.generation.service import MaterialGenerationService
from collateral_ai.materials.models import MarketingMaterial


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True,  # noqa: S607
        ).strip()
    except (subprocess.SubprocessError, OSError):
        return "local"


def evaluate_one(material_id: int, *, judge=None) -> dict:
    MaterialGenerationService().generate(material_id, force=True)
    material = MarketingMaterial.objects.select_related("template").get(pk=material_id)
    output = material.output_json or {}
    context = material.retrieved_context or {}
    allowed_ids = {
        item["source_id"]
        for key in ("sender_context", "receiver_context")
        for item in context.get(key, [])
    }
    return {
        "material_id": material_id,
        "schema_valid": evaluators.schema_valid(output, material.template),
        "sources_grounded": evaluators.sources_grounded(output, allowed_ids),
        "counts_match": evaluators.counts_match(output, material.template),
        "groundedness": evaluators.groundedness_judge(output, context, judge=judge),
    }


class Command(BaseCommand):
    help = "Run the generation graph over the golden dataset and grade outputs."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="material-gen-golden")
        parser.add_argument("--label", default="")

    def handle(self, *args, **options):
        from langsmith import Client  # noqa: PLC0415

        label = options["label"] or _git_sha()
        client = Client()
        dataset = client.read_dataset(dataset_name=options["name"])
        records = []
        for example in client.list_examples(dataset_id=dataset.id):
            material_id = example.inputs["material_id"]
            records.append(evaluate_one(material_id))
        n = len(records) or 1
        self.stdout.write(f"Experiment: {label}  (n={len(records)})")
        for key in ("schema_valid", "sources_grounded", "counts_match"):
            passed = sum(1 for r in records if r[key])
            self.stdout.write(f"  {key}: {passed}/{len(records)}")
        avg_ground = sum(r["groundedness"] for r in records) / n
        self.stdout.write(self.style.SUCCESS(f"  groundedness avg: {avg_ground:.3f}"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just pytest collateral_ai/materials/tests/generation/test_run_eval.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + lint gate**

Run: `just pytest collateral_ai -q`
Expected: PASS — all generation tests + existing `test_material_views.py`.

Run lint: `cd backend && pre-commit run --all-files` (or the project's ruff command).
Expected: no PLC0415/SLF001 violations in new files.

- [ ] **Step 6: Real end-to-end verification (must-not-break gate)**

With real Vertex credentials + `LANGSMITH_TRACING=true` in `.env`, run against a seeded material:

```bash
just pytest collateral_ai/materials/tests/generation/test_seed.py  # confirm seed works
# In a shell with the DB + ADC available:
python manage.py seed_eval_dataset --name material-gen-golden
python manage.py run_eval --label baseline
```

Expected:
- `run_eval` prints aggregate scores (schema_valid N/N, groundedness avg printed).
- A trace appears in the LangSmith project `collateral-material-gen`.
- Pick one golden `material_id` and confirm in the DB it is `COMPLETED` with `GenerationSource` rows.

If `with_structured_output` errored on the schema dialect, apply the Task 2 Step 5 converter and re-run.

- [ ] **Step 7: Commit**

```bash
git add backend/collateral_ai/materials/management/commands/run_eval.py \
  backend/collateral_ai/materials/tests/generation/test_run_eval.py
git commit -m "feat(materials): run_eval command + offline grading, verification gate"
```

---

## Self-Review

**Spec coverage:**
- §3 graph / repair cycle → Task 4. §4 state → Task 4. §5 nodes → Task 4/5. §6 model layer → Task 2. §7 enum hardening → Task 3. §8 tracing (env + `_FORWARDED_ENV`) → Task 1. §9 eval (seed/evaluators/run) → Tasks 6/7/8. §10 file layout → Tasks 2–8. §11 migration + verification gate → Task 5 (delete) + Task 8 Step 6. §12 deps/config → Task 1. All covered.

**Placeholder scan:** No TBD/TODO. The one implementation-discovery point (schema dialect) is a concrete conditional step with the actual converter code (Task 2 Step 5), not a placeholder.

**Type consistency:** `GenerationModel.generate_structured(system_instruction, user_input, response_schema) -> dict` used identically in Tasks 2, 4, 5. `build_response_schema(..., allowed_source_ids=...)` defined in Task 3, called in Task 4. `build_generation_graph(embedder, retriever, model, validator, max_repair_attempts)` defined Task 4, called Task 5. `evaluate_one(material_id, *, judge=None)` defined Task 8, tested Task 8. Consistent.

**Known constraint:** Tasks 5 and 8 service tests exercise real pgvector retrieval, so they seed real `DocumentChunk`s (embedding = `[0.0]*768` from the factory) rather than mocking `RetrievalService` — this keeps the DB contract honest.

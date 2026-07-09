"""Corrective LLM call: invalid JSON + validation errors → fixed JSON.

Spec §6.3 step 5.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from collateral_ai.materials.generation.prompts import REPAIR_SYSTEM_INSTRUCTION
from collateral_ai.materials.generation.prompts import build_repair_payload

if TYPE_CHECKING:
    from collateral_ai.materials.generation.llm import GenerationClient


class OutputRepairService:
    def __init__(self, client: GenerationClient) -> None:
        self.client = client

    def repair(  # noqa: PLR0913
        self,
        *,
        output: dict,
        errors: list[dict],
        constraints: dict,
        image_slots: list[dict],
        allowed_source_ids: list[str],
        response_schema: dict,
    ) -> dict:
        return self.client.generate_json(
            system_instruction=REPAIR_SYSTEM_INSTRUCTION,
            user_input=build_repair_payload(
                output=output,
                errors=errors,
                constraints=constraints,
                image_slots=image_slots,
                allowed_source_ids=allowed_source_ids,
            ),
            response_schema=response_schema,
        )

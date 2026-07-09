"""Deterministic validation of generated output against template constraints.

Error categories map one-to-one onto the detail page's Quality checks
(spec §6.4): structure, word_limit, image_slot, source. There is no theme
category — theme is server-stamped, never validated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

STRUCTURE = "structure"
WORD_LIMIT = "word_limit"
IMAGE_SLOT = "image_slot"
SOURCE = "source"


def _word_count(value: str) -> int:
    return len(value.split()) if value else 0


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"is_valid": self.is_valid, "errors": self.errors}


class OutputValidator:
    def validate(
        self,
        *,
        output: dict,
        constraints: dict,
        image_slots: list[dict],
        allowed_source_ids: set[str],
    ) -> ValidationResult:
        errors: list[dict[str, str]] = []
        self._check_structure(output, errors)
        if not errors:
            self._check_word_limits(output, constraints, errors)
            self._check_image_slots(output, image_slots, errors)
            self._check_sources(output, allowed_source_ids, errors)
        return ValidationResult(is_valid=not errors, errors=errors)

    def _add(self, errors: list, category: str, message: str) -> None:
        errors.append({"category": category, "message": message})

    def _check_structure(self, output: dict, errors: list) -> None:
        if not isinstance(output, dict):
            self._add(errors, STRUCTURE, "Output must be a JSON object.")
            return
        article = output.get("article")
        if not isinstance(article, dict):
            self._add(errors, STRUCTURE, "article must be an object.")
            return
        for key in ("headline", "subheadline", "cta"):
            value = article.get(key)
            if not isinstance(value, str) or not value.strip():
                self._add(
                    errors,
                    STRUCTURE,
                    f"article.{key} must be a non-empty string.",
                )
        sections = article.get("body_sections")
        if not isinstance(sections, list):
            self._add(errors, STRUCTURE, "article.body_sections must be a list.")
        else:
            self._check_body_sections(sections, errors)
        if not isinstance(output.get("image_slots"), list):
            self._add(errors, STRUCTURE, "image_slots must be a list.")
        if not isinstance(output.get("source_references"), list):
            self._add(errors, STRUCTURE, "source_references must be a list.")

    def _check_body_sections(self, sections: list, errors: list) -> None:
        for i, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                self._add(
                    errors,
                    STRUCTURE,
                    f"body_sections[{i}] must be an object.",
                )
                continue
            for field_name in ("title", "text"):
                value = section.get(field_name)
                if not isinstance(value, str) or not value.strip():
                    self._add(
                        errors,
                        STRUCTURE,
                        f"body_sections[{i}].{field_name} must be a non-empty string.",
                    )

    def _check_word_limits(self, output: dict, constraints: dict, errors: list) -> None:
        article = output["article"]
        limits = [
            (
                "article.headline",
                article["headline"],
                constraints["headline_max_words"],
            ),
            (
                "article.subheadline",
                article["subheadline"],
                constraints["subheadline_max_words"],
            ),
            ("article.cta", article["cta"], constraints["cta_max_words"]),
        ]
        for name, value, max_words in limits:
            count = _word_count(value)
            if count > max_words:
                self._add(
                    errors,
                    WORD_LIMIT,
                    f"{name} has {count} words, max {max_words}.",
                )
        sections = article["body_sections"]
        expected = constraints["body_section_count"]
        if len(sections) != expected:
            self._add(
                errors,
                WORD_LIMIT,
                f"Expected {expected} body sections, got {len(sections)}.",
            )
        for i, section in enumerate(sections, start=1):
            count = _word_count(section.get("text", ""))
            if count > constraints["body_section_max_words"]:
                self._add(
                    errors,
                    WORD_LIMIT,
                    f"body_sections[{i}].text has {count} words, "
                    f"max {constraints['body_section_max_words']}.",
                )

    def _check_image_slots(self, output: dict, image_slots: list, errors: list) -> None:
        expected = {slot["slot_id"]: slot["source"] for slot in image_slots}
        returned: dict[Any, Any] = {}
        seen_slot_ids: set[Any] = set()
        for i, slot in enumerate(output["image_slots"], start=1):
            if not isinstance(slot, dict):
                self._add(errors, IMAGE_SLOT, f"image_slots[{i}] must be an object.")
                continue
            slot_id = slot.get("slot_id")
            if slot_id in seen_slot_ids:
                self._add(errors, IMAGE_SLOT, f"Duplicate image slot: {slot_id}.")
            seen_slot_ids.add(slot_id)
            returned[slot_id] = slot.get("source")
        for slot_id, source in expected.items():
            if slot_id not in returned:
                self._add(
                    errors,
                    IMAGE_SLOT,
                    f"Missing required image slot: {slot_id}.",
                )
            elif returned[slot_id] != source:
                self._add(
                    errors,
                    IMAGE_SLOT,
                    (
                        f"Slot {slot_id} source must be {source!r}, "
                        f"got {returned[slot_id]!r}."
                    ),
                )
        for slot_id in returned:
            if slot_id not in expected:
                self._add(errors, IMAGE_SLOT, f"Unknown image slot: {slot_id}.")

    def _check_sources(self, output: dict, allowed: set[str], errors: list) -> None:
        references = output["source_references"]
        if not references:
            self._add(errors, SOURCE, "At least one source reference is required.")
            return
        for i, ref in enumerate(references, start=1):
            if not isinstance(ref, dict) or not ref.get("source_id"):
                self._add(errors, SOURCE, f"source_references[{i}] needs a source_id.")
                continue
            if ref["source_id"] not in allowed:
                self._add(
                    errors,
                    SOURCE,
                    f"source_references[{i}].source_id is unknown: {ref['source_id']}.",
                )
            if not ref.get("used_fact"):
                self._add(
                    errors,
                    SOURCE,
                    f"source_references[{i}].used_fact is required.",
                )

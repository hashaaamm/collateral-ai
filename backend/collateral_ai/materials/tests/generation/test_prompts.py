from collateral_ai.materials.generation.prompts import REPAIR_SYSTEM_INSTRUCTION


def test_repair_instruction_covers_image_slot_removal():
    assert "image_slots" in REPAIR_SYSTEM_INSTRUCTION
    assert "Unknown image slot" in REPAIR_SYSTEM_INSTRUCTION
    assert "Remove" in REPAIR_SYSTEM_INSTRUCTION


def test_repair_instruction_covers_empty_image_slots_case():
    assert "empty" in REPAIR_SYSTEM_INSTRUCTION
    assert "[]" in REPAIR_SYSTEM_INSTRUCTION

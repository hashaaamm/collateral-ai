from collateral_ai.materials.generation.eval import evaluators


def _template():
    class T:
        constraints = {"body_section_count": 1}
        image_slots = []

    return T()


def _output():
    return {
        "article": {
            "headline": "h",
            "subheadline": "s",
            "body_sections": [{"title": "t", "text": "x"}],
            "cta": "c",
        },
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
        _output(),
        {"sender_context": [], "receiver_context": []},
        judge=lambda prompt: "0.75",
    )
    assert score == 0.75

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


def test_no_inline_citations_true_when_clean():
    assert evaluators.no_inline_citations(_output()) is True


def test_no_inline_citations_false_when_token_present():
    output = _output()
    output["article"]["body_sections"][0]["text"] = "x (SENDER_SOURCE_1)"
    assert evaluators.no_inline_citations(output) is False


def test_groundedness_judge_parses_injected_score():
    score = evaluators.groundedness_judge(
        _output(),
        {"sender_context": [], "receiver_context": []},
        judge=lambda prompt: "0.75",
    )
    assert score == 0.75


def test_specificity_judge_parses_injected_score():
    score = evaluators.specificity_judge(_output(), judge=lambda p: "0.6")
    assert score == 0.6


def test_fact_fidelity_passes_facts_and_article_to_judge():
    prompts = []

    def judge(prompt):
        prompts.append(prompt)
        return '{"score": 0.67}'

    score = evaluators.fact_fidelity(
        _output(),
        ["sub-second requires the Enterprise tier"],
        judge=judge,
    )
    assert score == 0.67
    assert "sub-second requires the Enterprise tier" in prompts[0]
    assert "headline" in prompts[0]


def test_fact_fidelity_without_facts_returns_one_without_judge_call():
    def judge(prompt):
        msg = "judge must not be called"
        raise AssertionError(msg)

    assert evaluators.fact_fidelity(_output(), [], judge=judge) == 1.0


def test_parse_score_fenced_json():
    raw = '```json\n{"score": 0.7}\n```'
    assert evaluators._parse_score(raw) == 0.7  # noqa: SLF001


def test_parse_score_bare_number():
    assert evaluators._parse_score("0.4") == 0.4  # noqa: SLF001


def test_parse_score_number_in_prose():
    assert evaluators._parse_score("Score: 0.9 out of 1") == 0.9  # noqa: SLF001


def test_parse_score_garbage_returns_zero():
    assert evaluators._parse_score("n/a") == 0.0  # noqa: SLF001


def test_parse_score_clamps_out_of_range():
    assert evaluators._parse_score("1.5") == 1.0  # noqa: SLF001


def test_default_judge_retries_on_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr(evaluators.time, "sleep", lambda _seconds: None)

    calls = {"n": 0}

    class _FakeResponse:
        text = "0.5"

    class _FakeModels:
        def generate_content(self, **_kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                msg = "429 ResourceExhausted"
                raise RuntimeError(msg)
            return _FakeResponse()

    class _FakeClient:
        models = _FakeModels()

    monkeypatch.setattr(evaluators, "_judge_client", _FakeClient)

    result = evaluators._default_judge("prompt")  # noqa: SLF001

    assert result == "0.5"
    assert calls["n"] == 3


def test_default_judge_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(evaluators.time, "sleep", lambda _seconds: None)

    class _FakeModels:
        def generate_content(self, **_kwargs):
            msg = "429 rate limited"
            raise RuntimeError(msg)

    class _FakeClient:
        models = _FakeModels()

    monkeypatch.setattr(evaluators, "_judge_client", _FakeClient)

    result = evaluators._default_judge("prompt")  # noqa: SLF001

    assert result == ""


def test_default_judge_succeeds_without_retry(monkeypatch):
    sleep_calls = {"n": 0}
    monkeypatch.setattr(
        evaluators.time,
        "sleep",
        lambda _seconds: sleep_calls.__setitem__("n", sleep_calls["n"] + 1),
    )

    calls = {"n": 0}

    class _FakeResponse:
        text = "0.9"

    class _FakeModels:
        def generate_content(self, **_kwargs):
            calls["n"] += 1
            return _FakeResponse()

    class _FakeClient:
        models = _FakeModels()

    monkeypatch.setattr(evaluators, "_judge_client", _FakeClient)

    result = evaluators._default_judge("prompt")  # noqa: SLF001

    assert result == "0.9"
    assert calls["n"] == 1
    assert sleep_calls["n"] == 0

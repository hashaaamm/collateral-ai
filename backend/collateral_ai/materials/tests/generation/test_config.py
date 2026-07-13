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
    import langchain_google_vertexai  # noqa: F401, PLC0415
    import langgraph.graph  # noqa: F401, PLC0415


def test_material_max_repair_attempts_default():
    assert settings.MATERIAL_MAX_REPAIR_ATTEMPTS == 3

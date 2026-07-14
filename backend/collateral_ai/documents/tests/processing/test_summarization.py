from __future__ import annotations

from unittest import mock

from collateral_ai.documents.processing.summarization import DocumentSummaryService


def _client_returning(text):
    client = mock.MagicMock()
    client.models.generate_content.return_value = mock.MagicMock(text=text)
    return client


def test_summarize_returns_stripped_text():
    with mock.patch.object(
        DocumentSummaryService,
        "_client",
        return_value=_client_returning("  A summary.  "),
    ):
        result = DocumentSummaryService().summarize(["chunk one", "chunk two"])
        assert result == "A summary."


def test_summarize_empty_input_skips_llm_call():
    with mock.patch.object(DocumentSummaryService, "_client") as client:
        assert DocumentSummaryService().summarize(["", "   "]) == ""
    client.assert_not_called()


def test_summarize_clips_input_to_max_words(settings):
    settings.DOCUMENT_SUMMARY_INPUT_MAX_WORDS = 3
    client = _client_returning("s")
    with mock.patch.object(DocumentSummaryService, "_client", return_value=client):
        DocumentSummaryService().summarize(["w0 w1", "w2 w3 w4"])
    assert client.models.generate_content.call_args.kwargs["contents"] == "w0 w1 w2"


def test_summarize_empty_response_returns_empty():
    with mock.patch.object(
        DocumentSummaryService,
        "_client",
        return_value=_client_returning(None),
    ):
        assert DocumentSummaryService().summarize(["text"]) == ""

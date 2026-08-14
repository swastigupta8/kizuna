from unittest.mock import MagicMock, patch

from models import Finding, Severity
from remediate import generate_remediations


def _finding(node_id: str = "api", message: str = "no circuit breaker") -> Finding:
    return Finding(severity=Severity.HIGH, node_id=node_id, message=message)


def _mock_response(remediations: list[dict]) -> MagicMock:
    function_call = MagicMock()
    function_call.args = {"remediations": remediations}

    part = MagicMock()
    part.function_call = function_call

    response = MagicMock()
    response.candidates[0].content.parts = [part]
    return response


def test_no_findings_means_no_api_call_at_all():
    with patch("remediate.genai.Client") as mock_client_cls:
        result = generate_remediations([])
    assert result == {}
    mock_client_cls.assert_not_called()


def test_missing_api_key_returns_empty_mapping(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = generate_remediations([_finding()])
    assert result == {}


@patch("remediate.genai.Client")
def test_parses_a_successful_function_call_response(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    mock_client_cls.return_value.models.generate_content.return_value = _mock_response(
        [{"index": 0, "suggestion": "Wrap the call in a circuit breaker."}]
    )

    result = generate_remediations([_finding()])
    assert result == {0: "Wrap the call in a circuit breaker."}


@patch("remediate.genai.Client")
def test_out_of_range_indices_are_dropped(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    mock_client_cls.return_value.models.generate_content.return_value = _mock_response(
        [
            {"index": 0, "suggestion": "valid"},
            {"index": 7, "suggestion": "should be dropped — no finding at index 7"},
        ]
    )

    result = generate_remediations([_finding()])
    assert result == {0: "valid"}


@patch("remediate.genai.Client")
def test_any_api_failure_falls_back_to_an_empty_mapping_not_an_exception(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_client_cls.return_value.models.generate_content.side_effect = RuntimeError("network error")

    result = generate_remediations([_finding()])
    assert result == {}

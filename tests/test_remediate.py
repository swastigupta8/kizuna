from unittest.mock import MagicMock, patch

from models import Finding, Severity
from remediate import generate_remediations


def _finding(node_id: str = "api", message: str = "no circuit breaker") -> Finding:
    return Finding(severity=Severity.HIGH, node_id=node_id, message=message)


def test_no_findings_means_no_api_call_at_all():
    with patch("remediate.anthropic.Anthropic") as mock_anthropic_cls:
        result = generate_remediations([])
    assert result == {}
    mock_anthropic_cls.assert_not_called()


def test_missing_api_key_returns_empty_mapping(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = generate_remediations([_finding()])
    assert result == {}


@patch("remediate.anthropic.Anthropic")
def test_parses_a_successful_tool_use_response(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"remediations": [{"index": 0, "suggestion": "Wrap the call in a circuit breaker."}]}

    mock_response = MagicMock()
    mock_response.content = [tool_block]
    mock_anthropic_cls.return_value.messages.create.return_value = mock_response

    result = generate_remediations([_finding()])
    assert result == {0: "Wrap the call in a circuit breaker."}


@patch("remediate.anthropic.Anthropic")
def test_out_of_range_indices_are_dropped(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {
        "remediations": [
            {"index": 0, "suggestion": "valid"},
            {"index": 7, "suggestion": "should be dropped — no finding at index 7"},
        ]
    }
    mock_response = MagicMock()
    mock_response.content = [tool_block]
    mock_anthropic_cls.return_value.messages.create.return_value = mock_response

    result = generate_remediations([_finding()])
    assert result == {0: "valid"}


@patch("remediate.anthropic.Anthropic")
def test_any_api_failure_falls_back_to_an_empty_mapping_not_an_exception(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mock_anthropic_cls.return_value.messages.create.side_effect = RuntimeError("network error")

    result = generate_remediations([_finding()])
    assert result == {}

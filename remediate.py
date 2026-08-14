import os

import anthropic

from models import Finding

_MODEL = "claude-sonnet-5"

_SYSTEM_PROMPT = (
    "You are a senior site reliability engineer reviewing a resilience-scoring "
    "report for a microservice architecture. For each finding, write one concise, "
    "concrete remediation suggestion (at most two sentences). Be specific about "
    "what to change — name the config flag or pattern — rather than giving generic "
    "advice. Do not restate the finding itself."
)

_REMEDIATION_TOOL = {
    "name": "submit_remediations",
    "description": "Submit exactly one remediation suggestion per finding, referenced by index.",
    "input_schema": {
        "type": "object",
        "properties": {
            "remediations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "description": "the finding's index, as given"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["index", "suggestion"],
                },
            }
        },
        "required": ["remediations"],
    },
}


def generate_remediations(findings: list[Finding]) -> dict[int, str]:
    """
    Maps each finding's index to a natural-language remediation suggestion.

    This is deliberately isolated from score.py: the resilience score itself
    must stay deterministic and reproducible, since a CI gate has to give the
    same architecture the same score every time. The LLM only ever touches
    this human-readable explanation layer — and if it's unavailable or fails,
    callers get back an empty mapping, never an exception. A missing
    explanation should never be able to break the gate.
    """
    if not findings:
        return {}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {}

    findings_block = "\n".join(
        f"{i}. [{finding.severity.value}] {finding.node_id}: {finding.message}"
        for i, finding in enumerate(findings)
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=[_REMEDIATION_TOOL],
            tool_choice={"type": "tool", "name": "submit_remediations"},
            messages=[{"role": "user", "content": f"Findings:\n\n{findings_block}"}],
        )
        tool_use = next(block for block in response.content if block.type == "tool_use")
        remediations = tool_use.input["remediations"]
    except Exception:
        # network error, auth failure, rate limit, malformed response — the
        # score must still return successfully either way.
        return {}

    return {
        item["index"]: item["suggestion"]
        for item in remediations
        if 0 <= item["index"] < len(findings)
    }

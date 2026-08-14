import os

from google import genai
from google.genai import types

from models import Finding

_DEFAULT_MODEL = "gemini-3.5-flash"

_SYSTEM_PROMPT = (
    "You are a senior site reliability engineer reviewing a resilience-scoring "
    "report for a microservice architecture. For each finding, write one concise, "
    "concrete remediation suggestion (at most two sentences). Be specific about "
    "what to change — name the config flag or pattern — rather than giving generic "
    "advice. Do not restate the finding itself."
)

_REMEDIATION_FUNCTION = types.FunctionDeclaration(
    name="submit_remediations",
    description="Submit exactly one remediation suggestion per finding, referenced by index.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "remediations": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "index": {"type": "INTEGER", "description": "the finding's index, as given"},
                        "suggestion": {"type": "STRING"},
                    },
                    "required": ["index", "suggestion"],
                },
            }
        },
        "required": ["remediations"],
    },
)


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

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {}

    model = os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL)

    findings_block = "\n".join(
        f"{i}. [{finding.severity.value}] {finding.node_id}: {finding.message}"
        for i, finding in enumerate(findings)
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=f"Findings:\n\n{findings_block}",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                tools=[types.Tool(function_declarations=[_REMEDIATION_FUNCTION])],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY",
                        allowed_function_names=["submit_remediations"],
                    )
                ),
            ),
        )
        function_call = response.candidates[0].content.parts[0].function_call
        remediations = function_call.args["remediations"]
    except Exception:
        # network error, auth failure, rate limit, malformed response — the
        # score must still return successfully either way.
        return {}

    return {
        item["index"]: item["suggestion"]
        for item in remediations
        if 0 <= item["index"] < len(findings)
    }

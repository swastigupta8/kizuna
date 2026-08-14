"""One-off manual smoke test: calls the real Gemini API directly (no exception-swallowing)
so any real error is visible, then runs it through the normal generate_remediations() path.
"""

import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from models import Finding, Severity  # noqa: E402
from remediate import _REMEDIATION_FUNCTION, _SYSTEM_PROMPT, generate_remediations  # noqa: E402

findings = [
    Finding(severity=Severity.HIGH, node_id="booking-api", message="calls a downstream dependency with no circuit breaker"),
    Finding(severity=Severity.MEDIUM, node_id="payment-service", message="has no timeout configured on its outbound calls"),
]

print("--- raw call (exceptions NOT caught) ---")
try:
    api_key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    print(f"using model: {model}")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents="Findings:\n\n0. [high] booking-api: calls a downstream dependency with no circuit breaker",
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
    print("raw response object:", response)
except Exception:
    print("RAW CALL FAILED:")
    traceback.print_exc()

print("\n--- through generate_remediations() (normal path) ---")
result = generate_remediations(findings)
print(f"got {len(result)} remediation(s) back: {result}")

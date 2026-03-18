"""
Agent Brain — the AI-powered core of AutoFix.

Responsibilities:
  1. Receive a processed log snippet.
  2. Call the OpenAI API with a structured XML-style prompt for better
     accuracy (Software 3.0 approach).
  3. Parse the response to extract: root cause, proposed fix, and a
     confidence score.

The confidence score is simplified for practical use:
  - "High"   → the AI identified a clear, unambiguous error.
  - "Medium" → the error is present but the fix may need human review.
"""

import os
import json
import logging
import re
from typing import Optional

import openai

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"

# Structured XML-style prompt template — improves accuracy significantly
_SYSTEM_PROMPT = """\
You are an expert DevOps engineer and software debugger.
Your task is to analyse a CI/CD job failure log, identify the root cause,
propose a concrete code fix, and assign a confidence score.

Always respond in the following XML format and nothing else:

<analysis>
  <root_cause>Concise description of the root cause (1-3 sentences)</root_cause>
  <fix_description>What needs to be changed to fix the issue</fix_description>
  <code_fix>The exact code change (patch/snippet) that resolves the failure</code_fix>
  <confidence>High|Medium</confidence>
  <confidence_percentage>A number between 50 and 99</confidence_percentage>
  <affected_file>The file path most likely containing the bug (or "unknown")</affected_file>
</analysis>
"""

_USER_PROMPT_TEMPLATE = """\
<job_failure_log>
{log_snippet}
</job_failure_log>

Analyse the log above and provide your response in the specified XML format.
"""


def _parse_xml_response(response_text: str) -> dict:
    """Extract fields from the AI XML response.

    Args:
        response_text: Raw text returned by the AI model.

    Returns:
        Dictionary with keys: root_cause, fix_description, code_fix,
        confidence, confidence_percentage, affected_file.
    """

    def _tag(tag: str) -> Optional[str]:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", response_text, re.DOTALL)
        return match.group(1).strip() if match else None

    confidence = _tag("confidence") or "Medium"
    confidence = confidence if confidence in ("High", "Medium") else "Medium"

    try:
        confidence_pct = int(_tag("confidence_percentage") or "0")
        confidence_pct = max(50, min(99, confidence_pct))
    except ValueError:
        confidence_pct = 75 if confidence == "High" else 60

    return {
        "root_cause": _tag("root_cause") or "Unable to determine root cause.",
        "fix_description": _tag("fix_description") or "Manual review required.",
        "code_fix": _tag("code_fix") or "",
        "confidence": confidence,
        "confidence_percentage": confidence_pct,
        "affected_file": _tag("affected_file") or "unknown",
    }


def analyse_and_fix(log_snippet: str, model: Optional[str] = None) -> dict:
    """Analyse a CI/CD failure log and generate a fix using AI.

    Args:
        log_snippet: Processed log text (last 50-100 lines, cleaned).
        model: OpenAI model name to use. Defaults to ``gpt-4o-mini``.

    Returns:
        Dictionary with analysis results:
        - root_cause (str)
        - fix_description (str)
        - code_fix (str)
        - confidence ("High" | "Medium")
        - confidence_percentage (int, 50-99)
        - affected_file (str)

    Raises:
        openai.OpenAIError: When the API call fails.
        ValueError: When OPENAI_API_KEY is not configured.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please configure it in your .env file."
        )

    client = openai.OpenAI(api_key=api_key)
    chosen_model = model or os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)

    user_message = _USER_PROMPT_TEMPLATE.format(log_snippet=log_snippet)

    logger.info("Sending log snippet to AI model '%s' for analysis…", chosen_model)

    response = client.chat.completions.create(
        model=chosen_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,  # Low temperature → more deterministic, reliable fixes
        max_tokens=1024,
    )

    response_text = response.choices[0].message.content or ""
    logger.debug("AI raw response: %s", response_text)

    result = _parse_xml_response(response_text)
    logger.info(
        "Analysis complete — confidence: %s (%d%%)",
        result["confidence"],
        result["confidence_percentage"],
    )
    return result

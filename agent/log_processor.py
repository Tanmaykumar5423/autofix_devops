"""
Smart Log Processor — extracts the most relevant lines from CI/CD job logs.

Instead of sending the full log to the AI (which wastes tokens and reduces
accuracy), we:
  1. Strip ANSI escape codes and GitLab section markers.
  2. Return only the last ``tail_lines`` lines (default 50).

This improves speed ⚡, accuracy 🎯, and cost 💰.
"""

import re

# Match ANSI colour codes and GitLab CI section markers (e.g. \x1b[0K)
_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
# GitLab section start/end markers
_SECTION_MARKER = re.compile(r"section_(?:start|end):\d+:[^\r\n]*\r?")

DEFAULT_TAIL_LINES = 50
MAX_TAIL_LINES = 100


def clean_log(raw_log: str) -> str:
    """Remove ANSI codes and CI section markers from *raw_log*.

    Args:
        raw_log: Raw log text as returned by the GitLab Jobs API.

    Returns:
        Human-readable plain-text log.
    """
    text = _SECTION_MARKER.sub("", raw_log)
    text = _ANSI_ESCAPE.sub("", text)
    return text


def extract_tail(log_text: str, tail_lines: int = DEFAULT_TAIL_LINES) -> str:
    """Return the last *tail_lines* lines of *log_text*.

    Args:
        log_text: Cleaned log text.
        tail_lines: Number of lines to keep from the end of the log.
            Capped at :data:`MAX_TAIL_LINES`.

    Returns:
        Truncated log string ready to be sent to the AI model.
    """
    tail_lines = min(tail_lines, MAX_TAIL_LINES)
    lines = log_text.splitlines()
    return "\n".join(lines[-tail_lines:])


def process_log(raw_log: str, tail_lines: int = DEFAULT_TAIL_LINES) -> str:
    """Clean *raw_log* and return only the last *tail_lines* lines.

    Convenience wrapper combining :func:`clean_log` and
    :func:`extract_tail`.

    Args:
        raw_log: Raw log text from the CI/CD API.
        tail_lines: How many trailing lines to keep (default 50, max 100).

    Returns:
        Processed log snippet for AI analysis.
    """
    cleaned = clean_log(raw_log)
    return extract_tail(cleaned, tail_lines)

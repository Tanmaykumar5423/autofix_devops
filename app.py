"""
AutoFix Agent — Flask webhook server.

Receives GitLab CI/CD pipeline/job failure webhooks and orchestrates the
full self-healing flow:

  1. Trigger Layer  → filter for fixable failures (script_failure only)
  2. Log Processor  → fetch and trim logs to last 50 lines
  3. Agent Brain    → AI root-cause analysis + fix generation
  4. Action Layer   → commit fix to new branch + open Merge Request
"""

import hashlib
import hmac
import logging
import os

import gitlab
import requests
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request

from agent.action import execute_fix
from agent.brain import analyse_and_fix
from agent.log_processor import process_log
from agent.trigger import extract_failure_context, is_fixable_failure

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Webhook signature verification (optional but recommended)
# ---------------------------------------------------------------------------

def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Return True when the X-Gitlab-Token header matches WEBHOOK_SECRET."""
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret:
        return True  # Skip verification when no secret is configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Log fetching helper
# ---------------------------------------------------------------------------

def _fetch_job_log(project_id: int | str, job_id: int | str) -> str:
    """Fetch the raw job log from GitLab using the Jobs API.

    Args:
        project_id: GitLab project ID.
        job_id: CI job ID.

    Returns:
        Raw log text, or an empty string on failure.
    """
    gitlab_url = os.environ.get("GITLAB_URL", "https://gitlab.com")
    token = os.environ.get("GITLAB_TOKEN", "")

    try:
        gl = gitlab.Gitlab(gitlab_url, private_token=token)
        project = gl.projects.get(project_id)
        job = project.jobs.get(job_id)
        return job.trace().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.error("Could not fetch job log for job %s: %s", job_id, exc)
        return ""


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    """Main webhook handler — entry point for all GitLab CI events."""
    payload = request.get_data()
    signature = request.headers.get("X-Gitlab-Token", "")

    if not _verify_webhook_signature(payload, signature):
        logger.warning("Webhook signature mismatch — request rejected.")
        abort(403)

    event = request.get_json(force=True, silent=True)
    if not event:
        return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

    object_kind = event.get("object_kind", "unknown")
    logger.info("Received webhook event: object_kind=%s", object_kind)

    # ── Step 1: Trigger Layer ──────────────────────────────────────────────
    if not is_fixable_failure(event):
        logger.info("Event is not a fixable failure — skipping.")
        return jsonify({"status": "skipped", "reason": "not_a_fixable_failure"}), 200

    failure_context = extract_failure_context(event)
    logger.info("Failure context: %s", failure_context)

    # ── Step 2: Fetch & Process Logs ──────────────────────────────────────
    job_id = failure_context.get("job_id")
    project_id = failure_context.get("project_id") or os.environ.get(
        "GITLAB_PROJECT_ID", ""
    )

    raw_log = _fetch_job_log(project_id, job_id) if job_id else ""
    if not raw_log:
        logger.warning("No log available for job %s — aborting.", job_id)
        return jsonify({"status": "error", "message": "Could not fetch job log"}), 200

    log_snippet = process_log(raw_log, tail_lines=50)
    logger.info("Log snippet prepared (%d chars).", len(log_snippet))

    # ── Step 3: Agent Brain ────────────────────────────────────────────────
    try:
        analysis = analyse_and_fix(log_snippet)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    except Exception as exc:
        logger.error("AI analysis failed: %s", exc)
        return jsonify({"status": "error", "message": "AI analysis failed"}), 500

    logger.info(
        "Analysis — confidence: %s (%d%%), file: %s",
        analysis["confidence"],
        analysis["confidence_percentage"],
        analysis["affected_file"],
    )

    # ── Step 4: Action Layer ───────────────────────────────────────────────
    failure_context["project_id"] = project_id
    mr_url = execute_fix(failure_context, analysis)

    if mr_url:
        logger.info("Fix deployed — MR: %s", mr_url)
        return jsonify(
            {
                "status": "fixed",
                "merge_request_url": mr_url,
                "confidence": analysis["confidence"],
                "confidence_percentage": analysis["confidence_percentage"],
                "root_cause": analysis["root_cause"],
            }
        ), 201

    logger.warning("Fix could not be deployed (no affected file or commit error).")
    return jsonify(
        {
            "status": "analysed",
            "message": "Analysis complete but no automated fix could be committed.",
            "analysis": analysis,
        }
    ), 200


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "ok", "agent": "AutoFix DevOps Agent"}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("AutoFix Agent listening on port %d", port)
    app.run(host="0.0.0.0", port=port)

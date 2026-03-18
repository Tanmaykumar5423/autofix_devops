"""
Trigger Layer — filters incoming CI/CD pipeline webhook events.

Only real code failures (script_failure) are forwarded to the Agent Brain.
Infrastructure/runner issues are ignored to avoid false positives.
"""

# Pipeline failure reasons that indicate fixable code issues
FIXABLE_FAILURE_REASONS = {"script_failure"}

# Failure reasons to ignore (infra / runner problems — not fixable by code changes)
IGNORED_FAILURE_REASONS = {
    "runner_system_failure",
    "stuck_or_timeout_failure",
    "runner_unsupported",
    "stale_schedule",
    "job_execution_timeout",
    "archived_failure",
    "unmet_prerequisites",
    "scheduler_failure",
    "data_integrity_failure",
    "unknown_failure",
}


def is_fixable_failure(event: dict) -> bool:
    """Return True if the webhook event represents a fixable code failure.

    Only ``script_failure`` events indicate that the build script itself
    failed (compilation error, test failure, lint error, etc.) and are
    therefore candidates for automated fixing.

    Args:
        event: Parsed GitLab pipeline/job webhook payload.

    Returns:
        True when the event should be forwarded to the Agent Brain.
    """
    object_kind = event.get("object_kind", "")
    if object_kind not in ("build", "pipeline"):
        return False

    # For job (build) webhooks the failure reason is in the top-level key.
    # For pipeline webhooks we inspect the individual jobs array.
    if object_kind == "build":
        failure_reason = event.get("failure_reason", "")
        build_status = event.get("build_status", "")
        return build_status == "failed" and failure_reason in FIXABLE_FAILURE_REASONS

    # Pipeline webhook: check if any job failed with a fixable reason
    if object_kind == "pipeline":
        pipeline_status = event.get("object_attributes", {}).get("status", "")
        if pipeline_status != "failed":
            return False
        for build in event.get("builds", []):
            if (
                build.get("status") == "failed"
                and build.get("failure_reason", "") in FIXABLE_FAILURE_REASONS
            ):
                return True

    return False


def extract_failure_context(event: dict) -> dict:
    """Extract key fields from a webhook event for downstream processing.

    Args:
        event: Parsed GitLab webhook payload.

    Returns:
        Dictionary with project_id, pipeline_id, job_id, branch, and
        commit_sha so the Agent Brain knows what to fetch.
    """
    context: dict = {}

    if event.get("object_kind") == "build":
        context["job_id"] = event.get("build_id")
        context["job_name"] = event.get("build_name", "")
        context["branch"] = event.get("ref", "")
        context["commit_sha"] = event.get("sha", "")
        context["project_id"] = event.get("project_id")
        context["failure_reason"] = event.get("failure_reason", "")

    elif event.get("object_kind") == "pipeline":
        attrs = event.get("object_attributes", {})
        context["pipeline_id"] = attrs.get("id")
        context["branch"] = attrs.get("ref", "")
        context["commit_sha"] = attrs.get("sha", "")
        context["project_id"] = event.get("project", {}).get("id")
        # Pick the first failed job with a fixable reason
        for build in event.get("builds", []):
            if (
                build.get("status") == "failed"
                and build.get("failure_reason", "") in FIXABLE_FAILURE_REASONS
            ):
                context["job_id"] = build.get("id")
                context["job_name"] = build.get("name", "")
                context["failure_reason"] = build.get("failure_reason", "")
                break

    return context

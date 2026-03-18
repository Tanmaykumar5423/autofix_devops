"""
Action Layer — commits the AI-generated fix and opens a Merge Request.

Security model:
  ✅ Agent writes ONLY to a new branch (never to main/master).
  ✅ Human review is required before merging.
  ✅ The GitLab token needs only developer-level access (no owner rights).
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import gitlab

logger = logging.getLogger(__name__)


def _get_gitlab_client() -> gitlab.Gitlab:
    """Instantiate and authenticate a python-gitlab client.

    Reads ``GITLAB_URL`` and ``GITLAB_TOKEN`` from the environment.

    Returns:
        Authenticated :class:`gitlab.Gitlab` instance.

    Raises:
        ValueError: When required environment variables are missing.
    """
    url = os.environ.get("GITLAB_URL", "https://gitlab.com")
    token = os.environ.get("GITLAB_TOKEN", "")
    if not token:
        raise ValueError(
            "GITLAB_TOKEN environment variable is not set. "
            "Please configure it in your .env file."
        )
    gl = gitlab.Gitlab(url, private_token=token)
    gl.auth()
    return gl


def create_fix_branch_name(base_branch: str, job_name: str) -> str:
    """Generate a unique fix branch name.

    Args:
        base_branch: The branch where the failure occurred (e.g. "main").
        job_name: The CI job name (e.g. "test").

    Returns:
        Branch name like ``autofix/main-test-20240315T120000Z``.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_job = job_name.replace(" ", "-").replace("/", "-").lower()
    safe_base = base_branch.replace("/", "-").lower()
    return f"autofix/{safe_base}-{safe_job}-{timestamp}"


def commit_fix(
    project_id: int | str,
    fix_branch: str,
    base_branch: str,
    affected_file: str,
    code_fix: str,
    commit_message: str,
) -> bool:
    """Commit the AI-generated fix to *fix_branch* in GitLab.

    Creates the branch from *base_branch* and then commits a change to
    *affected_file* containing *code_fix*.

    Args:
        project_id: GitLab project ID or namespace/name.
        fix_branch: Name of the new branch to create.
        base_branch: The source branch to branch off.
        affected_file: Repository-relative path of the file to update.
        code_fix: File content (full replacement) or patch to apply.
        commit_message: Git commit message.

    Returns:
        True on success, False on failure.
    """
    if not code_fix or affected_file in ("", "unknown"):
        logger.warning(
            "Skipping commit: code_fix or affected_file is empty/unknown."
        )
        return False

    try:
        gl = _get_gitlab_client()
        project = gl.projects.get(project_id)

        # Create the fix branch from base_branch
        project.branches.create({"branch": fix_branch, "ref": base_branch})
        logger.info("Created branch '%s' from '%s'.", fix_branch, base_branch)

        # Commit the fix — update (or create) the affected file
        try:
            existing = project.files.get(affected_file, ref=base_branch)
            action = "update"
            _ = existing  # confirm it exists
        except gitlab.exceptions.GitlabGetError:
            action = "create"

        project.commits.create(
            {
                "branch": fix_branch,
                "commit_message": commit_message,
                "actions": [
                    {
                        "action": action,
                        "file_path": affected_file,
                        "content": code_fix,
                    }
                ],
            }
        )
        logger.info("Committed fix to '%s'.", fix_branch)
        return True

    except Exception as exc:
        logger.error("Failed to commit fix: %s", exc)
        return False


def open_merge_request(
    project_id: int | str,
    fix_branch: str,
    base_branch: str,
    title: str,
    description: str,
    assignee_id: Optional[int] = None,
) -> Optional[str]:
    """Open a GitLab Merge Request from *fix_branch* → *base_branch*.

    Args:
        project_id: GitLab project ID or namespace/name.
        fix_branch: Source branch containing the fix.
        base_branch: Target branch (e.g. "main").
        title: MR title.
        description: MR description (markdown).
        assignee_id: Optional GitLab user ID to assign the MR to.

    Returns:
        URL of the created MR, or None on failure.
    """
    try:
        gl = _get_gitlab_client()
        project = gl.projects.get(project_id)

        mr_data: dict = {
            "source_branch": fix_branch,
            "target_branch": base_branch,
            "title": title,
            "description": description,
            "remove_source_branch": True,
        }
        if assignee_id:
            mr_data["assignee_id"] = assignee_id

        mr = project.mergerequests.create(mr_data)
        logger.info("Merge Request created: %s", mr.web_url)
        return mr.web_url

    except Exception as exc:
        logger.error("Failed to create Merge Request: %s", exc)
        return None


def build_mr_description(analysis: dict, job_name: str, branch: str) -> str:
    """Build a rich Merge Request description from the AI analysis.

    Args:
        analysis: Result dict from :func:`agent.brain.analyse_and_fix`.
        job_name: Name of the failed CI job.
        branch: The branch where the failure occurred.

    Returns:
        Markdown-formatted MR description.
    """
    confidence = analysis.get("confidence", "Medium")
    confidence_pct = analysis.get("confidence_percentage", 60)
    root_cause = analysis.get("root_cause", "N/A")
    fix_description = analysis.get("fix_description", "N/A")
    code_fix = analysis.get("code_fix", "")
    affected_file = analysis.get("affected_file", "unknown")

    confidence_badge = "🟢" if confidence == "High" else "🟡"

    return f"""\
## 🤖 AutoFix Agent — Automated Fix

> **This Merge Request was generated automatically by the AutoFix Agent.**
> Human review is required before merging.

---

### 📋 Failure Summary

| Field | Value |
|-------|-------|
| **Failed Job** | `{job_name}` |
| **Branch** | `{branch}` |
| **Affected File** | `{affected_file}` |
| **Fix Confidence** | {confidence_badge} {confidence} ({confidence_pct}%) |

---

### 🔍 Root Cause

{root_cause}

---

### 🔧 Proposed Fix

{fix_description}

```
{code_fix}
```

---

### 🔐 Security Note

- ✅ This fix is committed to a **new branch only**
- ✅ It **cannot** be merged without human approval
- ✅ The agent has **no write access** to `main` or protected branches

---

*Generated by [AutoFix Agent](https://github.com/Tanmaykumar5423/autofix_devops)*
"""


def execute_fix(
    failure_context: dict,
    analysis: dict,
) -> Optional[str]:
    """Orchestrate the full action: create branch → commit → open MR.

    Args:
        failure_context: Output of :func:`agent.trigger.extract_failure_context`.
        analysis: Output of :func:`agent.brain.analyse_and_fix`.

    Returns:
        URL of the created Merge Request, or None if any step failed.
    """
    project_id = failure_context.get("project_id") or os.environ.get(
        "GITLAB_PROJECT_ID", ""
    )
    branch = failure_context.get("branch", "main")
    job_name = failure_context.get("job_name", "unknown-job")
    affected_file = analysis.get("affected_file", "unknown")
    code_fix = analysis.get("code_fix", "")

    if not project_id:
        logger.error("No project_id available — cannot execute fix.")
        return None

    fix_branch = create_fix_branch_name(branch, job_name)
    commit_message = (
        f"fix: AutoFix Agent — resolve '{job_name}' failure on '{branch}'\n\n"
        f"Root cause: {analysis.get('root_cause', 'See MR description')}\n"
        f"Confidence: {analysis.get('confidence', 'Medium')} "
        f"({analysis.get('confidence_percentage', 60)}%)"
    )

    success = commit_fix(
        project_id=project_id,
        fix_branch=fix_branch,
        base_branch=branch,
        affected_file=affected_file,
        code_fix=code_fix,
        commit_message=commit_message,
    )
    if not success:
        return None

    mr_title = (
        f"🤖 AutoFix: resolve '{job_name}' failure "
        f"[{analysis.get('confidence', 'Medium')} confidence "
        f"{analysis.get('confidence_percentage', 60)}%]"
    )
    description = build_mr_description(analysis, job_name, branch)

    return open_merge_request(
        project_id=project_id,
        fix_branch=fix_branch,
        base_branch=branch,
        title=mr_title,
        description=description,
    )

"""Tests for the Trigger Layer."""

import pytest

from agent.trigger import extract_failure_context, is_fixable_failure


# ---------------------------------------------------------------------------
# is_fixable_failure
# ---------------------------------------------------------------------------

class TestIsFixableFailure:
    """Unit tests for is_fixable_failure."""

    def test_build_script_failure_is_fixable(self):
        event = {
            "object_kind": "build",
            "build_status": "failed",
            "failure_reason": "script_failure",
        }
        assert is_fixable_failure(event) is True

    def test_build_runner_failure_is_not_fixable(self):
        event = {
            "object_kind": "build",
            "build_status": "failed",
            "failure_reason": "runner_system_failure",
        }
        assert is_fixable_failure(event) is False

    def test_build_success_is_not_fixable(self):
        event = {
            "object_kind": "build",
            "build_status": "success",
            "failure_reason": "script_failure",
        }
        assert is_fixable_failure(event) is False

    def test_pipeline_with_script_failure_job_is_fixable(self):
        event = {
            "object_kind": "pipeline",
            "object_attributes": {"status": "failed"},
            "builds": [
                {
                    "id": 1,
                    "name": "test",
                    "status": "failed",
                    "failure_reason": "script_failure",
                }
            ],
        }
        assert is_fixable_failure(event) is True

    def test_pipeline_success_is_not_fixable(self):
        event = {
            "object_kind": "pipeline",
            "object_attributes": {"status": "success"},
            "builds": [],
        }
        assert is_fixable_failure(event) is False

    def test_pipeline_all_infra_failures_not_fixable(self):
        event = {
            "object_kind": "pipeline",
            "object_attributes": {"status": "failed"},
            "builds": [
                {
                    "id": 1,
                    "name": "build",
                    "status": "failed",
                    "failure_reason": "runner_system_failure",
                }
            ],
        }
        assert is_fixable_failure(event) is False

    def test_unknown_object_kind_not_fixable(self):
        event = {"object_kind": "push", "status": "failed"}
        assert is_fixable_failure(event) is False

    def test_missing_object_kind_not_fixable(self):
        event = {}
        assert is_fixable_failure(event) is False


# ---------------------------------------------------------------------------
# extract_failure_context
# ---------------------------------------------------------------------------

class TestExtractFailureContext:
    """Unit tests for extract_failure_context."""

    def test_build_event_context(self):
        event = {
            "object_kind": "build",
            "build_id": 42,
            "build_name": "test",
            "ref": "main",
            "sha": "abc123",
            "project_id": 7,
            "failure_reason": "script_failure",
            "build_status": "failed",
        }
        ctx = extract_failure_context(event)
        assert ctx["job_id"] == 42
        assert ctx["job_name"] == "test"
        assert ctx["branch"] == "main"
        assert ctx["commit_sha"] == "abc123"
        assert ctx["project_id"] == 7
        assert ctx["failure_reason"] == "script_failure"

    def test_pipeline_event_context_picks_first_fixable_job(self):
        event = {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 99,
                "ref": "develop",
                "sha": "def456",
                "status": "failed",
            },
            "project": {"id": 3},
            "builds": [
                {
                    "id": 10,
                    "name": "lint",
                    "status": "success",
                    "failure_reason": "",
                },
                {
                    "id": 11,
                    "name": "test",
                    "status": "failed",
                    "failure_reason": "script_failure",
                },
            ],
        }
        ctx = extract_failure_context(event)
        assert ctx["job_id"] == 11
        assert ctx["job_name"] == "test"
        assert ctx["branch"] == "develop"
        assert ctx["project_id"] == 3

    def test_unknown_event_returns_empty_context(self):
        ctx = extract_failure_context({"object_kind": "note"})
        assert ctx == {}

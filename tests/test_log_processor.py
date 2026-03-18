"""Tests for the Smart Log Processor."""

import pytest

from agent.log_processor import clean_log, extract_tail, process_log


class TestCleanLog:
    """Unit tests for clean_log."""

    def test_strips_ansi_codes(self):
        raw = "\x1b[32mPASS\x1b[0m: test_foo"
        assert clean_log(raw) == "PASS: test_foo"

    def test_strips_gitlab_section_markers(self):
        raw = "section_start:1710000000:build_script\r\nnpm install\nsection_end:1710000001:build_script\r\n"
        cleaned = clean_log(raw)
        assert "section_start" not in cleaned
        assert "section_end" not in cleaned
        assert "npm install" in cleaned

    def test_plain_text_unchanged(self):
        raw = "Error: Cannot find module './app'"
        assert clean_log(raw) == raw

    def test_empty_log(self):
        assert clean_log("") == ""


class TestExtractTail:
    """Unit tests for extract_tail."""

    def test_returns_last_n_lines(self):
        lines = [f"line {i}" for i in range(1, 101)]
        log = "\n".join(lines)
        tail = extract_tail(log, tail_lines=10)
        tail_lines = tail.splitlines()
        assert len(tail_lines) == 10
        assert tail_lines[0] == "line 91"
        assert tail_lines[-1] == "line 100"

    def test_returns_all_lines_if_fewer_than_n(self):
        log = "line 1\nline 2\nline 3"
        tail = extract_tail(log, tail_lines=50)
        assert tail == log

    def test_caps_at_max_tail_lines(self):
        lines = [f"line {i}" for i in range(1, 201)]
        log = "\n".join(lines)
        # Requesting 150 lines should be capped at MAX_TAIL_LINES (100)
        tail = extract_tail(log, tail_lines=150)
        assert len(tail.splitlines()) == 100

    def test_default_tail_is_50_lines(self):
        lines = [f"line {i}" for i in range(1, 201)]
        log = "\n".join(lines)
        tail = extract_tail(log)
        assert len(tail.splitlines()) == 50


class TestProcessLog:
    """Unit tests for the combined process_log function."""

    def test_cleans_and_tails(self):
        lines = ["\x1b[0m" + f"line {i}" for i in range(1, 101)]
        raw = "\n".join(lines)
        result = process_log(raw, tail_lines=10)
        result_lines = result.splitlines()
        assert len(result_lines) == 10
        # ANSI codes should be stripped
        assert "\x1b" not in result

    def test_empty_log(self):
        assert process_log("") == ""

"""Tests for the Agent Brain (AI analysis module)."""

import pytest

from agent.brain import _parse_xml_response, analyse_and_fix


class TestParseXmlResponse:
    """Unit tests for internal XML response parser."""

    def test_parses_full_response(self):
        xml = """
<analysis>
  <root_cause>Missing semicolon on line 42.</root_cause>
  <fix_description>Add semicolon at end of statement.</fix_description>
  <code_fix>const x = 1;</code_fix>
  <confidence>High</confidence>
  <confidence_percentage>92</confidence_percentage>
  <affected_file>src/index.js</affected_file>
</analysis>
"""
        result = _parse_xml_response(xml)
        assert result["root_cause"] == "Missing semicolon on line 42."
        assert result["fix_description"] == "Add semicolon at end of statement."
        assert result["code_fix"] == "const x = 1;"
        assert result["confidence"] == "High"
        assert result["confidence_percentage"] == 92
        assert result["affected_file"] == "src/index.js"

    def test_defaults_to_medium_confidence_for_unknown_value(self):
        xml = "<analysis><confidence>Unknown</confidence><confidence_percentage>70</confidence_percentage></analysis>"
        result = _parse_xml_response(xml)
        assert result["confidence"] == "Medium"

    def test_clamps_confidence_percentage_low(self):
        xml = "<analysis><confidence>High</confidence><confidence_percentage>10</confidence_percentage></analysis>"
        result = _parse_xml_response(xml)
        assert result["confidence_percentage"] == 50

    def test_clamps_confidence_percentage_high(self):
        xml = "<analysis><confidence>High</confidence><confidence_percentage>100</confidence_percentage></analysis>"
        result = _parse_xml_response(xml)
        assert result["confidence_percentage"] == 99

    def test_handles_missing_tags(self):
        result = _parse_xml_response("<analysis></analysis>")
        assert result["root_cause"] == "Unable to determine root cause."
        assert result["fix_description"] == "Manual review required."
        assert result["code_fix"] == ""
        assert result["affected_file"] == "unknown"

    def test_medium_confidence_gets_reasonable_default_percentage(self):
        xml = "<analysis><confidence>Medium</confidence></analysis>"
        result = _parse_xml_response(xml)
        assert result["confidence"] == "Medium"
        assert 50 <= result["confidence_percentage"] <= 99


class TestAnalyseAndFix:
    """Integration-style tests for analyse_and_fix (AI calls mocked)."""

    def test_raises_value_error_without_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            analyse_and_fix("some log snippet")

    def test_calls_openai_and_returns_analysis(self, monkeypatch):
        """Mock the OpenAI client to avoid real API calls."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        xml_response = """
<analysis>
  <root_cause>Import error: module not found.</root_cause>
  <fix_description>Install missing dependency.</fix_description>
  <code_fix>pip install requests</code_fix>
  <confidence>High</confidence>
  <confidence_percentage>88</confidence_percentage>
  <affected_file>requirements.txt</affected_file>
</analysis>
"""

        class FakeMessage:
            content = xml_response

        class FakeChoice:
            message = FakeMessage()

        class FakeCompletion:
            choices = [FakeChoice()]

        class FakeChat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return FakeCompletion()

        class FakeClient:
            chat = FakeChat()

        monkeypatch.setattr("agent.brain.openai.OpenAI", lambda **kw: FakeClient())

        result = analyse_and_fix("ModuleNotFoundError: No module named 'requests'")
        assert result["confidence"] == "High"
        assert result["confidence_percentage"] == 88
        assert result["affected_file"] == "requirements.txt"
        assert "requests" in result["code_fix"]

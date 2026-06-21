"""Tests for ClaudeAdapter and OpenAIAdapter."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.adapters.claude_adapter import ClaudeAdapter
from src.adapters.openai_adapter import OpenAIAdapter

# ---------------------------------------------------------------------------
# ClaudeAdapter
# ---------------------------------------------------------------------------


@pytest.fixture()
def claude():
    with patch("src.adapters.claude_adapter.settings") as ms:
        ms.ANTHROPIC_API_KEY = "test-key"
        ms.ANTHROPIC_MODEL = "claude-3-haiku-20240307"
        adapter = ClaudeAdapter()
        yield adapter


class TestClaudeAdapterName:
    def test_name_is_claude(self, claude):
        assert claude.name == "claude"


class TestClaudeAdapterGetClient:
    def test_lazy_loads_client(self, claude):
        mock_client = MagicMock()
        mock_anthropic = MagicMock(Anthropic=MagicMock(return_value=mock_client))
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            claude._client = None
            client = claude._get_client()
            assert client is mock_client

    def test_caches_client(self, claude):
        mock_client = MagicMock()
        claude._client = mock_client
        assert claude._get_client() is mock_client

    def test_raises_on_import_error(self, claude):
        claude._client = None
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(Exception):
                claude._get_client()


class TestClaudeAdapterGenerateResponse:
    def test_returns_text_content(self, claude):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello there!")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        claude._client = mock_client

        result = claude.generate_response("Hi")
        assert result == "Hello there!"
        mock_client.messages.create.assert_called_once()

    def test_empty_content_returns_empty_string(self, claude):
        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage.input_tokens = 1
        mock_response.usage.output_tokens = 0
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        claude._client = mock_client

        result = claude.generate_response("Hi")
        assert result == ""

    def test_includes_system_prompt_when_provided(self, claude):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="OK")]
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 1
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        claude._client = mock_client

        claude.generate_response("Hi", system_prompt="Be concise")
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "system" in call_kwargs
        assert call_kwargs["system"] == "Be concise"

    def test_omits_system_when_empty(self, claude):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="OK")]
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 1
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        claude._client = mock_client

        claude.generate_response("Hi", system_prompt="")
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "system" not in call_kwargs

    def test_raises_on_api_error(self, claude):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API error")
        claude._client = mock_client

        with pytest.raises(RuntimeError):
            claude.generate_response("Hi")


class TestClaudeAdapterHealthCheck:
    def test_returns_true_on_success(self, claude):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock()
        claude._client = mock_client
        assert claude.health_check() is True

    def test_returns_false_on_error(self, claude):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("bad key")
        claude._client = mock_client
        assert claude.health_check() is False


class TestClaudeBuildMessages:
    def test_no_history_returns_single_user_message(self):
        msgs = ClaudeAdapter._build_messages("hello", "")
        assert msgs == [{"role": "user", "content": "hello"}]

    def test_parses_history_lines(self):
        history = "User: how are you?\nAI: Fine thanks.\n"
        msgs = ClaudeAdapter._build_messages("what else?", history)
        assert msgs[0] == {"role": "user", "content": "how are you?"}
        assert msgs[1] == {"role": "assistant", "content": "Fine thanks."}
        assert msgs[-1] == {"role": "user", "content": "what else?"}

    def test_ignores_unknown_prefixes(self):
        history = "System: ignore\nUser: hi\n"
        msgs = ClaudeAdapter._build_messages("ok", history)
        assert msgs[0] == {"role": "user", "content": "hi"}


# ---------------------------------------------------------------------------
# OpenAIAdapter
# ---------------------------------------------------------------------------


@pytest.fixture()
def openai_adapter():
    with patch("src.adapters.openai_adapter.settings") as ms:
        ms.OPENAI_API_KEY = "test-key"
        ms.OPENAI_MODEL = "gpt-4o-mini"
        adapter = OpenAIAdapter()
        yield adapter


class TestOpenAIAdapterName:
    def test_name_is_openai(self, openai_adapter):
        assert openai_adapter.name == "openai"


class TestOpenAIAdapterGetClient:
    def test_lazy_loads_client(self, openai_adapter):
        mock_client = MagicMock()
        mock_openai = MagicMock(OpenAI=MagicMock(return_value=mock_client))
        with patch.dict("sys.modules", {"openai": mock_openai}):
            openai_adapter._client = None
            client = openai_adapter._get_client()
            assert client is mock_client

    def test_caches_client(self, openai_adapter):
        mock_client = MagicMock()
        openai_adapter._client = mock_client
        assert openai_adapter._get_client() is mock_client

    def test_raises_on_import_error(self, openai_adapter):
        openai_adapter._client = None
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(Exception):
                openai_adapter._get_client()


class TestOpenAIAdapterGenerateResponse:
    def test_returns_text_content(self, openai_adapter):
        mock_choice = MagicMock()
        mock_choice.message.content = "Response here"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 20
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        openai_adapter._client = mock_client

        result = openai_adapter.generate_response("Hi")
        assert result == "Response here"

    def test_none_content_returns_empty_string(self, openai_adapter):
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 5
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        openai_adapter._client = mock_client

        result = openai_adapter.generate_response("Hi")
        assert result == ""

    def test_raises_on_api_error(self, openai_adapter):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("rate limit")
        openai_adapter._client = mock_client

        with pytest.raises(RuntimeError):
            openai_adapter.generate_response("Hi")


class TestOpenAIAdapterHealthCheck:
    def test_returns_true_when_models_available(self, openai_adapter):
        mock_client = MagicMock()
        mock_client.models.list.return_value = iter([MagicMock(), MagicMock()])
        openai_adapter._client = mock_client
        assert openai_adapter.health_check() is True

    def test_returns_false_on_error(self, openai_adapter):
        mock_client = MagicMock()
        mock_client.models.list.side_effect = RuntimeError("auth error")
        openai_adapter._client = mock_client
        assert openai_adapter.health_check() is False


class TestOpenAIBuildMessages:
    def test_no_system_no_history(self):
        msgs = OpenAIAdapter._build_messages("hello", "", "")
        assert msgs == [{"role": "user", "content": "hello"}]

    def test_adds_system_message_first(self):
        msgs = OpenAIAdapter._build_messages("hi", "Be helpful", "")
        assert msgs[0] == {"role": "system", "content": "Be helpful"}
        assert msgs[-1] == {"role": "user", "content": "hi"}

    def test_parses_history(self):
        history = "User: question\nAI: answer\n"
        msgs = OpenAIAdapter._build_messages("follow up", "", history)
        assert {"role": "user", "content": "question"} in msgs
        assert {"role": "assistant", "content": "answer"} in msgs

    def test_ignores_unknown_prefixes_in_history(self):
        history = "System: ignore this\nUser: valid\n"
        msgs = OpenAIAdapter._build_messages("next", "", history)
        assert {"role": "user", "content": "valid"} in msgs
        assert not any(m.get("content") == "ignore this" for m in msgs)

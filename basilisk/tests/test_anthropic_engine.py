import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import AsyncGenerator

import anthropic
from anthropic.types import MessageParam

from basilisk.provider_engine.anthropic_engine import AnthropicEngine
from basilisk.provider_engine.types import (
    ChatMessage,
    ChatResponse,
    ProviderConfig,
    StreamingChatResponse,
)

@pytest.fixture
def sample_config():
    """Create a sample ProviderConfig for testing."""
    return ProviderConfig(
        api_key="test-api-key",
        model="claude-3-sonnet-20240229",
        temperature=0.7,
        max_tokens=1000,
        timeout=30.0,
    )

@pytest.fixture
def minimal_config():
    """Create a minimal ProviderConfig with only required fields."""
    return ProviderConfig(api_key="test-api-key")

@pytest.fixture
def sample_messages():
    """Create sample chat messages for testing."""
    return [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there!"),
        ChatMessage(role="user", content="How are you?"),
    ]

@pytest.fixture
def empty_messages():
    """Create empty messages list for edge case testing."""
    return []

@pytest.fixture
def invalid_messages():
    """Create invalid messages for error testing."""
    return [
        ChatMessage(role="invalid_role", content="Test"),
        ChatMessage(role="user", content=""),
    ]

@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic API response."""
    mock_response = Mock()
    mock_response.content = [Mock(text="Test response")]
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_response.stop_reason = "end_turn"
    return mock_response

@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    with patch('basilisk.provider_engine.anthropic_engine.anthropic.AsyncAnthropic') as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        yield mock_client

class TestAnthropicEngineInitialization:
    """Test AnthropicEngine initialization."""

    def test_init_with_full_config(self, sample_config, mock_anthropic_client):
        """Test initialization with complete configuration."""
        engine = AnthropicEngine(sample_config)

        assert engine.config == sample_config
        assert engine.model == "claude-3-sonnet-20240229"
        assert engine.client is not None

    def test_init_with_minimal_config(self, minimal_config, mock_anthropic_client):
        """Test initialization with minimal configuration."""
        engine = AnthropicEngine(minimal_config)

        assert engine.config == minimal_config
        assert engine.model == "claude-3-sonnet-20240229"  # default model
        assert engine.client is not None

    def test_init_sets_client_timeout(self, sample_config, mock_anthropic_client):
        """Test that client timeout is properly set."""
        with patch('basilisk.provider_engine.anthropic_engine.anthropic.AsyncAnthropic') as mock_class:
            engine = AnthropicEngine(sample_config)

            mock_class.assert_called_once_with(
                api_key="test-api-key",
                timeout=30.0,
            )

    def test_init_default_timeout(self, minimal_config, mock_anthropic_client):
        """Test default timeout when not specified in config."""
        with patch('basilisk.provider_engine.anthropic_engine.anthropic.AsyncAnthropic') as mock_class:
            engine = AnthropicEngine(minimal_config)

            mock_class.assert_called_once_with(
                api_key="test-api-key",
                timeout=30.0,  # default timeout
            )

    def test_init_inherits_from_base_engine(self, sample_config):
        """Test that AnthropicEngine inherits from BaseEngine."""
        from basilisk.provider_engine.base_engine import BaseEngine
        engine = AnthropicEngine(sample_config)
        assert isinstance(engine, BaseEngine)

class TestAnthropicEngineChat:
    """Test AnthropicEngine chat functionality."""

    @pytest.mark.asyncio
    async def test_chat_success(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test successful chat completion."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(sample_messages)

        assert isinstance(response, ChatResponse)
        assert response.content == "Test response"
        assert response.model == "claude-3-sonnet-20240229"
        assert response.usage == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
        assert response.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test chat with system prompt."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, system_prompt="You are a helpful assistant")

        mock_anthropic_client.messages.create.assert_called_once()
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["system"] == "You are a helpful assistant"

    @pytest.mark.asyncio
    async def test_chat_with_temperature_override(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test chat with temperature override."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, temperature=0.9)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_chat_with_max_tokens_override(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test chat with max_tokens override."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, max_tokens=2000)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["max_tokens"] == 2000

    @pytest.mark.parametrize("temperature", [0.0, 0.5, 1.0])
    @pytest.mark.asyncio
    async def test_chat_temperature_clamping_valid(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response, temperature):
        """Test temperature clamping for valid values."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, temperature=temperature)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["temperature"] == temperature

    @pytest.mark.parametrize("temperature,expected", [(-0.1, 0.0), (1.1, 1.0), (2.0, 1.0)])
    @pytest.mark.asyncio
    async def test_chat_temperature_clamping_edge_cases(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response, temperature, expected):
        """Test temperature clamping for out-of-range values."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, temperature=temperature)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["temperature"] == expected

    @pytest.mark.asyncio
    async def test_chat_uses_config_defaults(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test that chat uses config defaults when parameters not provided."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["temperature"] == 0.7  # from config
        assert call_args["max_tokens"] == 1000  # from config

    @pytest.mark.asyncio
    async def test_chat_fallback_defaults(self, minimal_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test fallback to hardcoded defaults when config doesn't specify."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(minimal_config)
        await engine.chat(sample_messages)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["max_tokens"] == 4096  # fallback default
        assert "temperature" not in call_args  # not set when None

    @pytest.mark.asyncio
    async def test_chat_api_error(self, sample_config, sample_messages, mock_anthropic_client):
        """Test handling of Anthropic API errors."""
        error = anthropic.APIError("API Error")
        mock_anthropic_client.messages.create.side_effect = error

        engine = AnthropicEngine(sample_config)

        with pytest.raises(anthropic.APIError):
            await engine.chat(sample_messages)

    @pytest.mark.asyncio
    async def test_chat_unexpected_error(self, sample_config, sample_messages, mock_anthropic_client):
        """Test handling of unexpected errors."""
        mock_anthropic_client.messages.create.side_effect = Exception("Unexpected error")

        engine = AnthropicEngine(sample_config)

        with pytest.raises(Exception) as exc_info:
            await engine.chat(sample_messages)
        assert str(exc_info.value) == "Unexpected error"

class TestAnthropicEngineStreamChat:
    """Test AnthropicEngine streaming chat functionality."""

    @pytest.mark.asyncio
    async def test_stream_chat_success(self, sample_config, sample_messages, mock_anthropic_client):
        """Test successful streaming chat."""
        # Mock streaming response
        mock_chunk1 = Mock()
        mock_chunk1.delta = Mock(text="Hello ")
        mock_chunk2 = Mock()
        mock_chunk2.delta = Mock(text="world!")

        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = mock_stream
        mock_stream.__aexit__.return_value = None
        mock_stream.__aiter__.return_value = iter([mock_chunk1, mock_chunk2])

        mock_anthropic_client.messages.stream.return_value = mock_stream

        engine = AnthropicEngine(sample_config)
        responses = []

        async for response in engine.stream_chat(sample_messages):
            responses.append(response)

        assert len(responses) == 2
        assert responses[0].content == "Hello "
        assert responses[1].content == "world!"
        assert all(r.model == "claude-3-sonnet-20240229" for r in responses)
        assert all(r.finish_reason is None for r in responses)

    @pytest.mark.asyncio
    async def test_stream_chat_with_system_prompt(self, sample_config, sample_messages, mock_anthropic_client):
        """Test streaming chat with system prompt."""
        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = mock_stream
        mock_stream.__aexit__.return_value = None
        mock_stream.__aiter__.return_value = iter([])

        mock_anthropic_client.messages.stream.return_value = mock_stream

        engine = AnthropicEngine(sample_config)

        # Consume the async generator
        responses = []
        async for response in engine.stream_chat(sample_messages, system_prompt="Test system"):
            responses.append(response)

        call_args = mock_anthropic_client.messages.stream.call_args[1]
        assert call_args["system"] == "Test system"
        assert call_args["stream"] is True

    @pytest.mark.asyncio
    async def test_stream_chat_api_error(self, sample_config, sample_messages, mock_anthropic_client):
        """Test streaming chat API error handling."""
        error = anthropic.APIError("Stream API Error")
        mock_anthropic_client.messages.stream.side_effect = error

        engine = AnthropicEngine(sample_config)

        with pytest.raises(anthropic.APIError):
            async for response in engine.stream_chat(sample_messages):
                pass

    @pytest.mark.asyncio
    async def test_stream_chat_unexpected_error(self, sample_config, sample_messages, mock_anthropic_client):
        """Test streaming chat unexpected error handling."""
        mock_anthropic_client.messages.stream.side_effect = Exception("Stream error")

        engine = AnthropicEngine(sample_config)

        with pytest.raises(Exception) as exc_info:
            async for response in engine.stream_chat(sample_messages):
                pass
        assert str(exc_info.value) == "Stream error"

    @pytest.mark.asyncio
    async def test_stream_chat_empty_chunks(self, sample_config, sample_messages, mock_anthropic_client):
        """Test streaming chat with empty chunks."""
        mock_chunk_no_delta = Mock()
        if hasattr(mock_chunk_no_delta, 'delta'): delattr(mock_chunk_no_delta, 'delta')

        mock_chunk_no_text = Mock()
        mock_chunk_no_text.delta = Mock()
        if hasattr(mock_chunk_no_text.delta, 'text'): delattr(mock_chunk_no_text.delta, 'text')

        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = mock_stream
        mock_stream.__aexit__.return_value = None
        mock_stream.__aiter__.return_value = iter([mock_chunk_no_delta, mock_chunk_no_text])

        mock_anthropic_client.messages.stream.return_value = mock_stream

        engine = AnthropicEngine(sample_config)
        responses = []

        async for response in engine.stream_chat(sample_messages):
            responses.append(response)

        # Should not yield any responses for chunks without text
        assert len(responses) == 0

class TestAnthropicEngineMessageConversion:
    """Test AnthropicEngine message conversion functionality."""

    def test_convert_messages_success(self, sample_config):
        """Test successful message conversion."""
        engine = AnthropicEngine(sample_config)
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
        ]

        result = engine._convert_messages(messages)

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there!"}

    def test_convert_messages_empty_list(self, sample_config):
        """Test conversion with empty message list."""
        engine = AnthropicEngine(sample_config)

        with pytest.raises(ValueError, match="Messages cannot be empty"):
            engine._convert_messages([])

    def test_convert_messages_invalid_role(self, sample_config):
        """Test conversion with invalid message role."""
        engine = AnthropicEngine(sample_config)
        messages = [ChatMessage(role="invalid", content="Test")]

        with pytest.raises(ValueError, match="Invalid message role: invalid"):
            engine._convert_messages(messages)

    def test_convert_messages_system_role_warning(self, sample_config, caplog):
        """Test that system messages are skipped with warning."""
        engine = AnthropicEngine(sample_config)
        messages = [
            ChatMessage(role="system", content="System prompt"),
            ChatMessage(role="user", content="User message"),
        ]

        result = engine._convert_messages(messages)

        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "User message"}
        assert "System message found in messages list" in caplog.text

    def test_convert_messages_empty_content_skipped(self, sample_config):
        """Test that messages with empty content are skipped."""
        engine = AnthopicEngine(sample_config)
        messages = [
            ChatMessage(role="user", content=""),
            ChatMessage(role="user", content="Valid message"),
        ]

        result = engine._convert_messages(messages)

        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "Valid message"}

    def test_convert_messages_all_invalid_raises_error(self, sample_config):
        """Test that conversion fails when all messages are invalid."""
        engine = AnthropicEngine(sample_config)
        messages = [
            ChatMessage(role="system", content="System only"),
            ChatMessage(role="user", content=""),
        ]

        with pytest.raises(ValueError, match="No valid messages after conversion"):
            engine._convert_messages(messages)

    @pytest.mark.parametrize("role", ["user", "assistant"])
    def test_convert_messages_valid_roles(self, sample_config, role):
        """Test conversion with valid roles."""
        engine = AnthropicEngine(sample_config)
        messages = [ChatMessage(role=role, content="Test message")]

        result = engine._convert_messages(messages)

        assert len(result) == 1
        assert result[0]["role"] == role
        assert result[0]["content"] == "Test message"

    def test_convert_messages_mixed_valid_invalid(self, sample_config, caplog):
        """Test conversion with mix of valid and invalid messages."""
        engine = AnthropicEngine(sample_config)
        messages = [
            ChatMessage(role="system", content="System"),  # skipped
            ChatMessage(role="user", content="Valid"),     # kept
            ChatMessage(role="user", content=""),          # skipped
            ChatMessage(role="assistant", content="Also valid"),  # kept
        ]

        result = engine._convert_messages(messages)

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Valid"}
        assert result[1] == {"role": "assistant", "content": "Also valid"}

class TestAnthropicEngineEdgeCases:
    """Test AnthropicEngine edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_chat_with_none_messages(self, sample_config, mock_anthropic_client):
        """Test chat with None messages."""
        engine = AnthropicEngine(sample_config)

        with pytest.raises(ValueError):
            await engine.chat(None)

    @pytest.mark.asyncio
    async def test_chat_response_no_content(self, sample_config, sample_messages, mock_anthropic_client):
        """Test handling response with no content."""
        mock_response = Mock()
        mock_response.content = []
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 0
        mock_response.stop_reason = "end_turn"

        mock_anthropic_client.messages.create.return_value = mock_response

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(sample_messages)

        assert response.content == ""
        assert response.usage["completion_tokens"] == 0

    @pytest.mark.asyncio
    async def test_chat_response_no_usage(self, sample_config, sample_messages, mock_anthropic_client):
        """Test handling response with no usage information."""
        mock_response = Mock()
        mock_response.content = [Mock(text="Test")]
        mock_response.usage = None
        mock_response.stop_reason = "end_turn"

        mock_anthropic_client.messages.create.return_value = mock_response

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(sample_messages)

        assert response.usage == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    @pytest.mark.asyncio
    async def test_chat_response_multiple_content_blocks(self, sample_config, sample_messages, mock_anthropic_client):
        """Test response with multiple content blocks."""
        mock_response = Mock()
        mock_response.content = [
            Mock(text="First part "),
            Mock(text="second part."),
        ]
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 8
        mock_response.stop_reason = "end_turn"

        mock_anthropic_client.messages.create.return_value = mock_response

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(sample_messages)

        assert response.content == "First part second part."

    @pytest.mark.asyncio
    async def test_chat_response_content_block_no_text(self, sample_config, sample_messages, mock_anthropic_client):
        """Test response with content block that has no text attribute."""
        mock_block = Mock()
        if hasattr(mock_block, 'text'): delattr(mock_block, 'text')

        mock_response = Mock()
        mock_response.content = [mock_block]
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 0
        mock_response.stop_reason = "end_turn"

        mock_anthropic_client.messages.create.return_value = mock_response

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(sample_messages)

        assert response.content == ""

    @pytest.mark.parametrize("extreme_value", [0, 10000, -100])
    @pytest.mark.asyncio
    async def test_chat_extreme_max_tokens(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response, extreme_value):
        """Test chat with extreme max_tokens values."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, max_tokens=extreme_value)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["max_tokens"] == extreme_value

    @pytest.mark.asyncio
    async def test_close_method(self, sample_config, mock_anthropic_client):
        """Test the close method."""
        mock_anthropic_client.close = AsyncMock()

        engine = AnthropicEngine(sample_config)
        await engine.close()

        mock_anthropic_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_method_no_close_attribute(self, sample_config, mock_anthropic_client):
        """Test close method when client has no close attribute."""
        # Remove close method if it exists
        if hasattr(mock_anthropic_client, 'close'):
            delattr(mock_anthropic_client, 'close')

        engine = AnthropicEngine(sample_config)
        # Should not raise an exception
        await engine.close()

class TestAnthropicEngineParameterized:
    """Parameterized tests for comprehensive coverage."""

    @pytest.mark.parametrize("api_key", [
        "sk-test-key",
        "very-long-api-key-with-many-characters-12345",
        "key-with-special-chars-!@#$%",
    ])
    def test_init_with_different_api_keys(self, api_key, mock_anthropic_client):
        """Test initialization with various API key formats."""
        config = ProviderConfig(api_key=api_key)
        engine = AnthropicEngine(config)
        assert engine.config.api_key == api_key

    @pytest.mark.parametrize("model", [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        None,
    ])
    def test_init_with_different_models(self, model, mock_anthropic_client):
        """Test initialization with different model names."""
        config = ProviderConfig(api_key="test", model=model)
        engine = AnthropicEngine(config)
        expected_model = model or "claude-3-sonnet-20240229"
        assert engine.model == expected_model

    @pytest.mark.parametrize("temperature", [0.0, 0.3, 0.7, 1.0, None])
    @pytest.mark.asyncio
    async def test_chat_with_various_temperatures(self, sample_config, sample_messages, mock_anthropիրacic_client, mock_anthropic_response, temperature):
        """Test chat with various temperature values."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response
        sample_config.temperature = None  # Clear config temperature

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, temperature=temperature)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        if temperature is not None:
            assert call_args["temperature"] == temperature
        else:
            assert "temperature" not in call_args

    @pytest.mark.parametrize("max_tokens", [1, 100, 4096, 8192, None])
    @pytest.mark.asyncio
    async def test_chat_with_various_max_tokens(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response, max_tokens):
        """Test chat with various max_tokens values."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, max_tokens=max_tokens)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        expected_tokens = max_tokens or 1000  # from config
        assert call_args["max_tokens"] == expected_tokens

    @pytest.mark.parametrize("system_prompt", [
        "You are a helpful assistant.",
        "",
        "Very long system prompt " * 100,
        "System prompt with special chars: !@#$%^&*()",
        None,
    ])
    @pytest.mark.asyncio
    async def test_chat_with_various_system_prompts(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response, system_prompt):
        """Test chat with various system prompts."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)
        await engine.chat(sample_messages, system_prompt=system_prompt)

        call_args = mock_anthropic_client.messages.create.call_args[1]
        if system_prompt:
            assert call_args["system"] == system_prompt
        else:
            assert "system" not in call_args

    @pytest.mark.parametrize("num_messages", [1, 2, 5, 10, 50])
    @pytest.mark.asyncio
    async def test_chat_with_varying_message_counts(self, sample_config, mock_anthropic_client, mock_anthropic_response, num_messages):
        """Test chat with varying numbers of messages."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        messages = []
        for i in range(num_messages):
            role = "user" if i % 2 == 0 else "assistant"
            messages.append(ChatMessage(role=role, content=f"Message {i}"))

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(messages)

        assert isinstance(response, ChatResponse)
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert len(call_args["messages"]) == num_messages

    @pytest.mark.parametrize("content_length", [1, 100, 1000, 10000])
    @pytest.mark.asyncio
    async def test_chat_with_varying_content_lengths(self, sample_config, mock_anthropic_client, mock_anthropic_response, content_length):
        """Test chat with varying message content lengths."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        content = "x" * content_length
        messages = [ChatMessage(role="user", content=content)]

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(messages)

        assert isinstance(response, ChatResponse)
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["messages"][0]["content"] == content

class TestAnthropicEngineIntegration:
    """Integration and performance-related tests."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_chat_requests(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test handling multiple concurrent chat requests."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        engine = AnthropicEngine(sample_config)

        # Create multiple concurrent requests
        tasks = [
            engine.chat(sample_messages)
            for _ in range(5)
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 5
        assert all(isinstance(r, ChatResponse) for r in responses)
        assert mock_anthropic_client.messages.create.call_count == 5

    @pytest.mark.asyncio
    async def test_chat_and_stream_interleaved(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test interleaving regular chat and streaming chat."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        # Mock streaming
        mock_chunk = Mock()
        mock_chunk.delta = Mock(text="Streamed response")
        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = mock_stream
        mock_stream.__aexit__.return_value = None
        mock_stream.__aiter__.return_value = iter([mock_chunk])
        mock_anthropic_client.messages.stream.return_value = mock_stream

        engine = AnthropicEngine(sample_config)

        # Regular chat
        chat_response = await engine.chat(sample_messages)

        # Streaming chat
        stream_responses = []
        async for response in engine.stream_chat(sample_messages):
            stream_responses.append(response)

        assert isinstance(chat_response, ChatResponse)
        assert len(stream_responses) == 1
        assert stream_responses[0].content == "Streamed response"

    @pytest.mark.asyncio
    async def test_engine_lifecycle(self, sample_config, mock_anthropic_client):
        """Test complete engine lifecycle."""
        engine = AnthropicEngine(sample_config)

        # Test initialization
        assert engine.client is not None
        assert engine.model == sample_config.model

        # Test close
        mock_anthropic_client.close = AsyncMock()
        await engine.close()
        mock_anthropic_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_recovery(self, sample_config, sample_messages, mock_anthropic_client, mock_anthropic_response):
        """Test error recovery - engine should work after an error."""
        # First call fails
        mock_anthropic_client.messages.create.side_effect = [
            anthropic.APIError("Temporary error"),
            mock_anthropic_response,
        ]

        engine = AnthropicEngine(sample_config)

        # First call should fail
        with pytest.raises(anthropic.APIError):
            await engine.chat(sample_messages)

        # Second call should succeed
        response = await engine.chat(sample_messages)
        assert isinstance(response, ChatResponse)

    @pytest.mark.asyncio
    async def test_large_conversation_handling(self, sample_config, mock_anthropic_client, mock_anthropic_response):
        """Test handling of large conversation history."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        # Create a large conversation
        large_messages = []
        for i in range(100):
            role = "user" if i % 2 == 0 else "assistant"
            large_messages.append(ChatMessage(role=role, content=f"Message {i}"))

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(large_messages)

        assert isinstance(response, ChatResponse)
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert len(call_args["messages"]) == 100

class TestAnthropicEngineComprehensive:
    """Comprehensive tests covering remaining edge cases."""

    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, sample_config, mock_anthropic_client, mock_anthropic_response):
        """Test handling of unicode content in messages."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        unicode_messages = [
            ChatMessage(role="user", content="Hello 🌍"),
            ChatMessage(role="user", content="测试中文"),
            ChatMessage(role="user", content="Émojis and ñoñö"),
        ]

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(unicode_messages)

        assert isinstance(response, ChatResponse)
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["messages"][0]["content"] == "Hello 🌍"
        assert call_args["messages"][1]["content"] == "测试中文"
        assert call_args["messages"][2]["content"] == "Émojis and ñoñö"

    @pytest.mark.asyncio
    async def test_json_content_handling(self, sample_config, mock_anthropic_client, mock_anthropic_response):
        """Test handling of JSON content in messages."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        json_content = json.dumps({"key": "value", "nested": {"array": [1, 2, 3]}})
        messages = [ChatMessage(role="user", content=json_content)]

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(messages)

        assert isinstance(response, ChatResponse)
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["messages"][0]["content"] == json_content

    @pytest.mark.asyncio
    async def test_multiline_content_handling(self, sample_config, mock_anthropic_client, mock_anthropic_response):
        """Test handling of multiline content."""
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response

        multiline_content = """This is a
        multiline
        message with
        various indentation."""

        messages = [ChatMessage(role="user", content=multiline_content)]

        engine = AnthropicEngine(sample_config)
        response = await engine.chat(messages)

        assert isinstance(response, ChatResponse)
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args["messages"][0]["content"] == multiline_content

    def test_engine_string_representation(self, sample_config):
        """Test string representation of engine (if implemented)."""
        engine = AnthropicEngine(sample_config)
        # This test verifies that str/repr don't crash
        str_repr = str(engine)
        assert "AnthropicEngine" in str_repr or str_repr is not None

    @pytest.mark.asyncio
    async def test_response_finish_reason_variations(self, sample_config, sample_messages, mock_anthropic_client):
        """Test different finish reasons in responses."""
        finish_reasons = ["end_turn", "max_tokens", "stop_sequence", None]

        for finish_reason in finish_reasons:
            mock_response = Mock()
            mock_response.content = [Mock(text="Test response")]
            mock_response.usage = Mock()
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 5
            mock_response.stop_reason = finish_reason

            mock_anthropic_client.messages.create.return_value = mock_response

            engine = AnthropicEngine(sample_config)
            response = await engine.chat(sample_messages)

            assert response.finish_reason == finish_reason

    @pytest.mark.asyncio 
    async def test_config_property_access(self, sample_config):
        """Test that config properties are accessible."""
        engine = AnthropicEngine(sample_config)

        assert engine.config == sample_config
        assert engine.config.api_key == sample_config.api_key
        assert engine.config.model == sample_config.model
        assert engine.config.temperature == sample_config.temperature
        assert engine.config.max_tokens == sample_config.max_tokens
        assert engine.config.timeout == sample_config.timeout

"""
Comprehensive unit tests for AnthropicEngine.

This test suite covers:
- Initialization with various configurations
- Chat functionality (happy path, edge cases, errors)
- Streaming chat functionality  
- Message conversion logic
- Parameter validation and clamping
- Error handling and recovery
- Unicode and special content handling
- Concurrent request handling
- Engine lifecycle management

Testing framework: pytest with pytest-asyncio for async support
Mocking: unittest.mock for external dependencies
"""
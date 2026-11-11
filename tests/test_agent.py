"""
Tests for ConversationalAgent, LLMGateway, and prompt management.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from minimi.agent import ConversationalAgent
from minimi.config import Config
from minimi.llm import LLMGateway, LLMResponse, ToolCall
from minimi.prompts import format_context_block, get_system_prompt


def test_system_prompt_temporal_grounding():
    """Verify system prompt includes dynamic UTC timestamp and grounding instructions."""
    fixed_time = datetime(2026, 11, 11, 22, 0, 0, tzinfo=timezone.utc)
    prompt = get_system_prompt(current_time=fixed_time)
    assert "2026-11-11T22:00:00+00:00" in prompt
    assert "Wednesday, November 11, 2026" in prompt
    assert "You are Minimi" in prompt
    assert "<temporal_context>" in prompt


def test_format_context_block():
    """Verify formatting of search and memory context injection."""
    block = format_context_block(
        search_context="Source: Example.com - Info",
        memory_context="Turn 1: User asked about Python",
    )
    assert "<chronological_memory>" in block
    assert "Turn 1: User asked about Python" in block
    assert "<retrieved_search_evidence>" in block
    assert "Source: Example.com - Info" in block


def test_llm_gateway_complete_mock(monkeypatch):
    """Verify LLMGateway completion parsing and tool call handling."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Response from model"
    mock_choice.message.tool_calls = None
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 12
    mock_response.usage.completion_tokens = 8
    mock_response.usage.total_tokens = 20

    monkeypatch.setattr("litellm.completion", lambda **kwargs: mock_response)

    gateway = LLMGateway()
    res = gateway.complete(messages=[{"role": "user", "content": "Hi"}])
    assert res.content == "Response from model"
    assert res.usage["total_tokens"] == 20
    assert len(res.tool_calls) == 0


def test_agent_conversation_turn(mock_config):
    """Verify agent single turn execution and history tracking."""
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = LLMResponse(
        content="Hello! How can I assist you today?",
        model="mock/mock-model",
        tool_calls=[],
    )

    agent = ConversationalAgent(config=mock_config, llm_gateway=mock_gateway)
    response = agent.step("Hello")

    assert response == "Hello! How can I assist you today?"
    assert len(agent.state.messages) >= 3  # system, user, assistant
    assert agent.state.messages[1]["role"] == "user"
    assert agent.state.messages[1]["content"] == "Hello"
    assert agent.state.messages[2]["role"] == "assistant"
    assert agent.state.messages[2]["content"] == "Hello! How can I assist you today?"


def test_agent_tool_dispatch(mock_config):
    """Verify agent detects tool calls, executes registered tool, and returns final answer."""
    mock_gateway = MagicMock()

    # Step 1: LLM returns a tool call to 'get_weather'
    step1_response = LLMResponse(
        content="",
        model="mock/mock-model",
        tool_calls=[
            ToolCall(
                id="call_1",
                name="get_weather",
                arguments={"location": "San Francisco"},
            )
        ],
    )
    # Step 2: LLM returns final response after seeing tool output
    step2_response = LLMResponse(
        content="The weather in San Francisco is 65F and sunny.",
        model="mock/mock-model",
        tool_calls=[],
    )
    mock_gateway.complete.side_effect = [step1_response, step2_response]

    agent = ConversationalAgent(config=mock_config, llm_gateway=mock_gateway)

    # Register tool
    def get_weather(location: str):
        return f"{location}: 65F, Sunny"

    agent.register_tool(
        name="get_weather",
        description="Get current weather",
        parameters={
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
        func=get_weather,
    )

    response = agent.step("What is the weather in SF?")
    assert response == "The weather in San Francisco is 65F and sunny."

    # Check messages trace
    roles = [m["role"] for m in agent.state.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    tool_msg = agent.state.messages[3]
    assert tool_msg["role"] == "tool"
    assert "San Francisco: 65F, Sunny" in tool_msg["content"]


def test_agent_iteration_limit(mock_config):
    """Verify agent loop breaks if tool calls exceed max_iterations."""
    mock_config.max_iterations = 2
    mock_gateway = MagicMock()

    infinite_tool_response = LLMResponse(
        content="",
        model="mock/mock-model",
        tool_calls=[
            ToolCall(
                id="call_loop",
                name="dummy_tool",
                arguments={},
            )
        ],
    )
    mock_gateway.complete.return_value = infinite_tool_response

    agent = ConversationalAgent(config=mock_config, llm_gateway=mock_gateway)
    agent.register_tool(
        name="dummy_tool",
        description="Dummy tool",
        parameters={"type": "object", "properties": {}},
        func=lambda: "dummy result",
    )

    response = agent.step("Loop please")
    assert "maximum reasoning steps" in response
    assert agent.state.iteration_count == 2


def test_agent_streaming(mock_config):
    """Verify step_stream yields chunks and updates message state."""
    mock_gateway = MagicMock()
    mock_gateway.complete_stream.return_value = iter(["Hello", " ", "there", "!"])

    agent = ConversationalAgent(config=mock_config, llm_gateway=mock_gateway)
    tokens = list(agent.step_stream("Greeting"))

    assert "".join(tokens) == "Hello there!"
    last_msg = agent.state.messages[-1]
    assert last_msg["role"] == "assistant"
    assert last_msg["content"] == "Hello there!"

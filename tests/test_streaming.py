"""
Tests for streaming event orchestration, async step execution, and search caching optimization.
"""

import asyncio
from unittest.mock import MagicMock
import pytest

from minimi.agent import (
    CitationEvent,
    ConversationalAgent,
    TokenDeltaEvent,
    ToolEndEvent,
    ToolStartEvent,
    TurnCompleteEvent,
)
from minimi.llm import LLMResponse, ToolCall
from minimi.search import Citation, SearchResponse, WebSearchEngine
from minimi.tools import register_default_tools


def test_search_cache_optimization():
    """Verify WebSearchEngine caches identical queries to avoid duplicate network latency."""
    engine = WebSearchEngine(api_key="mock-key")

    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {"title": "Fast Search", "url": "https://speed.org", "content": "Latency benchmark."}
        ]
    }
    engine.search = MagicMock(wraps=engine.search)  # spy

    # First call
    res1 = engine.search("fast computing", max_results=3)
    assert res1.has_results
    assert len(engine._cache) == 1

    # Second call for same query & max_results should hit cache
    res2 = engine.search("fast computing", max_results=3)
    assert res2 == res1

    # Clear cache
    engine.clear_cache()
    assert len(engine._cache) == 0


def test_streaming_events_no_tools(mock_config):
    """Verify event emission sequence for standard non-tool conversational turns."""
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = LLMResponse(
        content="Streaming greeting response.",
        model="mock/mock-model",
        tool_calls=[],
    )

    agent = ConversationalAgent(
        config=mock_config,
        llm_gateway=mock_gateway,
        auto_register_tools=False,
    )

    events = list(agent.step_stream_events("Hello!"))
    types = [type(e) for e in events]

    assert TokenDeltaEvent in types
    assert TurnCompleteEvent in types
    last_event = events[-1]
    assert isinstance(last_event, TurnCompleteEvent)
    assert last_event.response == "Streaming greeting response."


def test_streaming_events_with_tools(mock_config):
    """Verify tool start, tool end, token delta, and citation events during tool orchestration."""
    mock_gateway = MagicMock()

    # Step 1: LLM triggers tool
    step1 = LLMResponse(
        content="",
        model="mock/mock-model",
        tool_calls=[
            ToolCall(
                id="call_web_1",
                name="web_search",
                arguments={"query": "Mars sample return"},
            )
        ],
    )
    # Step 2: LLM generates final answer citing [^1]
    step2 = LLMResponse(
        content="NASA is developing Mars Sample Return [^1].",
        model="mock/mock-model",
        tool_calls=[],
    )
    mock_gateway.complete.side_effect = [step1, step2]

    agent = ConversationalAgent(
        config=mock_config,
        llm_gateway=mock_gateway,
        auto_register_tools=False,
    )

    mock_search = MagicMock(spec=WebSearchEngine)
    mock_search.api_key = "mock-key"
    mock_search.search.return_value = SearchResponse(
        query="Mars sample return",
        citations=[
            Citation(
                index=1,
                title="MSR Mission",
                url="https://nasa.gov/msr",
                snippet="Sample tubes stored on Mars.",
            )
        ],
    )
    register_default_tools(agent, search_engine=mock_search)

    events = list(agent.step_stream_events("What is the Mars sample return plan?"))

    tool_start_events = [e for e in events if isinstance(e, ToolStartEvent)]
    tool_end_events = [e for e in events if isinstance(e, ToolEndEvent)]
    token_events = [e for e in events if isinstance(e, TokenDeltaEvent)]
    citation_events = [e for e in events if isinstance(e, CitationEvent)]
    complete_events = [e for e in events if isinstance(e, TurnCompleteEvent)]

    assert len(tool_start_events) == 1
    assert tool_start_events[0].tool_name == "web_search"

    assert len(tool_end_events) == 1
    assert "MSR Mission" in tool_end_events[0].output

    assert len(token_events) == 1
    assert "Mars Sample Return [^1]" in token_events[0].delta

    assert len(citation_events) == 1
    assert "**Sources:**" in citation_events[0].sources_footer

    assert len(complete_events) == 1
    assert "https://nasa.gov/msr" in complete_events[0].response


@pytest.mark.asyncio
async def test_step_async_execution(mock_config):
    """Verify asynchronous turn execution via step_async."""
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = LLMResponse(
        content="Async turn finished successfully.",
        model="mock/mock-model",
        tool_calls=[],
    )

    agent = ConversationalAgent(
        config=mock_config,
        llm_gateway=mock_gateway,
        auto_register_tools=False,
    )

    response = await agent.step_async("Run asynchronously")
    assert response == "Async turn finished successfully."

"""
Tests for WebSearchEngine, source attribution citations, and agent search integration.
"""

from unittest.mock import MagicMock, patch
import pytest

from minimi.agent import ConversationalAgent
from minimi.llm import LLMResponse, ToolCall
from minimi.search import Citation, SearchResponse, WebSearchEngine
from minimi.tools import WEB_SEARCH_SCHEMA, create_web_search_handler, register_default_tools


def test_citation_formatting():
    """Verify Citation anchor and markdown line generation."""
    cit = Citation(
        index=1,
        title="Python Documentation",
        url="https://docs.python.org/3/",
        snippet="Official documentation for Python 3.",
        score=0.95,
    )
    assert cit.to_anchor() == "[^1]"
    assert cit.to_citation_line() == "[^1]: [Python Documentation](https://docs.python.org/3/)"


def test_search_response_formatting():
    """Verify SearchResponse properly structures snippets and citation anchors."""
    cit1 = Citation(
        index=1,
        title="Doc 1",
        url="https://example.com/1",
        snippet="Snippet text 1",
    )
    cit2 = Citation(
        index=2,
        title="Doc 2",
        url="https://example.com/2",
        snippet="Snippet text 2",
    )
    res = SearchResponse(query="test query", citations=[cit1, cit2])
    formatted = res.format_for_agent()

    assert "Search Results for 'test query':" in formatted
    assert "[^1] Title: Doc 1" in formatted
    assert "https://example.com/1" in formatted
    assert "[^2] Title: Doc 2" in formatted
    assert "[^1]: [Doc 1](https://example.com/1)" in formatted
    assert "[^2]: [Doc 2](https://example.com/2)" in formatted


def test_search_engine_missing_api_key(monkeypatch):
    """Verify search engine returns empty results gracefully when TVLY_API_KEY is missing."""
    monkeypatch.delenv("TVLY_API_KEY", raising=False)
    engine = WebSearchEngine(api_key=None)
    response = engine.search("quantum computing")
    assert not response.has_results
    assert len(response.citations) == 0


def test_search_engine_with_mock_tavily(monkeypatch):
    """Verify URL deduplication and structured citation creation with mock TavilyClient."""
    mock_results = {
        "results": [
            {
                "title": "Quantum Supremacy",
                "url": "https://nature.com/articles/quantum-1",
                "content": "Overview of quantum processors.",
                "score": 0.98,
            },
            {
                "title": "Duplicate URL result",
                "url": "https://nature.com/articles/quantum-1/",  # Same URL with trailing slash
                "content": "Duplicate content.",
                "score": 0.90,
            },
            {
                "title": "Quantum Algorithms",
                "url": "https://arxiv.org/abs/2026.01234",
                "content": "Novel algorithms for fault-tolerant systems.",
                "score": 0.85,
            },
        ]
    }

    mock_client_instance = MagicMock()
    mock_client_instance.search.return_value = mock_results

    monkeypatch.setattr("minimi.search.TavilyClient", lambda api_key: mock_client_instance)
    monkeypatch.setattr("minimi.search.TAVILY_AVAILABLE", True)

    engine = WebSearchEngine(api_key="mock-key")
    response = engine.search("quantum computing", max_results=5)

    assert response.has_results
    # Verify deduplication (duplicate URL was filtered out)
    assert len(response.citations) == 2
    assert response.citations[0].index == 1
    assert response.citations[0].title == "Quantum Supremacy"
    assert response.citations[1].index == 2
    assert response.citations[1].title == "Quantum Algorithms"
    assert response.citations[1].url == "https://arxiv.org/abs/2026.01234"


def test_web_search_tool_handler():
    """Verify tool handler executes search and formats string for agent."""
    mock_engine = MagicMock(spec=WebSearchEngine)
    mock_engine.api_key = "mock-key"
    mock_engine.search.return_value = SearchResponse(
        query="langgraph",
        citations=[
            Citation(
                index=1,
                title="LangGraph Docs",
                url="https://langchain-ai.github.io/langgraph/",
                snippet="Build resilient multi-agent graphs.",
            )
        ],
    )

    handler = create_web_search_handler(mock_engine)
    result = handler(query="langgraph")

    assert "[^1] Title: LangGraph Docs" in result
    assert "https://langchain-ai.github.io/langgraph/" in result
    assert "Build resilient multi-agent graphs." in result


def test_agent_with_web_search_dispatch(mock_config):
    """End-to-end test verifying agent calls web_search and synthesizes grounded answer."""
    mock_gateway = MagicMock()

    # Step 1: Agent decides to call web_search
    step1_response = LLMResponse(
        content="",
        model="mock/mock-model",
        tool_calls=[
            ToolCall(
                id="call_search_1",
                name="web_search",
                arguments={"query": "latest Mars rover discovery"},
            )
        ],
    )

    # Step 2: Agent synthesizes final answer with citation
    step2_response = LLMResponse(
        content="The Perseverance rover recently discovered organic molecules in Jezero Crater [^1].",
        model="mock/mock-model",
        tool_calls=[],
    )
    mock_gateway.complete.side_effect = [step1_response, step2_response]

    agent = ConversationalAgent(
        config=mock_config,
        llm_gateway=mock_gateway,
        auto_register_tools=False,
    )

    # Custom mock search engine
    mock_engine = MagicMock(spec=WebSearchEngine)
    mock_engine.api_key = "mock-key"
    mock_engine.search.return_value = SearchResponse(
        query="latest Mars rover discovery",
        citations=[
            Citation(
                index=1,
                title="NASA Mars Mission Update",
                url="https://mars.nasa.gov/news/perseverance",
                snippet="Perseverance rover detected carbon-rich compounds in Jezero crater samples.",
            )
        ],
    )
    register_default_tools(agent, search_engine=mock_engine)

    assert "web_search" in agent.tools

    response = agent.step("What did the Mars rover discover recently?")
    assert "[^1]" in response
    assert "Perseverance" in response

    # Check conversation trace
    roles = [m["role"] for m in agent.state.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    tool_msg = agent.state.messages[3]
    assert tool_msg["role"] == "tool"
    assert tool_msg["name"] == "web_search"
    assert "NASA Mars Mission Update" in tool_msg["content"]

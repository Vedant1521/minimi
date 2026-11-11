"""
Tests for CrossSessionRecallEngine and multi-session historical question recall.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from minimi.agent import ConversationalAgent
from minimi.llm import LLMResponse
from minimi.recall import CrossSessionRecallEngine, HistoricalTurn
from minimi.storage import TemporalStorage


def test_recall_intent_detection():
    """Verify detection of user requests referencing past sessions or conversations."""
    assert CrossSessionRecallEngine.is_recall_query("What did I ask about Python in our previous conversation?")
    assert CrossSessionRecallEngine.is_recall_query("Did I mention anything about database indexing earlier?")
    assert CrossSessionRecallEngine.is_recall_query("Have we talked about transformers before?")
    assert CrossSessionRecallEngine.is_recall_query("What did I ask from our last chat?")
    assert CrossSessionRecallEngine.is_recall_query("Remember when I asked about Docker?")

    # Negative non-recall queries
    assert not CrossSessionRecallEngine.is_recall_query("What is the capital of Australia?")
    assert not CrossSessionRecallEngine.is_recall_query("Write a function to sort an array")
    assert not CrossSessionRecallEngine.is_recall_query("How does photosynthesis work?")


def test_keyword_extraction():
    """Verify stop-word filtering and keyword extraction."""
    kw = CrossSessionRecallEngine.extract_keywords("What did I ask about quantum entanglement in our previous chat?")
    assert "quantum" in kw
    assert "entanglement" in kw
    assert "what" not in kw
    assert "did" not in kw
    assert "previous" not in kw
    assert "chat" not in kw


def test_cross_session_search_and_ranking(tmp_path):
    """Verify cross-session searching pairs Q&A turns and ranks correctly."""
    db_file = tmp_path / "cross_session.duckdb"
    storage = TemporalStorage(db_file)
    engine = CrossSessionRecallEngine(storage)

    now = datetime(2026, 11, 11, 20, 0, 0, tzinfo=timezone.utc)

    # Session 1 (2 days ago)
    conv1 = storage.create_conversation(title="Asyncio Deep Dive", conversation_id="conv-1")
    t1 = now - timedelta(days=2)
    storage.add_message(
        conversation_id=conv1.id,
        role="user",
        content="How does asyncio event loop schedule coroutines?",
        timestamp=t1,
    )
    storage.add_message(
        conversation_id=conv1.id,
        role="assistant",
        content="Asyncio uses cooperative multitasking and tasks.",
        timestamp=t1 + timedelta(seconds=2),
    )

    # Session 2 (5 days ago)
    conv2 = storage.create_conversation(title="Database Systems", conversation_id="conv-2")
    t2 = now - timedelta(days=5)
    storage.add_message(
        conversation_id=conv2.id,
        role="user",
        content="What are the trade-offs of using DuckDB over SQLite?",
        timestamp=t2,
    )
    storage.add_message(
        conversation_id=conv2.id,
        role="assistant",
        content="DuckDB is optimized for analytical OLAP workloads.",
        timestamp=t2 + timedelta(seconds=2),
    )

    # Search for asyncio question
    results1 = engine.search_historical_questions(
        query="What did I ask about asyncio scheduling earlier?",
        reference_time=now,
    )
    assert len(results1) >= 1
    top1 = results1[0]
    assert top1.conversation_id == "conv-1"
    assert "asyncio event loop" in top1.user_message
    assert "cooperative multitasking" in top1.assistant_message
    assert top1.conversation_title == "Asyncio Deep Dive"

    # Search for DuckDB question
    results2 = engine.search_historical_questions(
        query="Did I ask about DuckDB vs SQLite in a previous session?",
        reference_time=now,
    )
    assert len(results2) >= 1
    top2 = results2[0]
    assert top2.conversation_id == "conv-2"
    assert "DuckDB over SQLite" in top2.user_message
    assert "analytical OLAP" in top2.assistant_message


def test_format_historical_context(tmp_path):
    """Verify XML context block formatting for prompt injection."""
    engine = CrossSessionRecallEngine(TemporalStorage(tmp_path / "fmt.duckdb"))
    ts = datetime(2026, 11, 10, 14, 0, 0, tzinfo=timezone.utc)

    turn = HistoricalTurn(
        conversation_id="c1",
        conversation_title="AI Research",
        user_message="What is RLHF?",
        assistant_message="Reinforcement Learning from Human Feedback.",
        timestamp=ts,
        score=0.92,
    )

    block = engine.format_historical_context([turn])
    assert block is not None
    assert "<historical_cross_session_context>" in block
    assert "AI Research" in block
    assert "What is RLHF?" in block
    assert "Reinforcement Learning from Human Feedback." in block
    assert "</historical_cross_session_context>" in block


def test_agent_cross_session_injection(mock_config, tmp_path):
    """Verify agent injects cross-session Q&A context when user references past chat."""
    db_file = tmp_path / "agent_cross_session.duckdb"
    storage = TemporalStorage(db_file)

    now = datetime(2026, 11, 11, 20, 0, 0, tzinfo=timezone.utc)

    # Prior session with historical knowledge
    old_session = "session-past-101"
    storage.create_conversation(title="Rust Architecture", conversation_id=old_session)
    storage.add_message(
        conversation_id=old_session,
        role="user",
        content="What is the difference between Box and Arc in Rust?",
        timestamp=now - timedelta(days=1),
    )
    storage.add_message(
        conversation_id=old_session,
        role="assistant",
        content="Box is single-threaded heap allocation; Arc is atomic reference counting for multi-threaded sharing.",
        timestamp=now - timedelta(days=1) + timedelta(seconds=2),
    )

    # New active session
    current_session = "session-active-202"
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = LLMResponse(
        content="In our previous conversation, you asked about the difference between Box and Arc in Rust.",
        model="mock/mock-model",
        tool_calls=[],
    )

    agent = ConversationalAgent(
        config=mock_config,
        session_id=current_session,
        llm_gateway=mock_gateway,
        storage=storage,
        auto_register_tools=False,
    )

    response = agent.step("In our previous conversation, what did I ask about Rust pointers?")
    assert "Box and Arc" in response

    # Verify context injection into messages passed to LLM
    call_args = mock_gateway.complete.call_args[1]
    passed_msgs = call_args["messages"]
    hist_msgs = [
        m for m in passed_msgs
        if m.get("role") == "system" and "<historical_cross_session_context>" in m.get("content", "")
    ]
    assert len(hist_msgs) == 1
    assert "What is the difference between Box and Arc in Rust?" in hist_msgs[0]["content"]


def test_agent_recall_tool_dispatch(mock_config, tmp_path):
    """Verify the recall_historical_conversations tool can be invoked explicitly."""
    db_file = tmp_path / "tool_cross_session.duckdb"
    storage = TemporalStorage(db_file)

    storage.create_conversation(title="Docker Setup", conversation_id="conv-docker")
    storage.add_message(
        conversation_id="conv-docker",
        role="user",
        content="How do I write a multi-stage Dockerfile?",
    )
    storage.add_message(
        conversation_id="conv-docker",
        role="assistant",
        content="Use multiple FROM statements to separate build and runtime environments.",
    )

    agent = ConversationalAgent(
        config=mock_config,
        session_id="conv-new",
        storage=storage,
        auto_register_tools=False,
    )

    assert "recall_historical_conversations" in agent.tools
    result = agent.execute_tool("recall_historical_conversations", {"query": "multi-stage Dockerfile"})
    assert "How do I write a multi-stage Dockerfile?" in result
    assert "Docker Setup" in result

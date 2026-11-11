"""
Tests for temporal parsing, time windows, and chronological memory retrieval.
"""

from datetime import datetime, time, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from minimi.agent import ConversationalAgent
from minimi.llm import LLMResponse
from minimi.storage import TemporalStorage
from minimi.temporal import (
    ChronologicalMemoryRetriever,
    TemporalParser,
    TimeWindow,
)


def test_temporal_parser_units():
    """Verify relative units parsing (hours, minutes, days, weeks)."""
    ref_time = datetime(2026, 11, 11, 15, 30, 0, tzinfo=timezone.utc)

    # Past 3 hours
    w_hours = TemporalParser.parse("What did we discuss in the past 3 hours?", reference_time=ref_time)
    assert w_hours is not None
    assert w_hours.label == "past 3 hours"
    assert w_hours.end_time == ref_time
    assert w_hours.start_time == ref_time - timedelta(hours=3)

    # Last 45 minutes
    w_mins = TemporalParser.parse("Summary of our chat over the last 45 minutes", reference_time=ref_time)
    assert w_mins is not None
    assert w_mins.start_time == ref_time - timedelta(minutes=45)

    # Past 2 days
    w_days = TemporalParser.parse("What did I ask during the past 2 days?", reference_time=ref_time)
    assert w_days is not None
    assert w_days.start_time == ref_time - timedelta(days=2)

    # Past week
    w_week = TemporalParser.parse("Show me our discussions from last week", reference_time=ref_time)
    assert w_week is not None
    assert w_week.start_time == ref_time - timedelta(days=7)


def test_temporal_parser_yesterday_today():
    """Verify yesterday and today boundary calculations."""
    ref_time = datetime(2026, 11, 11, 18, 0, 0, tzinfo=timezone.utc)

    # Today
    w_today = TemporalParser.parse("Can you list all questions from today?", reference_time=ref_time)
    assert w_today is not None
    assert w_today.start_time == datetime(2026, 11, 11, 0, 0, 0, tzinfo=timezone.utc)
    assert w_today.end_time == ref_time

    # Earlier today
    w_earlier = TemporalParser.parse("What was the Python code we discussed earlier today?", reference_time=ref_time)
    assert w_earlier is not None
    assert w_earlier.start_time == datetime(2026, 11, 11, 0, 0, 0, tzinfo=timezone.utc)

    # Yesterday
    w_yest = TemporalParser.parse("What did we talk about yesterday?", reference_time=ref_time)
    assert w_yest is not None
    assert w_yest.start_time == datetime(2026, 11, 10, 0, 0, 0, tzinfo=timezone.utc)
    assert w_yest.end_time.date() == datetime(2026, 11, 10).date()


def test_temporal_parser_non_temporal():
    """Verify non-temporal queries return None."""
    assert TemporalParser.parse("What is the capital of Japan?") is None
    assert TemporalParser.parse("Calculate the square root of 256") is None
    assert TemporalParser.parse("Explain quantum computing") is None


def test_time_window_contains():
    """Verify TimeWindow.contains boundary checks."""
    start = datetime(2026, 11, 11, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
    window = TimeWindow(start_time=start, end_time=end, label="test window")

    assert window.contains(datetime(2026, 11, 11, 11, 0, 0, tzinfo=timezone.utc))
    assert window.contains(start)
    assert window.contains(end)
    assert not window.contains(datetime(2026, 11, 11, 9, 59, 59, tzinfo=timezone.utc))
    assert not window.contains(datetime(2026, 11, 11, 12, 0, 1, tzinfo=timezone.utc))


def test_chronological_memory_retriever(tmp_path):
    """Verify retriever extracts and formats chronological transcripts."""
    db_file = tmp_path / "chrono.duckdb"
    storage = TemporalStorage(db_file)
    retriever = ChronologicalMemoryRetriever(storage)

    conv = storage.create_conversation(title="Temporal Chat")
    ref_time = datetime(2026, 11, 11, 16, 0, 0, tzinfo=timezone.utc)

    # Turn 1: 2 hours ago
    storage.add_message(
        conversation_id=conv.id,
        role="user",
        content="What is DuckDB?",
        timestamp=ref_time - timedelta(hours=2),
    )
    storage.add_message(
        conversation_id=conv.id,
        role="assistant",
        content="DuckDB is an in-process SQL OLAP database.",
        timestamp=ref_time - timedelta(hours=2) + timedelta(seconds=5),
    )

    # Turn 2: 30 minutes ago
    storage.add_message(
        conversation_id=conv.id,
        role="user",
        content="Does it support full-text search?",
        timestamp=ref_time - timedelta(minutes=30),
    )

    # Query for "in the past 3 hours"
    window, formatted = retriever.retrieve_context(
        "What did we discuss in the past 3 hours?",
        conversation_id=conv.id,
        reference_time=ref_time,
    )
    assert window is not None
    assert formatted is not None
    assert "Chronological Context for [past 3 hours]" in formatted
    assert "What is DuckDB?" in formatted
    assert "DuckDB is an in-process SQL OLAP database." in formatted
    assert "Does it support full-text search?" in formatted


def test_agent_temporal_memory_injection(mock_config, tmp_path):
    """Verify agent auto-injects chronological memory when a temporal question is asked."""
    db_file = tmp_path / "agent_temporal.duckdb"
    storage = TemporalStorage(db_file)

    session_id = "chrono-session-1"
    now = datetime(2026, 11, 11, 17, 0, 0, tzinfo=timezone.utc)

    # Populate historical turn from 1 hour ago
    storage.add_message(
        conversation_id=session_id,
        role="user",
        content="I prefer dark mode in UI applications.",
        timestamp=now - timedelta(hours=1),
    )
    storage.add_message(
        conversation_id=session_id,
        role="assistant",
        content="Understood, I will remember you prefer dark mode.",
        timestamp=now - timedelta(hours=1) + timedelta(seconds=3),
    )

    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = LLMResponse(
        content="Earlier you mentioned that you prefer dark mode.",
        model="mock/mock-model",
        tool_calls=[],
    )

    agent = ConversationalAgent(
        config=mock_config,
        session_id=session_id,
        llm_gateway=mock_gateway,
        storage=storage,
        auto_register_tools=False,
    )

    response = agent.step("What preference did I mention earlier today?")
    assert "dark mode" in response

    # Verify that chronological memory was injected into message context passed to LLM
    call_args = mock_gateway.complete.call_args[1]
    passed_messages = call_args["messages"]
    system_mem_msgs = [
        m for m in passed_messages
        if m.get("role") == "system" and "<chronological_memory>" in m.get("content", "")
    ]
    assert len(system_mem_msgs) >= 1
    assert "I prefer dark mode in UI applications." in system_mem_msgs[0]["content"]


def test_agent_retrieve_chronological_tool(mock_config, tmp_path):
    """Verify the retrieve_chronological_memory tool can be invoked directly."""
    db_file = tmp_path / "tool_temporal.duckdb"
    storage = TemporalStorage(db_file)
    session_id = "chrono-tool-session"

    now = datetime.now(timezone.utc)
    storage.add_message(
        conversation_id=session_id,
        role="user",
        content="My favorite language is Python.",
        timestamp=now - timedelta(hours=2),
    )

    agent = ConversationalAgent(
        config=mock_config,
        session_id=session_id,
        storage=storage,
        auto_register_tools=False,
    )

    assert "retrieve_chronological_memory" in agent.tools
    result = agent.execute_tool("retrieve_chronological_memory", {"time_phrase": "past 3 hours"})
    assert "My favorite language is Python." in result

"""
Tests for TemporalStorage DuckDB persistence and timestamp fidelity.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from minimi.agent import ConversationalAgent
from minimi.llm import LLMResponse
from minimi.storage import StoredConversation, StoredMessage, TemporalStorage


def test_storage_init_and_tables(tmp_path):
    """Verify DuckDB schema and indices initialize cleanly."""
    db_file = tmp_path / "test_init.duckdb"
    storage = TemporalStorage(db_file)

    # Inspect tables using DuckDB connection
    with storage._connection() as conn:
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        assert "conversations" in table_names
        assert "messages" in table_names


def test_conversation_crud(tmp_path):
    """Verify creating, fetching, and listing conversations."""
    db_file = tmp_path / "test_conv.duckdb"
    storage = TemporalStorage(db_file)

    conv = storage.create_conversation(title="Test Chat", model="mock/model")
    assert conv.id is not None
    assert conv.title == "Test Chat"
    assert conv.model == "mock/model"
    assert conv.created_at.tzinfo is not None

    fetched = storage.get_conversation(conv.id)
    assert fetched is not None
    assert fetched.id == conv.id
    assert fetched.title == "Test Chat"

    all_convs = storage.list_conversations()
    assert len(all_convs) == 1
    assert all_convs[0].id == conv.id


def test_timestamp_microsecond_fidelity(tmp_path):
    """Verify microsecond UTC timestamp precision is preserved exactly."""
    db_file = tmp_path / "test_ts.duckdb"
    storage = TemporalStorage(db_file)
    conv = storage.create_conversation(title="Time Chat")

    # Explicit timestamp with microsecond component
    target_ts = datetime(2026, 11, 11, 23, 15, 30, 123456, tzinfo=timezone.utc)
    msg = storage.add_message(
        conversation_id=conv.id,
        role="user",
        content="Testing timestamp precision",
        timestamp=target_ts,
    )

    messages = storage.get_messages(conv.id)
    assert len(messages) == 1
    persisted = messages[0]
    assert persisted.timestamp == target_ts
    assert persisted.timestamp.microsecond == 123456
    assert persisted.timestamp.tzinfo == timezone.utc


def test_message_structured_fields(tmp_path):
    """Verify tool_calls, citations, and metadata JSON serialization/deserialization."""
    db_file = tmp_path / "test_json.duckdb"
    storage = TemporalStorage(db_file)
    conv = storage.create_conversation(title="Structured Chat")

    tool_calls = [{"id": "call_abc", "function": {"name": "search", "arguments": "{}"}}]
    citations = [{"index": 1, "title": "Example", "url": "https://example.com"}]
    meta = {"tokens": 150, "latency_ms": 45}

    storage.add_message(
        conversation_id=conv.id,
        role="assistant",
        content="Structured response",
        tool_calls=tool_calls,
        citations=citations,
        metadata=meta,
    )

    messages = storage.get_messages(conv.id)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.tool_calls == tool_calls
    assert msg.citations == citations
    assert msg.metadata == meta


def test_time_range_queries(tmp_path):
    """Verify temporal range filtering across multiple messages."""
    db_file = tmp_path / "test_range.duckdb"
    storage = TemporalStorage(db_file)
    conv = storage.create_conversation(title="Range Chat")

    base_time = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)

    # Message 1 at 12:00
    storage.add_message(
        conversation_id=conv.id,
        role="user",
        content="Question 1",
        timestamp=base_time,
    )
    # Message 2 at 12:30
    storage.add_message(
        conversation_id=conv.id,
        role="assistant",
        content="Answer 1",
        timestamp=base_time + timedelta(minutes=30),
    )
    # Message 3 at 14:00
    storage.add_message(
        conversation_id=conv.id,
        role="user",
        content="Question 2",
        timestamp=base_time + timedelta(hours=2),
    )

    # Query between 11:59 and 12:45 (should match msg 1 and 2, but not 3)
    slice_msgs = storage.get_messages_in_time_range(
        start_time=base_time - timedelta(minutes=1),
        end_time=base_time + timedelta(minutes=45),
    )
    assert len(slice_msgs) == 2
    assert slice_msgs[0].content == "Question 1"
    assert slice_msgs[1].content == "Answer 1"

    # Query specifically for role='user'
    user_slice = storage.get_messages_in_time_range(
        start_time=base_time - timedelta(minutes=1),
        end_time=base_time + timedelta(hours=3),
        role="user",
    )
    assert len(user_slice) == 2
    assert [m.content for m in user_slice] == ["Question 1", "Question 2"]


def test_agent_storage_integration(mock_config, tmp_path):
    """Verify agent persists turns and reloads history when resuming session."""
    db_path = tmp_path / "agent_test.duckdb"
    storage = TemporalStorage(db_path)

    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = LLMResponse(
        content="Persistent answer",
        model="mock/mock-model",
        tool_calls=[],
    )

    session_id = "test-session-123"
    agent = ConversationalAgent(
        config=mock_config,
        session_id=session_id,
        llm_gateway=mock_gateway,
        storage=storage,
        auto_register_tools=False,
    )

    response = agent.step("What is the meaning of life?")
    assert response == "Persistent answer"

    # Check persistence
    stored_msgs = storage.get_messages(session_id)
    assert len(stored_msgs) == 2
    assert stored_msgs[0].role == "user"
    assert stored_msgs[0].content == "What is the meaning of life?"
    assert stored_msgs[1].role == "assistant"
    assert stored_msgs[1].content == "Persistent answer"

    # Resume session in new agent instance
    resumed_agent = ConversationalAgent(
        config=mock_config,
        session_id=session_id,
        llm_gateway=mock_gateway,
        storage=storage,
        auto_register_tools=False,
    )

    # Messages in resumed agent should include system + loaded prior turns
    assert len(resumed_agent.state.messages) >= 3
    assert resumed_agent.state.messages[1]["role"] == "user"
    assert resumed_agent.state.messages[1]["content"] == "What is the meaning of life?"

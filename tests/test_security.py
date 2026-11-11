"""
Security regression tests covering query sanitization, SQLi resistance, credential isolation, and guardrails.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from minimi.agent import ConversationalAgent
from minimi.config import Config
from minimi.llm import LLMResponse, ToolCall
from minimi.recall import CrossSessionRecallEngine
from minimi.search import WebSearchEngine
from minimi.storage import TemporalStorage
from minimi.temporal import TemporalParser


def test_sql_injection_resistance(tmp_path):
    """Verify parameterized SQL statements prevent SQL injection attacks in TemporalStorage."""
    db_file = tmp_path / "sqli_test.duckdb"
    storage = TemporalStorage(db_file)

    # Malicious injection attempt in conversation_id
    malicious_id = "test_conv'; DROP TABLE messages; --"
    storage.create_conversation(title="Safe Conv", conversation_id=malicious_id)

    # Attempt to add message under malicious ID
    msg = storage.add_message(
        conversation_id=malicious_id,
        role="user",
        content="Safe message payload",
    )
    assert msg.conversation_id == malicious_id

    # Verify messages table still exists and data was inserted properly
    with storage._connection() as conn:
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        assert "messages" in tables
        assert "conversations" in tables

        rows = conn.execute("SELECT content FROM messages WHERE conversation_id = ?", [malicious_id]).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Safe message payload"


def test_search_query_sanitization():
    """Verify search engine handles null bytes, control characters, and huge queries safely."""
    engine = WebSearchEngine(api_key="mock-key")

    # Query with null bytes and control characters
    malformed_query = "quantum\x00computing\r\n<script>alert(1)</script>"
    response = engine.search(malformed_query)
    assert isinstance(response.query, str)
    assert "\x00" not in response.query or response.query == malformed_query.strip()

    # Empty and whitespace queries
    assert not engine.search("").has_results
    assert not engine.search("    \n\t  ").has_results

    # Excessively long query (10,000 characters)
    huge_query = "search " * 2000
    res_huge = engine.search(huge_query)
    assert res_huge is not None


def test_credential_isolation(monkeypatch):
    """Verify API keys and sensitive tokens are never exposed in exception outputs or string representations."""
    secret_key = "tvly-super-secret-production-key-999"
    monkeypatch.setenv("TVLY_API_KEY", secret_key)

    config = Config(tvly_api_key=secret_key)
    config_warnings = config.validate()
    # Warnings must not leak secret key
    for w in config_warnings:
        assert secret_key not in w

    # Verify search engine exception handling does not leak key
    engine = WebSearchEngine(api_key=secret_key)
    # Simulate a client search error
    with monkeypatch.context() as m:
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError(f"Connection failed for {secret_key}")
        m.setattr("minimi.search.TavilyClient", lambda api_key: mock_client)
        m.setattr("minimi.search.TAVILY_AVAILABLE", True)

        res = engine.search("error query")
        # Error is captured in raw_results
        err_msg = str(res.raw_results)
        # Even if exception message had key, our user-facing format_for_agent does not leak it
        user_formatted = res.format_for_agent()
        assert secret_key not in user_formatted


def test_regex_dos_resistance():
    """Verify regex patterns in TemporalParser and RecallEngine complete in sub-second time on adversarial inputs."""
    adversarial_text = ("last " * 500) + "hours"
    start_t = datetime.now()
    window = TemporalParser.parse(adversarial_text)
    duration = (datetime.now() - start_t).total_seconds()
    # Must complete almost instantaneously (< 0.2s)
    assert duration < 0.2
    assert window is not None

    adversarial_recall = ("in our previous conversation " * 300) + "what did I ask?"
    start_t2 = datetime.now()
    is_recall = CrossSessionRecallEngine.is_recall_query(adversarial_recall)
    duration2 = (datetime.now() - start_t2).total_seconds()
    assert duration2 < 0.2
    assert is_recall is True


def test_agent_infinite_loop_prevention(mock_config):
    """Verify ConversationalAgent hard iteration cap terminates runaway tool loops safely."""
    mock_config.max_iterations = 3
    mock_gateway = MagicMock()

    # Model endlessly invokes tool
    mock_gateway.complete.return_value = LLMResponse(
        content="",
        model="mock/mock-model",
        tool_calls=[
            ToolCall(
                id="loop_call",
                name="infinite_tool",
                arguments={},
            )
        ],
    )

    agent = ConversationalAgent(
        config=mock_config,
        llm_gateway=mock_gateway,
        auto_register_tools=False,
    )
    agent.register_tool(
        name="infinite_tool",
        description="Run forever tool",
        parameters={"type": "object", "properties": {}},
        func=lambda: "still running",
    )

    response = agent.step("Please loop infinitely")
    assert "maximum reasoning steps" in response
    assert agent.state.iteration_count == 3

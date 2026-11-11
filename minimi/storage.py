"""
DuckDB-backed temporal conversation and timestamped message persistence store.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Generator, List, Optional
import uuid

import duckdb


@dataclass
class StoredMessage:
    """A persisted conversational message with timestamp and structured metadata."""
    id: str
    conversation_id: str
    role: str
    content: str
    timestamp: datetime
    tool_calls: Optional[list[dict[str, Any]]] = None
    citations: Optional[list[dict[str, Any]]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary representation."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": self.tool_calls,
            "citations": self.citations,
            "metadata": self.metadata,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "StoredMessage":
        """Reconstruct message from database tuple row."""
        (
            msg_id,
            conv_id,
            role,
            content,
            ts,
            tool_calls_json,
            citations_json,
            meta_json,
        ) = row

        # Parse timestamp safely ensuring timezone awareness
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts)
        elif isinstance(ts, datetime):
            dt = ts
        else:
            dt = datetime.now(timezone.utc)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        tool_calls = json.loads(tool_calls_json) if tool_calls_json else None
        citations = json.loads(citations_json) if citations_json else None
        metadata = json.loads(meta_json) if meta_json else {}

        return cls(
            id=str(msg_id),
            conversation_id=str(conv_id),
            role=str(role),
            content=str(content),
            timestamp=dt,
            tool_calls=tool_calls,
            citations=citations,
            metadata=metadata,
        )


@dataclass
class StoredConversation:
    """A persisted conversation with metadata and associated messages."""
    id: str
    title: str
    model: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    messages: list[StoredMessage] = field(default_factory=list)


class TemporalStorage:
    """Relational DuckDB storage managing timestamped conversations and chronological messages."""

    def __init__(self, db_path: Path | str = "minimi.duckdb"):
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:") and not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Context manager yielding an active DuckDB connection."""
        conn = duckdb.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database tables and performance indexes."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR PRIMARY KEY,
                    title VARCHAR NOT NULL,
                    model VARCHAR NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    metadata JSON
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id VARCHAR PRIMARY KEY,
                    conversation_id VARCHAR NOT NULL,
                    role VARCHAR NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    tool_calls JSON,
                    citations JSON,
                    metadata JSON,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
                ON messages(conversation_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
                ON messages(timestamp);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_role 
                ON messages(role);
            """)

    def create_conversation(
        self,
        title: str = "New Conversation",
        model: str = "default",
        conversation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> StoredConversation:
        """Create and persist a new conversation session."""
        conv_id = conversation_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        meta_json = json.dumps(metadata or {})

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, model, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [conv_id, title, model, now, now, meta_json],
            )

        return StoredConversation(
            id=conv_id,
            title=title,
            model=model,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

    def get_conversation(self, conversation_id: str) -> Optional[StoredConversation]:
        """Fetch conversation metadata and its messages."""
        with self._connection() as conn:
            res = conn.execute(
                """
                SELECT id, title, model, created_at, updated_at, metadata
                FROM conversations
                WHERE id = ?
                """,
                [conversation_id],
            ).fetchone()

            if not res:
                return None

            conv_id, title, model, created_at, updated_at, meta_json = res
            meta = json.loads(meta_json) if meta_json else {}

            if isinstance(created_at, datetime) and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)

            messages = self.get_messages(conversation_id)

            return StoredConversation(
                id=conv_id,
                title=title,
                model=model,
                created_at=created_at,
                updated_at=updated_at,
                metadata=meta,
                messages=messages,
            )

    def list_conversations(self, limit: int = 50) -> list[StoredConversation]:
        """List recent conversations ordered by updated_at descending."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, model, created_at, updated_at, metadata
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()

            result = []
            for conv_id, title, model, created_at, updated_at, meta_json in rows:
                meta = json.loads(meta_json) if meta_json else {}
                if isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)

                result.append(
                    StoredConversation(
                        id=conv_id,
                        title=title,
                        model=model,
                        created_at=created_at,
                        updated_at=updated_at,
                        metadata=meta,
                    )
                )
            return result

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        timestamp: Optional[datetime] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        citations: Optional[list[dict[str, Any]]] = None,
        metadata: Optional[dict[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> StoredMessage:
        """Persist a message with explicit microsecond UTC timestamp."""
        msg_id = message_id or str(uuid.uuid4())
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        tool_calls_json = json.dumps(tool_calls) if tool_calls else None
        citations_json = json.dumps(citations) if citations else None
        meta_json = json.dumps(metadata) if metadata else None

        with self._connection() as conn:
            # Ensure conversation exists; if not, create it
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", [conversation_id]
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO conversations (id, title, model, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [conversation_id, "New Chat", "default", ts, ts, "{}"],
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    [ts, conversation_id],
                )

            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, timestamp, tool_calls, citations, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    ts,
                    tool_calls_json,
                    citations_json,
                    meta_json,
                ],
            )

        return StoredMessage(
            id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=ts,
            tool_calls=tool_calls,
            citations=citations,
            metadata=metadata or {},
        )

    def get_messages(self, conversation_id: str) -> list[StoredMessage]:
        """Fetch all messages for a conversation ordered chronologically."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, role, content, timestamp, tool_calls, citations, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
                """,
                [conversation_id],
            ).fetchall()

            return [StoredMessage.from_row(row) for row in rows]

    def get_messages_in_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        conversation_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> list[StoredMessage]:
        """Fetch messages within an explicit timestamp range across sessions or within a single session."""
        query = """
            SELECT id, conversation_id, role, content, timestamp, tool_calls, citations, metadata
            FROM messages
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params: list[Any] = [start_time, end_time]

        if conversation_id:
            query += " AND conversation_id = ?"
            params.append(conversation_id)

        if role:
            query += " AND role = ?"
            params.append(role)

        query += " ORDER BY timestamp ASC"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [StoredMessage.from_row(row) for row in rows]

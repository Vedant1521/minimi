"""
Temporal expression parsing and chronological memory retrieval engine.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import re
from typing import Optional, Tuple

from minimi.storage import StoredMessage, TemporalStorage


@dataclass
class TimeWindow:
    """A bounded time interval for temporal queries."""
    start_time: datetime
    end_time: datetime
    label: str

    def contains(self, dt: datetime) -> bool:
        """Check if a timestamp falls within this time window."""
        target = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return self.start_time <= target <= self.end_time


class TemporalParser:
    """Parses natural language relative time expressions into exact UTC datetime ranges."""

    # Patterns for relative units: hours, minutes, days, weeks
    _REL_UNIT_PATTERN = re.compile(
        r"\b(?:in\s+the\s+|within\s+(?:the\s+)?|over\s+(?:the\s+)?|past\s+|last\s+)(\d+)\s*(hour|hr|minute|min|day|week)s?\b",
        re.IGNORECASE,
    )
    _HOURS_AGO_PATTERN = re.compile(r"\b(\d+)\s*(?:hour|hr)s?\s+ago\b", re.IGNORECASE)
    _DAYS_AGO_PATTERN = re.compile(r"\b(\d+)\s*days?\s+ago\b", re.IGNORECASE)

    @classmethod
    def parse(cls, text: str, reference_time: Optional[datetime] = None) -> Optional[TimeWindow]:
        """Parse temporal expression from query text relative to reference UTC timestamp."""
        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        clean = text.lower().strip()

        # Check for numeric relative units (e.g., "last 3 hours", "past 2 days")
        unit_match = cls._REL_UNIT_PATTERN.search(clean)
        if unit_match:
            qty = int(unit_match.group(1))
            unit = unit_match.group(2).lower()
            if unit in {"hour", "hr"}:
                start = now - timedelta(hours=qty)
                return TimeWindow(start_time=start, end_time=now, label=f"past {qty} hours")
            elif unit in {"minute", "min"}:
                start = now - timedelta(minutes=qty)
                return TimeWindow(start_time=start, end_time=now, label=f"past {qty} minutes")
            elif unit == "day":
                start = now - timedelta(days=qty)
                return TimeWindow(start_time=start, end_time=now, label=f"past {qty} days")
            elif unit == "week":
                start = now - timedelta(weeks=qty)
                return TimeWindow(start_time=start, end_time=now, label=f"past {qty} weeks")

        # Check for "N hours ago"
        hrs_ago_match = cls._HOURS_AGO_PATTERN.search(clean)
        if hrs_ago_match:
            qty = int(hrs_ago_match.group(1))
            start = now - timedelta(hours=qty + 1)
            end = now - timedelta(hours=max(0, qty - 1))
            return TimeWindow(start_time=start, end_time=end, label=f"{qty} hours ago")

        # Check for "N days ago"
        days_ago_match = cls._DAYS_AGO_PATTERN.search(clean)
        if days_ago_match:
            qty = int(days_ago_match.group(1))
            target_date = (now - timedelta(days=qty)).date()
            start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
            end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
            return TimeWindow(start_time=start, end_time=end, label=f"{qty} days ago")

        # Check for "earlier today"
        if "earlier today" in clean or "this morning" in clean or "this afternoon" in clean:
            start_of_day = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
            return TimeWindow(start_time=start_of_day, end_time=now, label="earlier today")

        # Check for "yesterday"
        if "yesterday" in clean:
            yesterday_date = now.date() - timedelta(days=1)
            start = datetime.combine(yesterday_date, time.min, tzinfo=timezone.utc)
            end = datetime.combine(yesterday_date, time.max, tzinfo=timezone.utc)
            return TimeWindow(start_time=start, end_time=end, label="yesterday")

        # Check for "today"
        if re.search(r"\btoday\b", clean):
            start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
            return TimeWindow(start_time=start, end_time=now, label="today")

        # Check for "past week" or "last week" or "this week"
        if re.search(r"\b(last week|past week|this week)\b", clean):
            start = now - timedelta(days=7)
            return TimeWindow(start_time=start, end_time=now, label="past week")

        # Check for general "earlier" / "recently" / "previously"
        if re.search(r"\b(earlier|recently|previous turn|previous message)\b", clean):
            start = now - timedelta(hours=24)
            return TimeWindow(start_time=start, end_time=now, label="recently (past 24h)")

        return None


class ChronologicalMemoryRetriever:
    """Retrieves and formats chronological message history within specified temporal windows."""

    def __init__(self, storage: TemporalStorage):
        self.storage = storage

    def retrieve_context(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        reference_time: Optional[datetime] = None,
        max_messages: int = 15,
    ) -> Tuple[Optional[TimeWindow], Optional[str]]:
        """Identify time expressions and fetch chronological messages from storage."""
        window = TemporalParser.parse(query, reference_time=reference_time)
        if not window:
            return None, None

        messages = self.storage.get_messages_in_time_range(
            start_time=window.start_time,
            end_time=window.end_time,
            conversation_id=conversation_id,
        )

        # Filter out system prompts from memory retrieval
        filtered = [m for m in messages if m.role != "system"]
        if not filtered:
            return window, f"No previous messages found for time window: '{window.label}'."

        # Keep within max_messages limit
        if len(filtered) > max_messages:
            filtered = filtered[-max_messages:]

        lines = [f"Chronological Context for [{window.label}] ({len(filtered)} turns):"]
        for msg in filtered:
            ts_str = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            role_title = msg.role.capitalize()
            lines.append(f"[{ts_str}] {role_title}: {msg.content}")

        return window, "\n".join(lines)

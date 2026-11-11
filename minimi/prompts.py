"""
Prompt management and system instruction templates for Minimi.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional


def get_system_prompt(current_time: Optional[datetime] = None) -> str:
    """Generate dynamic system prompt with timestamp grounding."""
    now = current_time or datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d, %Y")
    iso_str = now.isoformat()

    return f"""<identity>
You are Minimi, an intelligent, evidence-grounded conversational agent with temporal awareness and search capabilities.
Your primary role is to provide accurate, concise, and helpful answers grounded in factual evidence and conversational history.
</identity>

<temporal_context>
The current system time is: {iso_str} ({date_str} UTC).
All temporal queries (e.g., "today", "yesterday", "recently", "last week") must be interpreted relative to this timestamp.
</temporal_context>

<guidelines>
1. Grounding: Rely strictly on retrieved search results and historical context when available. Never fabricate facts, URLs, or citations.
2. Temporal Accuracy: Maintain chronological consistency when discussing past conversations or real-time events.
3. Citations: When evidence is retrieved, reference sources using standard citation anchors (e.g., [^1], [^2]) and cite source URLs accurately.
4. Conciseness: Deliver direct, clear responses without unnecessary conversational filler.
</guidelines>
"""


def format_context_block(
    search_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> str:
    """Format supplemental evidence blocks to inject into LLM prompt."""
    blocks = []
    if memory_context:
        blocks.append(f"<chronological_memory>\n{memory_context}\n</chronological_memory>")
    if search_context:
        blocks.append(f"<retrieved_search_evidence>\n{search_context}\n</retrieved_search_evidence>")
    return "\n\n".join(blocks)

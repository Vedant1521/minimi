"""
Cross-session historical question recall and hybrid lexical/recency memory search.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import List, Optional

from minimi.storage import StoredMessage, TemporalStorage

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "while", "of", "at", "by", "for",
    "with", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off",
    "over", "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "s", "t", "can", "will", "just", "don", "should", "now", "i",
    "me", "my", "we", "our", "you", "your", "he", "she", "it", "they", "what",
    "did", "ask", "asked", "mention", "mentioned", "talk", "talked", "discuss",
    "discussed", "conversation", "conversations", "session", "sessions", "chat",
    "earlier", "previous", "prior", "past", "remember", "recall",
}

WORD_PATTERN = re.compile(r"[a-zA-Z0-9_]+")

RECALL_TRIGGERS = [
    re.compile(r"\b(?:previous|past|earlier|prior)\s+(?:conversation|session|chat|discussion)s?\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+did\s+i\s+(?:ask|say|mention)\b", re.IGNORECASE),
    re.compile(r"\bdid\s+i\s+(?:ask|say|mention|talk\s+about)\b", re.IGNORECASE),
    re.compile(r"\bhave\s+we\s+(?:talked|discussed|spoken)\s+about\b", re.IGNORECASE),
    re.compile(r"\b(?:remember|recall)\s+(?:when|what|if)\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+(?:our\s+)?(?:last|previous|other)\s+(?:chat|session)\b", re.IGNORECASE),
]


@dataclass
class HistoricalTurn:
    """A paired user question and assistant answer from historical sessions."""
    conversation_id: str
    conversation_title: str
    user_message: str
    assistant_message: Optional[str]
    timestamp: datetime
    score: float


class CrossSessionRecallEngine:
    """Indexes and recalls user questions and answers across historical sessions."""

    def __init__(self, storage: TemporalStorage):
        self.storage = storage

    @classmethod
    def is_recall_query(cls, text: str) -> bool:
        """Determine if a query is asking to recall past conversation history."""
        return any(pattern.search(text) for pattern in RECALL_TRIGGERS)

    @classmethod
    def extract_keywords(cls, text: str) -> set[str]:
        """Extract substantive keywords, filtering out stop words and recall phrases."""
        tokens = WORD_PATTERN.findall(text.lower())
        return {t for t in tokens if t not in STOP_WORDS and len(t) > 2}

    def search_historical_questions(
        self,
        query: str,
        current_session_id: Optional[str] = None,
        top_k: int = 5,
        recency_half_life_days: float = 7.0,
        reference_time: Optional[datetime] = None,
    ) -> list[HistoricalTurn]:
        """Search across historical conversations using hybrid lexical match and recency decay."""
        keywords = self.extract_keywords(query)
        if not keywords:
            # Fallback to general tokens if all words were stripped
            raw_tokens = WORD_PATTERN.findall(query.lower())
            keywords = {t for t in raw_tokens if len(t) > 2}
            if not keywords:
                return []

        now = reference_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Retrieve all conversations from storage
        conversations = self.storage.list_conversations(limit=200)
        candidates: list[HistoricalTurn] = []

        for conv in conversations:
            # Optionally filter out current session if looking strictly across past sessions
            # But allow searching within it if it's the only one or requested
            all_messages = self.storage.get_messages(conv.id)
            if not all_messages:
                continue

            # Pair user messages with immediate assistant responses
            for idx, msg in enumerate(all_messages):
                if msg.role != "user":
                    continue

                user_text = msg.content
                user_tokens = set(WORD_PATTERN.findall(user_text.lower()))

                # Match against keywords
                matched = keywords.intersection(user_tokens)
                if not matched:
                    # Also check partial phrase match
                    matched = {k for k in keywords if k in user_text.lower()}

                if not matched:
                    continue

                # Compute lexical score (Jaccard-like overlap weighted by match count)
                lexical_score = len(matched) / (len(keywords) + 0.5)

                # Locate corresponding assistant response if available
                asst_text: Optional[str] = None
                for forward_idx in range(idx + 1, min(idx + 3, len(all_messages))):
                    if all_messages[forward_idx].role == "assistant":
                        asst_text = all_messages[forward_idx].content
                        break

                # Compute exponential recency decay
                msg_time = msg.timestamp if msg.timestamp.tzinfo else msg.timestamp.replace(tzinfo=timezone.utc)
                days_ago = max(0.0, (now - msg_time).total_seconds() / 86400.0)
                recency_factor = math.pow(2.0, -days_ago / recency_half_life_days)

                # Combined score: 70% lexical relevancy + 30% recency
                final_score = (lexical_score * 0.7) + (recency_factor * 0.3)

                candidates.append(
                    HistoricalTurn(
                        conversation_id=conv.id,
                        conversation_title=conv.title,
                        user_message=user_text,
                        assistant_message=asst_text,
                        timestamp=msg_time,
                        score=final_score,
                    )
                )

        # Sort by final score descending
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:top_k]

    def format_historical_context(self, turns: list[HistoricalTurn]) -> Optional[str]:
        """Format retrieved historical turns into a structured prompt context block."""
        if not turns:
            return None

        lines = [
            f"<historical_cross_session_context>",
            f"Found {len(turns)} relevant prior question(s) from past sessions:",
        ]

        for idx, turn in enumerate(turns, 1):
            ts_str = turn.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            lines.append(f"\n[Prior Turn #{idx} | Session: '{turn.conversation_title}' | {ts_str}]")
            lines.append(f"User Asked: {turn.user_message}")
            if turn.assistant_message:
                lines.append(f"Assistant Answered: {turn.assistant_message}")

        lines.append("</historical_cross_session_context>")
        return "\n".join(lines)

    def recall_and_format(
        self,
        query: str,
        current_session_id: Optional[str] = None,
        top_k: int = 3,
        reference_time: Optional[datetime] = None,
    ) -> Optional[str]:
        """Execute full recall pipeline and return formatted context block."""
        turns = self.search_historical_questions(
            query=query,
            current_session_id=current_session_id,
            top_k=top_k,
            reference_time=reference_time,
        )
        return self.format_historical_context(turns)

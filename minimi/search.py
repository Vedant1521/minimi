"""
Consolidated web search engine and source attribution using Tavily.
"""

from dataclasses import dataclass, field
import os
from typing import Any, List, Optional
from urllib.parse import urlparse

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TavilyClient = None  # type: ignore
    TAVILY_AVAILABLE = False


@dataclass
class Citation:
    """Represents a structured, verifiable source citation."""
    index: int
    title: str
    url: str
    snippet: str
    score: Optional[float] = None

    def to_anchor(self) -> str:
        """Format citation as Markdown anchor."""
        return f"[^{self.index}]"

    def to_citation_line(self) -> str:
        """Format citation entry with anchor, title, and link."""
        title_str = self.title.strip() or "Source"
        return f"[^{self.index}]: [{title_str}]({self.url})"


@dataclass
class SearchResponse:
    """Standardized response from web search execution."""
    query: str
    citations: list[Citation] = field(default_factory=list)
    raw_results: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return len(self.citations) > 0

    def format_for_agent(self) -> str:
        """Format citations and snippets as grounding context for LLM prompt."""
        if not self.citations:
            return f"No web search results found for query: '{self.query}'."

        lines = [f"Search Results for '{self.query}':\n"]
        for cit in self.citations:
            lines.append(f"[^{cit.index}] Title: {cit.title}")
            lines.append(f"    URL: {cit.url}")
            lines.append(f"    Snippet: {cit.snippet}\n")

        lines.append("Sources:")
        for cit in self.citations:
            lines.append(cit.to_citation_line())

        return "\n".join(lines)


class WebSearchEngine:
    """Consolidated web search provider wrapping Tavily with deduplication and source attribution."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TVLY_API_KEY")

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication by stripping tracking query params and trailing slashes."""
        try:
            parsed = urlparse(url)
            scheme = parsed.scheme.lower() or "https"
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip("/")
            return f"{scheme}://{netloc}{path}"
        except Exception:
            return url.strip().rstrip("/")

    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """Execute web search and return structured source citations."""
        clean_query = query.strip()
        if not clean_query:
            return SearchResponse(query=query)

        if not self.api_key:
            return SearchResponse(
                query=clean_query,
                citations=[],
                raw_results=[],
            )

        if not TAVILY_AVAILABLE or TavilyClient is None:
            return SearchResponse(
                query=clean_query,
                citations=[],
                raw_results=[],
            )

        try:
            client = TavilyClient(api_key=self.api_key)
            raw_response = client.search(
                clean_query,
                search_depth="basic",
                max_results=max_results * 2,  # Fetch slightly more to account for dedup
                include_raw_content=False,
            )
        except Exception as e:
            # Handle rate limits, auth errors, or network timeouts cleanly
            return SearchResponse(
                query=clean_query,
                citations=[],
                raw_results=[{"error": str(e)}],
            )

        raw_items = raw_response.get("results", []) if isinstance(raw_response, dict) else []
        citations: list[Citation] = []
        seen_urls: set[str] = set()
        index = 1

        for item in raw_items:
            raw_url = item.get("url", "")
            if not raw_url:
                continue

            normalized_url = self._normalize_url(raw_url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            title = item.get("title", "") or "Untitled Document"
            snippet = item.get("content", "") or ""
            score = item.get("score")

            citations.append(
                Citation(
                    index=index,
                    title=title,
                    url=raw_url,
                    snippet=snippet,
                    score=float(score) if score is not None else None,
                )
            )
            index += 1
            if len(citations) >= max_results:
                break

        return SearchResponse(
            query=clean_query,
            citations=citations,
            raw_results=raw_items,
        )

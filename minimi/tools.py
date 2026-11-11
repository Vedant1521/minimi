"""
Consolidated tool declarations and dispatch registration for Minimi agent.
"""

from typing import Any, Optional
from minimi.search import WebSearchEngine

WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query to look up on the web for factual information.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of search results to retrieve (default: 5).",
        },
    },
    "required": ["query"],
}


def create_web_search_handler(search_engine: WebSearchEngine, agent: Optional[Any] = None):
    """Factory creating the executable handler for the web_search tool."""

    def web_search_handler(query: str, max_results: int = 5) -> str:
        """Execute web search and return formatted attribution context."""
        if not search_engine.api_key:
            return (
                f"Web search unavailable: TVLY_API_KEY is not configured. "
                f"Cannot fetch live results for '{query}'."
            )

        response = search_engine.search(query=query, max_results=max_results)
        if not response.has_results:
            return f"No results found for query: '{query}'."

        if agent and hasattr(agent, "state") and hasattr(agent.state, "active_citations"):
            agent.state.active_citations.extend(response.citations)

        return response.format_for_agent()

    return web_search_handler


def register_default_tools(agent: Any, search_engine: Optional[WebSearchEngine] = None) -> None:
    """Register all default agent tools onto a ConversationalAgent instance."""
    engine = search_engine or WebSearchEngine(api_key=agent.config.tvly_api_key)
    handler = create_web_search_handler(engine, agent=agent)

    agent.register_tool(
        name="web_search",
        description=(
            "Search the web for current events, external documentation, and real-time facts. "
            "Returns structured search results with URL citations and numbered anchors."
        ),
        parameters=WEB_SEARCH_SCHEMA,
        func=handler,
    )

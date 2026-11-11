"""
Core conversational agent loop with state management and tool dispatching.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Callable, Dict, Generator, List, Optional
import uuid

from minimi.config import Config, get_default_config
from minimi.grounding import EvidenceGrounder
from minimi.llm import LLMGateway, LLMResponse, ToolCall
from minimi.prompts import get_system_prompt
from minimi.recall import CrossSessionRecallEngine
from minimi.search import Citation
from minimi.storage import TemporalStorage
from minimi.temporal import ChronologicalMemoryRetriever, TemporalParser
from minimi.tools import register_default_tools


@dataclass
class AgentEvent:
    """Base streaming event emitted during agent orchestration."""
    pass


@dataclass
class TokenDeltaEvent(AgentEvent):
    """Text chunk delta streamed from LLM."""
    delta: str


@dataclass
class ToolStartEvent(AgentEvent):
    """Emitted when agent begins executing a tool."""
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ToolEndEvent(AgentEvent):
    """Emitted when tool execution completes."""
    tool_name: str
    output: str


@dataclass
class CitationEvent(AgentEvent):
    """Emitted when grounding citations and sources footer are synthesized."""
    citations: list[Citation]
    sources_footer: str


@dataclass
class TurnCompleteEvent(AgentEvent):
    """Final event emitted when turn completes with full grounded response."""
    response: str


@dataclass
class ToolDefinition:
    """Tool schema and executable handler."""
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def to_schema(self) -> dict[str, Any]:
        """Convert to OpenAI / LiteLLM function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class AgentState:
    """State tracking for an active conversation session."""
    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    active_citations: list[Citation] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationalAgent:
    """Conversational ReAct agent with LiteLLM integration and tool dispatch."""

    def __init__(
        self,
        config: Optional[Config] = None,
        session_id: Optional[str] = None,
        llm_gateway: Optional[LLMGateway] = None,
        storage: Optional[TemporalStorage] = None,
        auto_register_tools: bool = True,
    ):
        self.config = config or get_default_config()
        self.session_id = session_id or str(uuid.uuid4())
        self.llm = llm_gateway or LLMGateway(
            default_model=self.config.model,
            default_temperature=self.config.temperature,
        )
        self.storage = storage or TemporalStorage(db_path=self.config.db_path)
        self.temporal_retriever = ChronologicalMemoryRetriever(storage=self.storage)
        self.recall_engine = CrossSessionRecallEngine(storage=self.storage)
        self.tools: dict[str, ToolDefinition] = {}
        self.state = AgentState(
            session_id=self.session_id,
            max_iterations=self.config.max_iterations,
        )
        self._init_system_prompt()
        self.load_history()
        self._register_temporal_tool()
        self._register_recall_tool()
        if auto_register_tools:
            register_default_tools(self)

    def _register_recall_tool(self) -> None:
        """Register the built-in cross-session recall tool."""
        self.register_tool(
            name="recall_historical_conversations",
            description=(
                "Search and recall questions and answers from earlier conversation sessions "
                "using semantic keywords or topics."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords or topic to search across previous sessions.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of previous exchanges to retrieve (default: 3).",
                    },
                },
                "required": ["query"],
            },
            func=lambda query, top_k=3: self.recall_engine.recall_and_format(
                query=query, current_session_id=self.session_id, top_k=top_k
            ) or "No relevant questions found from earlier sessions.",
        )

    def _register_temporal_tool(self) -> None:
        """Register the built-in chronological memory retrieval tool."""
        self.register_tool(
            name="retrieve_chronological_memory",
            description=(
                "Query past conversation history within an explicit relative time window "
                "(e.g., 'today', 'yesterday', 'last 2 hours', 'past week')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "time_phrase": {
                        "type": "string",
                        "description": "Temporal expression to search (e.g. 'yesterday', 'past 3 hours').",
                    }
                },
                "required": ["time_phrase"],
            },
            func=lambda time_phrase: self.temporal_retriever.retrieve_context(
                time_phrase, conversation_id=self.session_id
            )[1] or "No memory found for this timeframe.",
        )

    def load_history(self) -> None:
        """Load prior conversation messages from persistent storage into memory."""
        stored = self.storage.get_messages(self.session_id)
        for msg in stored:
            entry: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.citations:
                entry["citations"] = msg.citations
            self.state.messages.append(entry)

    def _init_system_prompt(self) -> None:
        """Initialize or refresh system prompt."""
        system_content = get_system_prompt()
        if not self.state.messages or self.state.messages[0].get("role") != "system":
            self.state.messages.insert(0, {"role": "system", "content": system_content})
        else:
            self.state.messages[0]["content"] = system_content

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: Callable[..., Any],
    ) -> None:
        """Register a callable tool with parameter schema."""
        self.tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            func=func,
        )

    def _get_tools_schema(self) -> Optional[list[dict[str, Any]]]:
        """Return list of active tool schemas for LLM invocation."""
        if not self.tools:
            return None
        return [t.to_schema() for t in self.tools.values()]

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Safely execute a registered tool and format output as string."""
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' is not registered."

        tool = self.tools[tool_name]
        try:
            result = tool.func(**arguments)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"

    def step(self, user_input: str) -> str:
        """Execute a full conversational turn with ReAct tool loop."""
        self._init_system_prompt()

        user_ts = datetime.now(timezone.utc)
        # Add user message to active state and persist
        self.state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": user_ts.isoformat(),
        })
        self.storage.add_message(
            conversation_id=self.session_id,
            role="user",
            content=user_input,
            timestamp=user_ts,
        )

        # Detect temporal queries and inject chronological memory context if available
        window, mem_context = self.temporal_retriever.retrieve_context(
            user_input, conversation_id=self.session_id, reference_time=user_ts
        )
        if mem_context and "No previous messages" not in mem_context:
            self.state.messages.append({
                "role": "system",
                "content": f"<chronological_memory>\n{mem_context}\n</chronological_memory>",
            })

        # Detect cross-session recall queries and inject historical context if available
        if self.recall_engine.is_recall_query(user_input):
            hist_context = self.recall_engine.recall_and_format(
                query=user_input,
                current_session_id=self.session_id,
                top_k=3,
                reference_time=user_ts,
            )
            if hist_context:
                self.state.messages.append({
                    "role": "system",
                    "content": hist_context,
                })

        iteration = 0
        final_response_content = ""

        while iteration < self.state.max_iterations:
            iteration += 1
            self.state.iteration_count += 1

            tools_schema = self._get_tools_schema()
            response = self.llm.complete(
                messages=self.state.messages,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                tools=tools_schema,
            )

            # If tool calls were made by LLM
            if response.tool_calls:
                # Add assistant message with tool calls
                asst_tool_msg = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in response.tool_calls
                    ],
                }
                self.state.messages.append(asst_tool_msg)
                self.storage.add_message(
                    conversation_id=self.session_id,
                    role="assistant",
                    content=response.content or "",
                    tool_calls=asst_tool_msg["tool_calls"],
                )

                # Execute each tool and append tool response message
                for tc in response.tool_calls:
                    tool_output = self.execute_tool(tc.name, tc.arguments)
                    tool_ts = datetime.now(timezone.utc)
                    self.state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": tool_output,
                    })
                    self.storage.add_message(
                        conversation_id=self.session_id,
                        role="tool",
                        content=tool_output,
                        timestamp=tool_ts,
                        metadata={"tool_name": tc.name, "tool_call_id": tc.id},
                    )
                # Continue loop to allow LLM to process tool results
                continue

            # No tool calls; final answer reached
            grounding_report = EvidenceGrounder.verify_and_format(
                response_text=response.content,
                available_citations=self.state.active_citations,
            )
            final_response_content = grounding_report.grounded_response
            citation_dicts = [
                c.to_citation_line()
                for c in self.state.active_citations
                if c.index in grounding_report.valid_indices
            ]
            asst_final_ts = datetime.now(timezone.utc)
            self.state.messages.append({
                "role": "assistant",
                "content": final_response_content,
                "timestamp": asst_final_ts.isoformat(),
                "citations": citation_dicts,
            })
            self.storage.add_message(
                conversation_id=self.session_id,
                role="assistant",
                content=final_response_content,
                timestamp=asst_final_ts,
                citations=[{"line": line} for line in citation_dicts] if citation_dicts else None,
            )
            break

        if not final_response_content:
            # Fallback if loop exceeded max iterations
            final_response_content = "I reached the maximum reasoning steps for this query."
            fallback_ts = datetime.now(timezone.utc)
            self.state.messages.append({
                "role": "assistant",
                "content": final_response_content,
                "timestamp": fallback_ts.isoformat(),
            })
            self.storage.add_message(
                conversation_id=self.session_id,
                role="assistant",
                content=final_response_content,
                timestamp=fallback_ts,
            )

        return final_response_content

    def step_stream(self, user_input: str) -> Generator[str, None, None]:
        """Stream response tokens for queries that do not require tool iterations."""
        self._init_system_prompt()
        stream_user_ts = datetime.now(timezone.utc)
        self.state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": stream_user_ts.isoformat(),
        })
        self.storage.add_message(
            conversation_id=self.session_id,
            role="user",
            content=user_input,
            timestamp=stream_user_ts,
        )

        # Detect temporal queries and inject chronological memory context if available
        window, mem_context = self.temporal_retriever.retrieve_context(
            user_input, conversation_id=self.session_id, reference_time=stream_user_ts
        )
        if mem_context and "No previous messages" not in mem_context:
            self.state.messages.append({
                "role": "system",
                "content": f"<chronological_memory>\n{mem_context}\n</chronological_memory>",
            })

        # Detect cross-session recall queries and inject historical context if available
        if self.recall_engine.is_recall_query(user_input):
            hist_context = self.recall_engine.recall_and_format(
                query=user_input,
                current_session_id=self.session_id,
                top_k=3,
                reference_time=stream_user_ts,
            )
            if hist_context:
                self.state.messages.append({
                    "role": "system",
                    "content": hist_context,
                })

        accumulated = []
        for delta in self.llm.complete_stream(
            messages=self.state.messages,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ):
            accumulated.append(delta)
            yield delta

        full_content = "".join(accumulated)
        grounding_report = EvidenceGrounder.verify_and_format(
            response_text=full_content,
            available_citations=self.state.active_citations,
        )
        final_grounded = grounding_report.grounded_response
        citation_dicts = [
            c.to_citation_line()
            for c in self.state.active_citations
            if c.index in grounding_report.valid_indices
        ]
        stream_asst_ts = datetime.now(timezone.utc)
        self.state.messages.append({
            "role": "assistant",
            "content": final_grounded,
            "timestamp": stream_asst_ts.isoformat(),
            "citations": citation_dicts,
        })
        self.storage.add_message(
            conversation_id=self.session_id,
            role="assistant",
            content=final_grounded,
            timestamp=stream_asst_ts,
            citations=[{"line": line} for line in citation_dicts] if citation_dicts else None,
        )

    def step_stream_events(self, user_input: str) -> Generator[AgentEvent, None, None]:
        """Execute conversational turn emitting real-time tool, token, and grounding events."""
        self._init_system_prompt()
        stream_user_ts = datetime.now(timezone.utc)
        self.state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": stream_user_ts.isoformat(),
        })
        self.storage.add_message(
            conversation_id=self.session_id,
            role="user",
            content=user_input,
            timestamp=stream_user_ts,
        )

        # Detect temporal queries and inject chronological memory context if available
        window, mem_context = self.temporal_retriever.retrieve_context(
            user_input, conversation_id=self.session_id, reference_time=stream_user_ts
        )
        if mem_context and "No previous messages" not in mem_context:
            self.state.messages.append({
                "role": "system",
                "content": f"<chronological_memory>\n{mem_context}\n</chronological_memory>",
            })

        # Detect cross-session recall queries and inject historical context if available
        if self.recall_engine.is_recall_query(user_input):
            hist_context = self.recall_engine.recall_and_format(
                query=user_input,
                current_session_id=self.session_id,
                top_k=3,
                reference_time=stream_user_ts,
            )
            if hist_context:
                self.state.messages.append({
                    "role": "system",
                    "content": hist_context,
                })

        iteration = 0
        final_response_content = ""

        while iteration < self.state.max_iterations:
            iteration += 1
            self.state.iteration_count += 1

            tools_schema = self._get_tools_schema()
            response = self.llm.complete(
                messages=self.state.messages,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                tools=tools_schema,
            )

            if response.tool_calls:
                asst_tool_msg = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in response.tool_calls
                    ],
                }
                self.state.messages.append(asst_tool_msg)
                self.storage.add_message(
                    conversation_id=self.session_id,
                    role="assistant",
                    content=response.content or "",
                    tool_calls=asst_tool_msg["tool_calls"],
                )

                for tc in response.tool_calls:
                    yield ToolStartEvent(tool_name=tc.name, arguments=tc.arguments)
                    tool_output = self.execute_tool(tc.name, tc.arguments)
                    tool_ts = datetime.now(timezone.utc)
                    yield ToolEndEvent(tool_name=tc.name, output=tool_output)

                    self.state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": tool_output,
                    })
                    self.storage.add_message(
                        conversation_id=self.session_id,
                        role="tool",
                        content=tool_output,
                        timestamp=tool_ts,
                        metadata={"tool_name": tc.name, "tool_call_id": tc.id},
                    )
                continue

            final_response_content = response.content
            if final_response_content:
                yield TokenDeltaEvent(delta=final_response_content)

            grounding_report = EvidenceGrounder.verify_and_format(
                response_text=final_response_content,
                available_citations=self.state.active_citations,
            )
            final_grounded = grounding_report.grounded_response
            valid_cits = [
                c for c in self.state.active_citations
                if c.index in grounding_report.valid_indices
            ]
            if grounding_report.sources_footer:
                yield CitationEvent(
                    citations=valid_cits,
                    sources_footer=grounding_report.sources_footer,
                )

            citation_dicts = [c.to_citation_line() for c in valid_cits]
            asst_final_ts = datetime.now(timezone.utc)
            self.state.messages.append({
                "role": "assistant",
                "content": final_grounded,
                "timestamp": asst_final_ts.isoformat(),
                "citations": citation_dicts,
            })
            self.storage.add_message(
                conversation_id=self.session_id,
                role="assistant",
                content=final_grounded,
                timestamp=asst_final_ts,
                citations=[{"line": line} for line in citation_dicts] if citation_dicts else None,
            )
            yield TurnCompleteEvent(response=final_grounded)
            return

        fallback_content = "I reached the maximum reasoning steps for this query."
        fallback_ts = datetime.now(timezone.utc)
        self.state.messages.append({
            "role": "assistant",
            "content": fallback_content,
            "timestamp": fallback_ts.isoformat(),
        })
        self.storage.add_message(
            conversation_id=self.session_id,
            role="assistant",
            content=fallback_content,
            timestamp=fallback_ts,
        )
        yield TokenDeltaEvent(delta=fallback_content)
        yield TurnCompleteEvent(response=fallback_content)

    async def step_async(self, user_input: str) -> str:
        """Asynchronously execute conversational turn via thread pool."""
        import asyncio
        return await asyncio.to_thread(self.step, user_input)

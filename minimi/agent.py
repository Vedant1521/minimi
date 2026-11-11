"""
Core conversational agent loop with state management and tool dispatching.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Callable, Dict, Generator, List, Optional
import uuid

from minimi.config import Config, get_default_config
from minimi.llm import LLMGateway, LLMResponse, ToolCall
from minimi.prompts import get_system_prompt
from minimi.tools import register_default_tools


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
        auto_register_tools: bool = True,
    ):
        self.config = config or get_default_config()
        self.session_id = session_id or str(uuid.uuid4())
        self.llm = llm_gateway or LLMGateway(
            default_model=self.config.model,
            default_temperature=self.config.temperature,
        )
        self.tools: dict[str, ToolDefinition] = {}
        self.state = AgentState(
            session_id=self.session_id,
            max_iterations=self.config.max_iterations,
        )
        self._init_system_prompt()
        if auto_register_tools:
            register_default_tools(self)

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

        # Add user message
        self.state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
                self.state.messages.append({
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
                })

                # Execute each tool and append tool response message
                for tc in response.tool_calls:
                    tool_output = self.execute_tool(tc.name, tc.arguments)
                    self.state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": tool_output,
                    })
                # Continue loop to allow LLM to process tool results
                continue

            # No tool calls; final answer reached
            final_response_content = response.content
            self.state.messages.append({
                "role": "assistant",
                "content": final_response_content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            break

        if not final_response_content:
            # Fallback if loop exceeded max iterations
            final_response_content = "I reached the maximum reasoning steps for this query."
            self.state.messages.append({
                "role": "assistant",
                "content": final_response_content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return final_response_content

    def step_stream(self, user_input: str) -> Generator[str, None, None]:
        """Stream response tokens for queries that do not require tool iterations."""
        self._init_system_prompt()
        self.state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        self.state.messages.append({
            "role": "assistant",
            "content": full_content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

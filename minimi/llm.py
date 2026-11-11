"""
LLM provider gateway using LiteLLM.
"""

from dataclasses import dataclass, field
import os
from typing import Any, Callable, Dict, Generator, List, Optional
import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

# Disable tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Suppress litellm verbose output by default
litellm.suppress_debug_info = True


@dataclass
class ToolCall:
    """Represents a tool/function call emitted by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Standardized response container from LLM invocation."""
    content: str
    model: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None


class LLMGateway:
    """Gateway interface for executing model completions via LiteLLM."""

    def __init__(self, default_model: str = "openai/gpt-4o-mini", default_temperature: float = 0.7):
        self.default_model = default_model
        self.default_temperature = default_temperature

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    def complete(
        self,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 1024,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Execute a non-streaming chat completion."""
        target_model = model or self.default_model
        target_temp = temperature if temperature is not None else self.default_temperature

        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": target_temp,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = litellm.completion(**kwargs)
        choice = response.choices[0]
        message = choice.message

        content = message.content or ""
        tool_calls: list[ToolCall] = []

        if hasattr(message, "tool_calls") and message.tool_calls:
            import json
            for raw_call in message.tool_calls:
                fn_name = raw_call.function.name
                fn_args_raw = raw_call.function.arguments
                try:
                    fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                except Exception:
                    fn_args = {"raw": fn_args_raw}

                tool_calls.append(
                    ToolCall(
                        id=getattr(raw_call, "id", f"call_{len(tool_calls)}"),
                        name=fn_name,
                        arguments=fn_args,
                    )
                )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

        return LLMResponse(
            content=content,
            model=target_model,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=getattr(choice, "finish_reason", "stop"),
        )

    def complete_stream(
        self,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 1024,
    ) -> Generator[str, None, None]:
        """Execute a streaming chat completion yielding text deltas."""
        target_model = model or self.default_model
        target_temp = temperature if temperature is not None else self.default_temperature

        response_stream = litellm.completion(
            model=target_model,
            messages=messages,
            temperature=target_temp,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in response_stream:
            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if delta and getattr(delta, "content", None):
                yield delta.content

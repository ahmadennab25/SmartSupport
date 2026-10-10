"""The single support agent: one LLM that decides which tool to call (function calling)."""
import json
import logging
import time
from dataclasses import dataclass, field

from django.conf import settings

from .llm_client import get_openai_client
from .prompts import build_system_prompt
from .tools import execute_tool, get_tool_names, get_tool_schemas

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    reply: str
    tool_calls: list[str] = field(default_factory=list)
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    failed: bool = False


class SupportAgent:
    def __init__(self, client=None, model: str | None = None, max_rounds: int | None = None):
        self._client = client
        self.model = model or settings.OPENAI_MODEL
        self.max_rounds = max_rounds or getattr(settings, "AGENT_MAX_TOOL_ROUNDS", 5)

    @property
    def client(self):
        if self._client is None:
            self._client = get_openai_client()
        return self._client

    def run(self, customer, user_message: str, history: list[dict] | None = None) -> AgentResult:
        started = time.perf_counter()
        result = AgentResult(reply="", model=self.model)
        messages = [
            {"role": "system", "content": build_system_prompt(customer, get_tool_names())},
            *(history or []),
            {"role": "user", "content": user_message},
        ]
        try:
            for _ in range(self.max_rounds):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=get_tool_schemas(),
                    temperature=settings.OPENAI_DEFAULT_TEMPERATURE,
                )
                self._add_usage(result, response)
                message = response.choices[0].message
                tool_calls = getattr(message, "tool_calls", None) or []
                if not tool_calls:
                    result.reply = (message.content or "").strip()
                    break
                messages.append(self._assistant_tool_message(message, tool_calls))
                for call in tool_calls:
                    result.tool_calls.append(call.function.name)
                    output = execute_tool(call.function.name, call.function.arguments, customer)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(output, ensure_ascii=False, default=str),
                        }
                    )
        except Exception:
            logger.exception("Support agent failed")

        if not result.reply:
            result.failed = True
            result.reply = settings.OPENAI_DEFAULT_ERROR_MESSAGE
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    @staticmethod
    def _assistant_tool_message(message, tool_calls) -> dict:
        return {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in tool_calls
            ],
        }

    @staticmethod
    def _add_usage(result: AgentResult, response) -> None:
        usage = getattr(response, "usage", None)
        if usage:
            result.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            result.completion_tokens += getattr(usage, "completion_tokens", 0) or 0

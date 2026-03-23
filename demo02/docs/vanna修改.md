# D:\Files\Pycharm\vanna\src\vanna\integrations\openai\llm.py

```python
"""
OpenAI LLM service implementation.

This module provides an implementation of the LlmService interface backed by
OpenAI's Chat Completions API (openai>=1.0.0). It supports non-streaming
responses and best-effort streaming of text content. Tool/function calling is
passed through when tools are provided, but full tool-call conversation
round-tripping may require adding assistant tool-call messages to the
conversation upstream.
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

from vanna.core.llm import (
    LlmService,
    LlmRequest,
    LlmResponse,
    LlmStreamChunk,
)
from vanna.core.tool import ToolCall, ToolSchema


class OpenAILlmService(LlmService):
    """OpenAI Chat Completions-backed LLM service.

    Args:
        model: OpenAI model name (e.g., "gpt-5").
        api_key: API key; falls back to env `OPENAI_API_KEY`.
        organization: Optional org; env `OPENAI_ORG` if unset.
        base_url: Optional custom base URL; env `OPENAI_BASE_URL` if unset.
        extra_client_kwargs: Extra kwargs forwarded to `openai.OpenAI()`.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        base_url: Optional[str] = None,
        **extra_client_kwargs: Any,
    ) -> None:
        try:
            from openai import OpenAI
        except Exception as e:  # pragma: no cover - import-time error surface
            raise ImportError(
                "openai package is required. Install with: pip install 'vanna[openai]'"
            ) from e

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        organization = organization or os.getenv("OPENAI_ORG")
        base_url = base_url or os.getenv("OPENAI_BASE_URL")

        client_kwargs: Dict[str, Any] = {**extra_client_kwargs}
        if api_key:
            client_kwargs["api_key"] = api_key
        if organization:
            client_kwargs["organization"] = organization
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(**client_kwargs)

    async def send_request(self, request: LlmRequest) -> LlmResponse:
        """Send a non-streaming request to OpenAI and return the response."""
        payload = self._build_payload(request)

        # Call the API synchronously; this function is async but we can block here.
        resp = self._client.chat.completions.create(**payload, stream=False)

        if not resp.choices:
            return LlmResponse(content=None, tool_calls=None, finish_reason=None)

        choice = resp.choices[0]
        content: Optional[str] = getattr(choice.message, "content", None)
        tool_calls = self._extract_tool_calls_from_message(choice.message)

        usage: Dict[str, int] = {}
        if getattr(resp, "usage", None):
            usage = {
                k: int(v)
                for k, v in {
                    "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
                    "total_tokens": getattr(resp.usage, "total_tokens", 0),
                }.items()
            }

        return LlmResponse(
            content=content,
            tool_calls=tool_calls or None,
            finish_reason=getattr(choice, "finish_reason", None),
            usage=usage or None,
        )

    async def stream_request(
        self, request: LlmRequest
    ) -> AsyncGenerator[LlmStreamChunk, None]:
        """Stream a request to OpenAI.

        Emits `LlmStreamChunk` for textual deltas as they arrive. Tool-calls are
        accumulated and emitted in a final chunk when the stream ends.
        """
        payload = self._build_payload(request)

        # Debug: if tool calling is involved, print message structure.
        try:
            msg_summary = []
            has_tool_role = False
            for i, mm in enumerate(payload.get("messages", []) or []):
                role = mm.get("role")
                if role == "tool":
                    has_tool_role = True
                entry = {"i": i, "role": role}
                if "content" in mm:
                    c = mm.get("content")
                    entry["content_present"] = True
                    if c is None:
                        entry["content_is_none"] = True
                    elif isinstance(c, str):
                        entry["content_len"] = len(c)
                    else:
                        entry["content_type"] = type(c).__name__
                else:
                    entry["content_present"] = False
                if role == "tool":
                    entry["tool_call_id"] = mm.get("tool_call_id")
                if role == "assistant" and mm.get("tool_calls"):
                    tcs = mm["tool_calls"]
                    entry["tool_calls"] = [
                        {
                            "id": tc.get("id"),
                            "name": (tc.get("function") or {}).get("name"),
                        }
                        for tc in tcs
                    ]
                msg_summary.append(entry)
            if has_tool_role:
                print(
                    "[OpenAI LLM payload debug] model="
                    + str(payload.get("model"))
                    + " messages="
                    + str(msg_summary)
                    + " tools_present="
                    + str(bool(payload.get("tools")))
                )
        except Exception:
            # Never let debug printing break the request.
            pass

        # Synchronous streaming iterator; iterate within async context.
        try:
            stream = self._client.chat.completions.create(**payload, stream=True)
        except Exception as e:
            # Some OpenAI-compatible gateways reject tool-calling payloads only on streaming.
            # Retry with non-streaming so tool-calling can proceed.
            msg = str(e)
            if ("messages" in msg and "illegal" in msg):
                resp = await self.send_request(request)
                if resp.tool_calls:
                    yield LlmStreamChunk(
                        tool_calls=resp.tool_calls,
                        finish_reason=resp.finish_reason or "stop",
                    )
                else:
                    yield LlmStreamChunk(
                        content=resp.content,
                        finish_reason=resp.finish_reason or "stop",
                    )
                return
            raise

        # Builders for streamed tool-calls (index -> partial)
        tc_builders: Dict[int, Dict[str, Optional[str]]] = {}
        last_finish: Optional[str] = None

        for event in stream:
            if not getattr(event, "choices", None):
                continue

            choice = event.choices[0]
            delta = getattr(choice, "delta", None)
            if delta is None:
                # Some SDK versions use `event.choices[0].message` on the final packet
                last_finish = getattr(choice, "finish_reason", last_finish)
                continue

            # Text content
            content_piece: Optional[str] = getattr(delta, "content", None)
            if content_piece:
                yield LlmStreamChunk(content=content_piece)

            # Tool calls (streamed)
            streamed_tool_calls = getattr(delta, "tool_calls", None)
            if streamed_tool_calls:
                for tc in streamed_tool_calls:
                    idx = getattr(tc, "index", 0) or 0
                    b = tc_builders.setdefault(
                        idx, {"id": None, "name": None, "arguments": ""}
                    )
                    if getattr(tc, "id", None):
                        b["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            b["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            b["arguments"] = (b["arguments"] or "") + fn.arguments

            last_finish = getattr(choice, "finish_reason", last_finish)

        # Emit final tool-calls chunk if any
        final_tool_calls: List[ToolCall] = []
        for b in tc_builders.values():
            if not b.get("name"):
                continue
            args_raw = b.get("arguments") or "{}"
            try:
                loaded = json.loads(args_raw)
                if isinstance(loaded, dict):
                    args_dict: Dict[str, Any] = loaded
                else:
                    args_dict = {"args": loaded}
            except Exception:
                args_dict = {"_raw": args_raw}
            final_tool_calls.append(
                ToolCall(
                    id=b.get("id") or "tool_call",
                    name=b["name"] or "tool",
                    arguments=args_dict,
                )
            )

        if final_tool_calls:
            yield LlmStreamChunk(tool_calls=final_tool_calls, finish_reason=last_finish)
        else:
            # Still emit a terminal chunk to signal completion
            yield LlmStreamChunk(finish_reason=last_finish or "stop")

    async def validate_tools(self, tools: List[ToolSchema]) -> List[str]:
        """Validate tool schemas. Returns a list of error messages."""
        errors: List[str] = []
        # Basic checks; OpenAI will enforce further validation server-side.
        for t in tools:
            if not t.name or len(t.name) > 64:
                errors.append(f"Invalid tool name: {t.name!r}")
        return errors

    # Internal helpers
    def _build_payload(self, request: LlmRequest) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = []

        # Add system prompt as first message if provided
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        for m in request.messages:
            # Some tool-calling providers are strict about assistant/tool message shapes.
            # In particular, when `assistant.tool_calls` exists, `content` being `null` can be rejected.
            if m.role == "assistant" and m.tool_calls:
                # Many OpenAI-compatible gateways reject assistant+tool_calls when `content`
                # is null or non-empty. Use empty string to keep the message shape stable.
                msg = {"role": m.role, "content": ""}
            else:
                msg = {"role": m.role, "content": m.content}

            if m.role == "tool" and m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            elif m.role == "tool":
                # Some providers enforce strict validation for tool messages.
                # If tool_call_id is missing, request can be rejected with "messages illegal".
                msg["tool_call_id"] = m.tool_call_id or "tool_call"
                if msg.get("content") is None:
                    msg["content"] = ""
            elif m.role == "assistant" and m.tool_calls:
                # Convert tool calls to OpenAI format
                tool_calls_payload = []
                for tc in m.tool_calls:
                    tool_calls_payload.append(
                        {
                            "id": tc.id or "tool_call",
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                    )
                msg["tool_calls"] = tool_calls_payload
            messages.append(msg)

        # Quick structural sanity checks for tool calling.
        # If the provider rejects the request, these logs usually make the culprit obvious.
        if messages:
            tool_msg_missing_id = [
                i
                for i, mm in enumerate(messages)
                if mm.get("role") == "tool" and not mm.get("tool_call_id")
            ]
            if tool_msg_missing_id:
                # Keep output short; this is for debugging only.
                print(f"[OpenAI LLM payload debug] tool messages missing tool_call_id at indexes: {tool_msg_missing_id}")

        tools_payload: Optional[List[Dict[str, Any]]] = None
        if request.tools:
            tools_payload = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if tools_payload:
            payload["tools"] = tools_payload
            payload["tool_choice"] = "auto"

        return payload

    def _extract_tool_calls_from_message(self, message: Any) -> List[ToolCall]:
        tool_calls: List[ToolCall] = []
        raw_tool_calls = getattr(message, "tool_calls", None) or []
        for tc in raw_tool_calls:
            fn = getattr(tc, "function", None)
            if not fn:
                continue
            args_raw = getattr(fn, "arguments", "{}")
            try:
                loaded = json.loads(args_raw)
                if isinstance(loaded, dict):
                    args_dict: Dict[str, Any] = loaded
                else:
                    args_dict = {"args": loaded}
            except Exception:
                args_dict = {"_raw": args_raw}
            tool_calls.append(
                ToolCall(
                    id=getattr(tc, "id", "tool_call"),
                    name=getattr(fn, "name", "tool"),
                    arguments=args_dict,
                )
            )
        return tool_calls

```


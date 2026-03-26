"""
带超时功能的 LLM 服务包装器。

当 LLM 响应超过指定时间（默认 5 分钟）时，自动终止会话并返回超时提示。
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, List, Optional

from vanna.core.llm import (
    LlmService,
    LlmRequest,
    LlmResponse,
    LlmStreamChunk,
)
from vanna.core.tool import ToolSchema

logger = logging.getLogger(__name__)


class LlmTimeoutError(Exception):
    """LLM 请求超时异常。"""

    def __init__(self, timeout_seconds: float, message: Optional[str] = None):
        self.timeout_seconds = timeout_seconds
        self.message = message or f"LLM 请求超时，已超过 {timeout_seconds / 60:.1f} 分钟"
        super().__init__(self.message)


class TimeoutLlmService(LlmService):
    """带超时功能的 LLM 服务包装器。

    包装任意 LlmService 实现，为所有 LLM 请求添加超时控制。
    当请求超时时，返回包含超时提示的响应。

    Args:
        llm_service: 被包装的 LLM 服务实例。
        timeout_seconds: 超时时间（秒），默认 300 秒（5 分钟）。
        timeout_message: 超时时返回的提示信息。
    """

    DEFAULT_TIMEOUT_SECONDS = 300  # 5 分钟
    DEFAULT_TIMEOUT_MESSAGE = (
        "抱歉，LLM 响应超时（已超过 5 分钟）。"
        "当前会话已自动终止，请尝试简化您的问题或稍后重试。"
    )

    def __init__(
        self,
        llm_service: LlmService,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        timeout_message: Optional[str] = None,
    ) -> None:
        self._llm_service = llm_service
        self._timeout_seconds = timeout_seconds
        self._timeout_message = timeout_message or self.DEFAULT_TIMEOUT_MESSAGE

        # 继承被包装服务的 model 属性（如果有）
        if hasattr(llm_service, "model"):
            self.model = llm_service.model

    async def send_request(self, request: LlmRequest) -> LlmResponse:
        """发送非流式请求，带超时控制。"""
        try:
            return await asyncio.wait_for(
                self._llm_service.send_request(request),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"LLM 请求超时: 已超过 {self._timeout_seconds / 60:.1f} 分钟"
            )
            # 返回包含超时提示的响应
            return LlmResponse(
                content=self._timeout_message,
                tool_calls=None,
                finish_reason="timeout",
            )

    async def stream_request(
        self, request: LlmRequest
    ) -> AsyncGenerator[LlmStreamChunk, None]:
        """发送流式请求，带超时控制。

        对于流式请求，超时计时从第一个 chunk 开始，
        如果在超时时间内没有收到新的 chunk，则终止流并返回超时提示。
        """
        try:
            async for chunk in self._stream_with_timeout(request):
                yield chunk
        except asyncio.TimeoutError:
            logger.warning(
                f"LLM 流式响应超时: 已超过 {self._timeout_seconds / 60:.1f} 分钟"
            )
            # 返回超时提示 chunk
            yield LlmStreamChunk(
                content=f"\n\n{self._timeout_message}",
                finish_reason="timeout",
            )

    async def _stream_with_timeout(
        self, request: LlmRequest
    ) -> AsyncGenerator[LlmStreamChunk, None]:
        """内部方法：带整体超时的流式请求。

        整个流式响应过程的总时间不能超过超时时间。
        """
        # 创建底层流生成器
        stream = self._llm_service.stream_request(request)

        # 使用 asyncio.timeout 控制整体超时（Python 3.11+）
        # 对于旧版本 Python，使用手动超时控制
        try:
            # Python 3.11+ 使用 asyncio.timeout
            async with asyncio.timeout(self._timeout_seconds):
                async for chunk in stream:
                    yield chunk
        except AttributeError:
            # Python < 3.11 回退方案
            async for chunk in self._stream_with_manual_timeout(stream):
                yield chunk

    async def _stream_with_manual_timeout(
        self, stream: AsyncGenerator[LlmStreamChunk, None]
    ) -> AsyncGenerator[LlmStreamChunk, None]:
        """Python < 3.11 的手动超时实现。"""
        import time

        start_time = time.monotonic()

        async for chunk in stream:
            elapsed = time.monotonic() - start_time
            if elapsed > self._timeout_seconds:
                raise asyncio.TimeoutError()
            yield chunk

    async def validate_tools(self, tools: List[ToolSchema]) -> List[str]:
        """验证工具模式，委托给底层服务。"""
        return await self._llm_service.validate_tools(tools)

    def __getattr__(self, name: str):
        """将未定义的属性访问委托给底层 LLM 服务。"""
        return getattr(self._llm_service, name)

"""
日志可观测性提供者。

记录 Agent 运行时的指标（Metric）和链路追踪（Span），
用于监控 LLM 调用耗时、工具执行耗时等性能数据。
"""

import logging
from typing import Any, Dict, List, Optional

from vanna.core import (
    ObservabilityProvider,
    Span,
    Metric,
)

logger = logging.getLogger(__name__)


class LoggingObservabilityProvider(ObservabilityProvider):
    """基于 logging 的可观测性提供者，记录指标和链路追踪。"""

    def __init__(self) -> None:
        self.metrics: List[Metric] = []
        self.spans: List[Span] = []

    async def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录指标数据。"""
        metric = Metric(name=name, value=value, unit=unit, tags=tags or {})
        self.metrics.append(metric)
        tags_str = ", ".join(f"{k}={v}" for k, v in (tags or {}).items())
        logger.info(f"[METRIC] {name}: {value}{unit} {tags_str}")

    async def create_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Span:
        """创建链路追踪 span。"""
        span = Span(name=name, attributes=attributes or {})
        logger.info(f"[SPAN 开始] {name}")
        return span

    async def end_span(self, span: Span) -> None:
        """结束 span 并记录耗时。"""
        span.end()
        self.spans.append(span)
        duration = span.duration_ms() or 0
        logger.info(f"[SPAN 结束] {span.name}: {duration:.2f}ms")

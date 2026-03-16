"""
日志可观测性提供者。

记录指标和追踪信息，方便监控和调试。
"""

from typing import Any, Dict, List, Optional

from vanna.core import (
    ObservabilityProvider,
    Span,
    Metric,
)


class LoggingObservabilityProvider(ObservabilityProvider):
    """通过日志记录指标和追踪信息的可观测性提供者。"""

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
        metric = Metric(name=name, value=value, unit=unit, tags=tags or {})
        self.metrics.append(metric)
        tags_str = ", ".join(f"{k}={v}" for k, v in (tags or {}).items())
        print(f"[指标] {name}: {value}{unit} {tags_str}")

    async def create_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Span:
        span = Span(name=name, attributes=attributes or {})
        print(f"[追踪开始] {name}")
        return span

    async def end_span(self, span: Span) -> None:
        span.end()
        self.spans.append(span)
        duration = span.duration_ms() or 0
        print(f"[追踪结束] {span.name}: {duration:.2f}ms")

"""
日志生命周期钩子（复用 demo01）。
"""

from typing import Any, Optional
from vanna.core.lifecycle import LifecycleHook
from vanna.core import Tool
from vanna.core import ToolContext, ToolResult


class LoggingLifecycleHook(LifecycleHook):
    """在工具调用前后记录日志的生命周期钩子。"""

    async def before_tool(self, tool: "Tool[Any]", context: "ToolContext") -> None:
        print("===== 工具请求 =====")
        for field_name, field_value in tool.__dict__.items():
            print(f"  {field_name}: {field_value}")

    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        print("===== 工具响应 =====")
        for field_name, field_value in result.__dict__.items():
            print(f"  {field_name}: {field_value}")
        return None

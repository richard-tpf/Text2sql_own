"""
空操作的 AgentMemory 实现（复用 demo01）。
"""

from typing import Any, Dict, List, Optional

from vanna.capabilities.agent_memory import (
    AgentMemory,
    TextMemory,
    TextMemorySearchResult,
    ToolMemory,
    ToolMemorySearchResult,
)
from vanna.core.tool import ToolContext


class NoOpAgentMemory(AgentMemory):
    """不执行任何操作的 AgentMemory 空实现。"""

    async def save_tool_usage(self, question, tool_name, args, context, success=True, metadata=None):
        pass

    async def save_text_memory(self, content, context):
        return TextMemory(content=content)

    async def search_similar_usage(self, question, context, *, limit=10, similarity_threshold=0.7, tool_name_filter=None):
        return []

    async def search_text_memories(self, query, context, *, limit=10, similarity_threshold=0.7):
        return []

    async def get_recent_memories(self, context, limit=10):
        return []

    async def get_recent_text_memories(self, context, limit=10):
        return []

    async def delete_by_id(self, context, memory_id):
        return False

    async def delete_text_memory(self, context, memory_id):
        return False

    async def clear_memories(self, context, tool_name=None, before_date=None):
        return 0

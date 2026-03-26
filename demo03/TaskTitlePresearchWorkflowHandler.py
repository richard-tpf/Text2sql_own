"""
Workflow handler for requirement-title pre-search in demo03.

At the beginning of a conversation, if the first user message looks like a
task title / requirement name, run search_knowledge(search_scope='business')
before normal LLM processing and inject the result into conversation context.
"""

from __future__ import annotations

import re
import uuid
from typing import List

from vanna.core.storage import Message
from vanna.core.tool import ToolCall, ToolContext
from vanna.core.workflow.base import WorkflowResult
from vanna.core.workflow.default import DefaultWorkflowHandler


class TaskTitlePresearchWorkflowHandler(DefaultWorkflowHandler):
    """Pre-search business knowledge when first message is likely a task title."""

    _TASK_TITLE_PATTERNS: List[re.Pattern[str]] = [
        re.compile(r"(?:开发|设计|实现|构建|生成).{0,30}(?:指标|统计|报表|宽表|明细表|需求|任务)"),
        re.compile(r"(?:任务标题|需求标题|需求名)"),
        re.compile(r"[《【].{2,80}[》】]"),
        re.compile(r".{2,80}(?:指标统计表|漏斗|看板|报表)$"),
    ]

    def _is_first_user_turn(self, conversation: "Conversation") -> bool:
        return not any(msg.role == "user" for msg in conversation.messages)

    def _looks_like_task_title(self, message: str) -> bool:
        text = (message or "").strip()
        if not text:
            return False
        if len(text) > 200:
            return False
        return any(p.search(text) for p in self._TASK_TITLE_PATTERNS)

    async def try_handle(
        self, agent: "Agent", user: "User", conversation: "Conversation", message: str
    ) -> WorkflowResult:
        # Preserve default commands/starter behavior first.
        base_result = await super().try_handle(agent, user, conversation, message)
        if base_result.should_skip_llm:
            return base_result

        # Only run once at the beginning of a conversation.
        if not self._is_first_user_turn(conversation):
            return WorkflowResult(should_skip_llm=False)

        if not self._looks_like_task_title(message):
            return WorkflowResult(should_skip_llm=False)

        # Execute business pre-search via ToolRegistry to keep access checks and
        # argument validation behavior consistent with normal tool-calling flow.
        tool_call = ToolCall(
            id=f"wf_presearch_{uuid.uuid4().hex[:8]}",
            name="search_knowledge",
            arguments={
                "query": message.strip(),
                "search_scope": "business",
                "limit": 5,
            },
        )
        context = ToolContext(
            user=user,
            conversation_id=conversation.id,
            request_id=f"wf_presearch_{uuid.uuid4().hex[:12]}",
            agent_memory=agent.agent_memory,
            observability_provider=agent.observability_provider,
            metadata={"workflow_presearch": True},
        )

        result = await agent.tool_registry.execute(tool_call, context)
        summary = (
            result.result_for_llm
            if result.success
            else f"预检索失败: {result.error or result.result_for_llm}"
        )

        # Inject as system context for the next LLM request in the same turn.
        conversation.add_message(
            Message(
                role="system",
                content=(
                    "[工作流预检索] 已针对当前任务标题执行业务知识库检索。\n"
                    f"检索query: {message.strip()}\n"
                    f"检索结果:\n{summary}"
                ),
                metadata={"workflow_presearch": True, "scope": "business"},
            )
        )
        return WorkflowResult(should_skip_llm=False)


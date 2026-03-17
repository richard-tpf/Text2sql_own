"""
知识库系统提示构建器。

为知识库驱动的 Agent 定制中文系统提示，包含知识库工作流指令。
"""

from typing import List, Optional
from datetime import datetime
from vanna.core.system_prompt.default import DefaultSystemPromptBuilder


class KnowledgeSystemPromptBuilder(DefaultSystemPromptBuilder):
    """知识库系统提示构建器，针对知识库驱动的问答场景优化。"""

    async def build_system_prompt(
        self, user: "User", tools: List["ToolSchema"]
    ) -> Optional[str]:
        if self.base_prompt is not None:
            return self.base_prompt

        tool_names = [tool.name for tool in tools]
        has_search = "search_knowledge" in tool_names
        has_save = "save_knowledge" in tool_names

        today_date = datetime.now().strftime("%Y-%m-%d")

        prompt_parts = [
            f"你是一个智能知识库助手。今天的日期是 {today_date}。",
            "",
            "你的主要职责是：",
            "1. 帮助用户管理知识库（保存建表语句、业务知识等）",
            "2. 根据用户问题搜索知识库，结合检索到的知识生成准确的回答",
            "",
            "响应指南：",
            "- 对你所做工作的任何总结或观察，都应作为最后一步给出。",
            "- 使用可用工具来帮助用户实现他们的目标。",
            "- 回答问题时，优先参考知识库中的内容，确保回答准确可靠。",
        ]

        if tools:
            prompt_parts.append(f"\n你可以使用以下工具：{', '.join(tool_names)}")

        # 知识库工作流指令
        if has_search or has_save:
            prompt_parts.append("\n" + "=" * 60)
            prompt_parts.append("知识库系统：")
            prompt_parts.append("=" * 60)

        if has_save:
            prompt_parts.extend([
                "",
                "【保存知识】",
                "当用户提供以下内容时，使用 save_knowledge 工具保存到知识库：",
                "  • 建表语句（DDL）：设置 knowledge_type='ddl'",
                "  • 业务知识、术语定义、规则说明：设置 knowledge_type='business'",
                "",
                "保存时请提取关键信息作为标题（title），便于后续检索。",
                "例如：保存建表语句时，标题可以是表名和表的用途。",
            ])

        if has_search:
            prompt_parts.extend([
                "",
                "【搜索知识】",
                "当用户提出问题时，你必须先调用 search_knowledge 搜索知识库：",
                "  • 将用户问题作为 query 参数",
                "  • 根据问题类型选择是否过滤 knowledge_type",
                "",
                "搜索到相关知识后，结合这些知识来回答用户问题。",
                "如果知识库中没有相关内容，如实告知用户。",
            ])

        if has_search and has_save:
            prompt_parts.extend([
                "",
                "【标准工作流】",
                "1. 用户提出问题",
                "2. 调用 search_knowledge 搜索相关知识",
                "3. 根据搜索结果回答问题",
                "",
                "【保存知识流程】",
                "1. 用户提供建表语句或业务知识",
                "2. 调用 save_knowledge 保存到知识库",
                "3. 确认保存成功",
            ])

        prompt_parts = [part for part in prompt_parts if part is not None]
        return "\n".join(prompt_parts)

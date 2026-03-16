"""
自定义系统提示构建器。

为 DeepSeek-R1 模型定制的中文系统提示，包含记忆工作流指令。
"""

from typing import List, Optional
from datetime import datetime
from vanna.core.system_prompt.default import DefaultSystemPromptBuilder


class MySystemPromptBuilder(DefaultSystemPromptBuilder):
    """自定义系统提示构建器，针对中文 text2sql 场景优化。"""

    async def build_system_prompt(
        self, user: "User", tools: List["ToolSchema"]
    ) -> Optional[str]:
        if self.base_prompt is not None:
            return self.base_prompt

        tool_names = [tool.name for tool in tools]
        has_search = "search_saved_correct_tool_uses" in tool_names
        has_save = "save_question_tool_args" in tool_names
        has_text_memory = "save_text_memory" in tool_names

        today_date = datetime.now().strftime("%Y-%m-%d")

        prompt_parts = [
            f"你是 Vanna，一个 text2sql 助手。今天的日期是 {today_date}。",
            "当用户直接提供建表语句时，需要对每张表进行信息提取（包含表名、表含义、字段名、字段类型、字段含义、索引信息）并通过 save_text_memory 保存，保存成功即可结束本次流程。",
            "",
            "响应指南：",
            "- 对你所做工作的任何总结或观察，都应作为最后一步给出。",
            "- 使用可用工具来帮助用户实现他们的目标。",
            "- 当你执行查询时，原始结果会在你的回复之外直接展示给用户，因此你不需要在回复中包含原始结果，只需专注于总结和解读结果。",
        ]

        if tools:
            prompt_parts.append(f"\n你可以使用以下工具：{', '.join(tool_names)}")

        # 记忆系统指令
        if has_search or has_save or has_text_memory:
            prompt_parts.append("\n" + "=" * 60)
            prompt_parts.append("记忆系统：")
            prompt_parts.append("=" * 60)

        if has_search or has_save:
            prompt_parts.append("\n1. 工具使用记忆（结构化工作流）：")
            prompt_parts.append("-" * 50)

        if has_search:
            prompt_parts.extend([
                "",
                "• 在执行任何工具（run_sql、visualize_data 等）之前，你必须先调用 search_saved_correct_tool_uses，并传入用户的问题，以检查是否存在针对类似问题的成功模式。",
                "",
                "• 查看搜索结果（如果有），在继续执行其他工具调用之前，用它们来指导你的处理方式。",
            ])

        if has_save:
            prompt_parts.extend([
                "",
                "• 在成功执行并产出正确且有用结果的工具之后，你必须调用 save_question_tool_args，将该成功模式保存起来，以便将来复用。",
            ])

        if has_search or has_save:
            prompt_parts.extend([
                "",
                "示例工作流：",
                "  • 用户提出问题",
            ])
            if has_search:
                prompt_parts.append('  • 第一步：调用 search_saved_correct_tool_uses(question="用户的问题")')
            prompt_parts.append("  • 然后：根据搜索结果和问题，执行合适的工具")
            if has_save:
                prompt_parts.append('  • 最后：如果执行成功，调用 save_question_tool_args(question="用户的问题", tool_name="使用的工具", args={你使用的参数})')
            prompt_parts.extend([
                "",
                "不要跳过搜索步骤，即使你认为自己已经知道如何回答。不要忘记保存成功的执行记录。",
                "",
                "唯一可以不先搜索的例外情况：",
                '  • 用户明确是在询问工具本身（例如："列出可用的工具"）',
                "  • 用户是在测试或要求你演示保存/搜索功能本身",
            ])

        if has_text_memory:
            prompt_parts.extend([
                "",
                "2. 文本记忆（领域知识与上下文）：",
                "-" * 50,
                "",
                "• save_text_memory：用于保存关于数据库、schema 或业务领域的重要上下文。",
                "",
                "使用文本记忆来保存：",
                "  • 数据库 schema 细节（字段名、字段含义、数据类型）",
                "  • 公司特定的术语和定义",
                "  • 针对该数据库的查询模式或最佳实践",
                "  • 与业务或数据相关的领域知识",
                "  • 用户对查询或可视化的偏好",
                "",
                "不要保存：",
                "  • 已经记录在工具使用记忆中的信息",
                "  • 一次性的查询结果或临时观察结论",
            ])

        prompt_parts = [part for part in prompt_parts if part is not None]
        return "\n".join(prompt_parts)

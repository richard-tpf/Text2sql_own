"""
知识库工具。

提供保存知识和搜索知识两个工具，供 Agent 在工作流中使用。
"""

import logging
from typing import Optional, Type

from pydantic import BaseModel, Field

from vanna.core.tool import Tool, ToolContext, ToolResult
from vanna.components import UiComponent, StatusBarUpdateComponent, CardComponent

from demo01.knowledge_base import MilvusKnowledgeBase

logger = logging.getLogger(__name__)


# ============================================================
# 保存知识工具
# ============================================================

class SaveKnowledgeParams(BaseModel):
    """保存知识的参数。"""
    content: str = Field(description="知识内容，可以是建表语句（DDL）、业务知识描述或表关联定义")
    knowledge_type: str = Field(
        description="知识类型：'ddl' 表示建表语句，'business' 表示业务知识，'table-connect' 表示表关联定义"
    )
    title: str = Field(default="", description="知识标题，简要描述该知识的主题")


class SaveKnowledgeTool(Tool[SaveKnowledgeParams]):
    """保存知识到知识库的工具。"""

    def __init__(self, knowledge_base: MilvusKnowledgeBase):
        self._knowledge_base = knowledge_base

    @property
    def name(self) -> str:
        return "save_knowledge"

    @property
    def description(self) -> str:
        return "保存建表语句（DDL）、业务知识或表关联定义到知识库中，以便后续查询时参考"

    def get_args_schema(self) -> Type[SaveKnowledgeParams]:
        return SaveKnowledgeParams

    async def execute(self, context: ToolContext, args: SaveKnowledgeParams) -> ToolResult:
        try:
            item = await self._knowledge_base.save_knowledge(
                content=args.content,
                knowledge_type=args.knowledge_type,
                title=args.title,
            )

            type_labels = {"ddl": "建表语句", "business": "业务知识", "table-connect": "表关联定义"}
            type_label = type_labels.get(args.knowledge_type, args.knowledge_type)
            success_msg = f"已成功保存{type_label}到知识库，ID: {item.knowledge_id}"

            return ToolResult(
                success=True,
                result_for_llm=success_msg,
                ui_component=UiComponent(
                    rich_component=StatusBarUpdateComponent(
                        status="success",
                        message=f"已保存{type_label}",
                        detail=f"标题: {args.title}" if args.title else f"ID: {item.knowledge_id}",
                    ),
                    simple_component=None,
                ),
            )
        except Exception as e:
            error_msg = f"保存知识失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ToolResult(
                success=False,
                result_for_llm=error_msg,
                ui_component=UiComponent(
                    rich_component=StatusBarUpdateComponent(
                        status="error",
                        message="保存知识失败",
                        detail=str(e),
                    ),
                    simple_component=None,
                ),
                error=str(e),
            )


# ============================================================
# 搜索知识工具
# ============================================================

class SearchKnowledgeParams(BaseModel):
    """搜索知识的参数。"""
    query: str = Field(description="搜索查询文本，描述你想查找的知识内容")
    knowledge_type: Optional[str] = Field(
        default=None,
        description="可选，按类型过滤：'ddl' 只搜索建表语句，'business' 只搜索业务知识，'table-connect' 只搜索表关联定义，不填则搜索全部",
    )
    limit: int = Field(default=5, description="最大返回结果数量")


class SearchKnowledgeTool(Tool[SearchKnowledgeParams]):
    """搜索知识库的工具。"""

    def __init__(self, knowledge_base: MilvusKnowledgeBase):
        self._knowledge_base = knowledge_base

    @property
    def name(self) -> str:
        return "search_knowledge"

    @property
    def description(self) -> str:
        return "搜索知识库中的建表语句和业务知识，根据语义相似度返回最相关的结果"

    def get_args_schema(self) -> Type[SearchKnowledgeParams]:
        return SearchKnowledgeParams

    async def execute(self, context: ToolContext, args: SearchKnowledgeParams) -> ToolResult:
        try:
            results = await self._knowledge_base.search_knowledge(
                query=args.query,
                limit=args.limit,
                knowledge_type=args.knowledge_type,
            )

            if not results:
                return ToolResult(
                    success=True,
                    result_for_llm="知识库中未找到与该查询相关的知识。",
                    ui_component=UiComponent(
                        rich_component=StatusBarUpdateComponent(
                            status="idle",
                            message="未找到相关知识",
                            detail="知识库搜索完成",
                        ),
                        simple_component=None,
                    ),
                )

            # 格式化结果供 LLM 使用
            results_text = f"从知识库中找到 {len(results)} 条相关知识：\n\n"
            for i, result in enumerate(results, 1):
                item = result.item
                type_labels_text = {"ddl": "建表语句", "business": "业务知识", "table-connect": "表关联定义"}
                type_label = type_labels_text.get(item.knowledge_type, item.knowledge_type)
                results_text += f"--- 第 {i} 条 [{type_label}] (相似度: {result.similarity_score:.2f}) ---\n"
                if item.title:
                    results_text += f"标题: {item.title}\n"
                results_text += f"内容:\n{item.content}\n\n"

            logger.info(f"知识库搜索结果: {len(results)} 条")

            # 构建 UI 展示
            detail_content = f"**搜索到 {len(results)} 条相关知识：**\n\n"
            for i, result in enumerate(results, 1):
                item = result.item
                type_labels_ui = {"ddl": "📋 建表语句", "business": "📖 业务知识", "table-connect": "🔗 表关联定义"}
                type_label = type_labels_ui.get(item.knowledge_type, f"📄 {item.knowledge_type}")
                detail_content += f"**{i}. {type_label}** (相似度: {result.similarity_score:.2f})\n"
                if item.title:
                    detail_content += f"- 标题: {item.title}\n"
                detail_content += f"- 内容预览: {item.content[:200]}{'...' if len(item.content) > 200 else ''}\n\n"

            return ToolResult(
                success=True,
                result_for_llm=results_text.strip(),
                ui_component=UiComponent(
                    rich_component=CardComponent(
                        title=f"📚 知识库搜索: {len(results)} 条结果",
                        content=detail_content.strip(),
                        icon="🔍",
                        status="info",
                        collapsible=True,
                        collapsed=True,
                        markdown=True,
                    ),
                    simple_component=None,
                ),
            )

        except Exception as e:
            error_msg = f"搜索知识库失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ToolResult(
                success=False,
                result_for_llm=error_msg,
                ui_component=UiComponent(
                    rich_component=StatusBarUpdateComponent(
                        status="error",
                        message="搜索知识库失败",
                        detail=str(e),
                    ),
                    simple_component=None,
                ),
                error=str(e),
            )

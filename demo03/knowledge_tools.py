"""
数仓开发助手知识库工具。

提供保存和搜索两个工具，支持双知识库：
- 表结构知识库：table_name + ddl + source_tables
- 业务文档知识库：content + knowledge_type + title
"""

import logging
from typing import Optional, Type

from pydantic import BaseModel, Field

from vanna.core.tool import Tool, ToolContext, ToolResult
from vanna.components import UiComponent, StatusBarUpdateComponent, CardComponent

from demo03.knowledge_base import DualKnowledgeBaseManager

logger = logging.getLogger(__name__)


# ============================================================
# 保存知识工具
# ============================================================

class SaveKnowledgeParams(BaseModel):
    """保存知识的参数。"""
    # 表结构知识库字段（save_target='schema' 时使用）
    table_name: str = Field(default="", description="库名.表名，如 zijie.dwd_credit_apply_df")
    layer: str = Field(default="", description="所属层级：DWD / MID / DWS / ADS")
    ddl: str = Field(default="", description="建表语句原文")
    source_tables: str = Field(default="", description="来源表，逗号分隔")
    # 业务文档知识库字段（save_target='business' 时使用）
    content: str = Field(default="", description="业务文档内容")
    knowledge_type: str = Field(default="", description="业务知识类型: business/requirement/standard")
    title: str = Field(default="", description="业务文档标题")
    # 目标知识库
    save_target: str = Field(description="目标知识库: 'schema' 表结构库, 'business' 业务文档库")


class SaveKnowledgeTool(Tool[SaveKnowledgeParams]):
    """保存知识到对应知识库的工具。"""

    def __init__(self, kb_manager: DualKnowledgeBaseManager):
        self._kb_manager = kb_manager

    @property
    def name(self) -> str:
        return "save_knowledge"

    @property
    def description(self) -> str:
        return (
            "保存知识到知识库。"
            "save_target='schema' 时保存表结构（需提供 table_name 和 ddl）；"
            "save_target='business' 时保存业务文档（需提供 content 和 knowledge_type）。"
        )

    def get_args_schema(self) -> Type[SaveKnowledgeParams]:
        return SaveKnowledgeParams

    async def execute(self, context: ToolContext, args: SaveKnowledgeParams) -> ToolResult:
        try:
            if args.save_target == "schema":
                if not args.table_name or not args.ddl:
                    return ToolResult(success=False, result_for_llm="保存表结构需要提供 table_name 和 ddl")
                item = await self._kb_manager.save_schema(
                    table_name=args.table_name, ddl=args.ddl,
                    layer=args.layer, source_tables=args.source_tables,
                )
                msg = f"已保存表结构 {item.table_name} 到表结构知识库，ID: {item.knowledge_id}"
                return ToolResult(
                    success=True, result_for_llm=msg,
                    ui_component=UiComponent(
                        rich_component=StatusBarUpdateComponent(
                            status="success", message="已保存表结构", detail=item.table_name,
                        ), simple_component=None,
                    ),
                )
            elif args.save_target == "business":
                if not args.content or not args.knowledge_type:
                    return ToolResult(success=False, result_for_llm="保存业务文档需要提供 content 和 knowledge_type")
                item = await self._kb_manager.save_business(
                    content=args.content, knowledge_type=args.knowledge_type, title=args.title,
                )
                tl = DualKnowledgeBaseManager.TYPE_LABELS.get(args.knowledge_type, args.knowledge_type)
                msg = f"已保存{tl}到业务文档知识库，ID: {item.knowledge_id}"
                return ToolResult(
                    success=True, result_for_llm=msg,
                    ui_component=UiComponent(
                        rich_component=StatusBarUpdateComponent(
                            status="success", message=f"已保存{tl}", detail=args.title or "",
                        ), simple_component=None,
                    ),
                )
            else:
                return ToolResult(success=False, result_for_llm=f"无效的 save_target: {args.save_target}，支持 schema/business")
        except Exception as e:
            logger.error(f"保存知识失败: {e}", exc_info=True)
            return ToolResult(
                success=False, result_for_llm=f"保存知识失败: {str(e)}",
                ui_component=UiComponent(
                    rich_component=StatusBarUpdateComponent(status="error", message="保存失败", detail=str(e)),
                    simple_component=None,
                ), error=str(e),
            )


# ============================================================
# 搜索知识工具
# ============================================================

class SearchKnowledgeParams(BaseModel):
    """搜索知识的参数。"""
    query: str = Field(description="搜索查询文本")
    search_scope: str = Field(
        default="all",
        description="搜索范围: 'all' 全部, 'schema' 仅表结构, 'business' 仅业务文档",
    )
    table_name_filter: Optional[str] = Field(
        default=None,
        description="按表名精确过滤（仅 schema 搜索时有效），如 zijie.dwd_credit_apply_df",
    )
    layer_filter: Optional[str] = Field(
        default=None,
        description="按所属层级过滤（仅 schema 搜索时有效）：DWD / MID / DWS / ADS",
    )
    knowledge_type: Optional[str] = Field(
        default=None,
        description="按业务知识类型过滤（仅 business 搜索时有效）: business/requirement/standard",
    )
    limit: int = Field(default=5, description="最大返回结果数量")


class SearchKnowledgeTool(Tool[SearchKnowledgeParams]):
    """搜索知识库的工具，支持跨库或定向搜索。"""

    def __init__(self, kb_manager: DualKnowledgeBaseManager):
        self._kb_manager = kb_manager

    @property
    def name(self) -> str:
        return "search_knowledge"

    @property
    def description(self) -> str:
        return (
            "搜索知识库。search_scope='schema' 搜表结构（返回 table_name、layer、ddl、source_tables），"
            "'business' 搜业务文档，'all' 同时搜两个库。"
            "可用 layer_filter 按层级过滤（DWD/MID/DWS/ADS）。"
            "开发数仓加工 SQL 时建议先搜表结构再搜业务文档。"
        )

    def get_args_schema(self) -> Type[SearchKnowledgeParams]:
        return SearchKnowledgeParams

    async def execute(self, context: ToolContext, args: SearchKnowledgeParams) -> ToolResult:
        try:
            results_text = ""
            detail_content = ""

            if args.search_scope in ("all", "schema"):
                schema_results = await self._kb_manager.search_schema(
                    query=args.query, limit=args.limit,
                    table_name_filter=args.table_name_filter,
                    layer_filter=args.layer_filter,
                )
                if schema_results:
                    results_text += f"=== 表结构知识库: {len(schema_results)} 条结果 ===\n\n"
                    detail_content += f"**🗄️ 表结构知识库: {len(schema_results)} 条**\n\n"
                    for i, r in enumerate(schema_results, 1):
                        s = r.item
                        sources = s.source_tables if s.source_tables else "无"
                        layer_label = s.layer if s.layer else "未知"
                        results_text += f"--- 第 {i} 条 (相似度: {r.similarity_score:.2f}) ---\n"
                        results_text += f"表名: {s.table_name}\n层级: {layer_label}\n来源表: {sources}\n建表语句:\n{s.ddl}\n\n"
                        ddl_preview = s.ddl[:150].replace('\n', ' ')
                        detail_content += f"**{i}. {s.table_name}** [{layer_label}] (相似度: {r.similarity_score:.2f})\n"
                        detail_content += f"- 来源表: {sources}\n"
                        detail_content += f"- DDL: `{ddl_preview}{'...' if len(s.ddl) > 150 else ''}`\n\n"

            if args.search_scope in ("all", "business"):
                business_results = await self._kb_manager.search_business(
                    query=args.query, limit=args.limit, knowledge_type=args.knowledge_type,
                )
                if business_results:
                    type_labels = DualKnowledgeBaseManager.TYPE_LABELS
                    results_text += f"=== 业务文档知识库: {len(business_results)} 条结果 ===\n\n"
                    detail_content += f"**📖 业务文档知识库: {len(business_results)} 条**\n\n"
                    for i, r in enumerate(business_results, 1):
                        item = r.item
                        tl = type_labels.get(item.knowledge_type, item.knowledge_type)
                        results_text += f"--- 第 {i} 条 [{tl}] (相似度: {r.similarity_score:.2f}) ---\n"
                        if item.title:
                            results_text += f"标题: {item.title}\n"
                        results_text += f"内容:\n{item.content}\n\n"
                        preview = item.content[:200] + ("..." if len(item.content) > 200 else "")
                        detail_content += f"**{i}. {tl}** (相似度: {r.similarity_score:.2f})\n"
                        if item.title:
                            detail_content += f"- 标题: {item.title}\n"
                        detail_content += f"- 内容预览: {preview}\n\n"

            if not results_text:
                return ToolResult(
                    success=True, result_for_llm="知识库中未找到与该查询相关的知识。",
                    ui_component=UiComponent(
                        rich_component=StatusBarUpdateComponent(status="idle", message="未找到相关知识", detail="搜索完成"),
                        simple_component=None,
                    ),
                )

            return ToolResult(
                success=True, result_for_llm=results_text.strip(),
                ui_component=UiComponent(
                    rich_component=CardComponent(
                        title="📚 知识库搜索结果",
                        content=detail_content.strip(),
                        icon="🔍", status="info",
                        collapsible=True, collapsed=True, markdown=True,
                    ), simple_component=None,
                ),
            )
        except Exception as e:
            logger.error(f"搜索知识库失败: {e}", exc_info=True)
            return ToolResult(
                success=False, result_for_llm=f"搜索知识库失败: {str(e)}",
                ui_component=UiComponent(
                    rich_component=StatusBarUpdateComponent(status="error", message="搜索失败", detail=str(e)),
                    simple_component=None,
                ), error=str(e),
            )

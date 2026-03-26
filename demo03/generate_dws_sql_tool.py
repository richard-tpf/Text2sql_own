"""
DWS层SQL生成工具。

提供工具化、规范化的DWS层加工SQL生成能力。
基于输入的字段定义、来源表DDL和加工模式，生成完整的DDL和INSERT OVERWRITE SQL。
"""

import logging
from typing import List, Optional, Type
from enum import Enum

from pydantic import BaseModel, Field

from vanna.core.tool import Tool, ToolContext, ToolResult
from vanna.components import UiComponent, CardComponent, StatusBarUpdateComponent

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class ProcessPattern(str, Enum):
    """DWS层加工模式枚举。"""
    MULTI_CTE_FLAG = "multi_cte_flag"  # 多CTE打标：多个来源表分别打标后聚合
    SINGLE_CTE_FLAG = "single_cte_flag"  # 单CTE flag：单来源表打标后聚合
    DIRECT_AGGREGATE = "direct_aggregate"  # 直接聚合：无需打标，直接聚合计算


class AggregateType(str, Enum):
    """聚合类型枚举。"""
    SUM = "SUM"
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    MAX = "MAX"
    MIN = "MIN"
    AVG = "AVG"
    NONE = "NONE"  # 非聚合字段（维度字段）


# ============================================================
# 数据模型定义
# ============================================================

class FieldDef(BaseModel):
    """字段定义模型。"""
    name: str = Field(description="字段名，使用小写蛇形命名（snake_case）")
    data_type: str = Field(description="字段数据类型，如 STRING、BIGINT、DECIMAL(18,2) 等")
    comment: str = Field(description="字段中文注释说明")
    source_field: Optional[str] = Field(
        default=None,
        description="来源字段表达式，如 'a.user_id' 或 'CASE WHEN ... END'，非聚合字段必填"
    )
    aggregate_type: str = Field(
        default="NONE",
        description="聚合类型：SUM/COUNT/COUNT_DISTINCT/MAX/MIN/AVG/NONE"
    )
    is_dimension: bool = Field(
        default=False,
        description="是否为维度字段（GROUP BY字段）"
    )
    nullable_handling: bool = Field(
        default=True,
        description="聚合时是否使用COALESCE处理空值（仅聚合字段有效）"
    )


class SourceTableDef(BaseModel):
    """来源表定义（从DDL解析）。"""
    table_name: str = Field(description="完整表名，如 zijie.dwd_credit_apply_df")
    alias: str = Field(description="表别名，如 a、b")
    ddl: str = Field(description="原始DDL语句")


class JoinCondition(BaseModel):
    """表关联条件。"""
    left_table_alias: str = Field(description="左表别名")
    right_table_alias: str = Field(description="右表别名")
    join_type: str = Field(default="LEFT JOIN", description="关联类型：LEFT JOIN / INNER JOIN / FULL OUTER JOIN")
    on_condition: str = Field(description="关联条件表达式，如 'a.user_id = b.user_id AND a.ds = b.ds'")


class GenerateDwsSqlParams(BaseModel):
    """生成DWS SQL的参数。"""
    table_name: str = Field(
        description="目标DWS表名，需符合命名规范：zijie.dws_<主题域>_<业务描述>_<时间粒度>_df"
    )
    table_comment: str = Field(
        description="表注释说明"
    )
    fields: List[FieldDef] = Field(
        description="字段定义列表"
    )
    source_ddls: List[str] = Field(
        description="来源表DDL列表"
    )
    source_aliases: List[str] = Field(
        description="来源表别名列表，与source_ddls一一对应，如 ['a', 'b']"
    )
    process_pattern: str = Field(
        description="加工模式：multi_cte_flag（多CTE打标）/ single_cte_flag（单CTE flag）/ direct_aggregate（直接聚合）"
    )
    join_conditions: Optional[List[JoinCondition]] = Field(
        default=None,
        description="表关联条件列表（多表场景必填）"
    )
    where_conditions: Optional[List[str]] = Field(
        default=None,
        description="WHERE过滤条件列表，如 [\"a.ds = '${bizdate}'\", \"a.status = 'SUCCESS'\"]"
    )
    cte_definitions: Optional[List[str]] = Field(
        default=None,
        description="自定义CTE定义列表（multi_cte_flag模式时可用于预定义打标逻辑）"
    )
    partition_field: str = Field(
        default="ds",
        description="分区字段名，默认为 ds"
    )
    partition_value: str = Field(
        default="${bizdate}",
        description="分区值变量，默认为 ${bizdate}"
    )


class GenerateDwsSqlResult(BaseModel):
    """生成结果模型。"""
    ddl: str = Field(description="生成的DDL语句")
    insert_sql: str = Field(description="生成的INSERT OVERWRITE SQL语句")
    validation_notes: List[str] = Field(description="校验和注意事项")


# ============================================================
# DWS SQL 生成工具
# ============================================================

class GenerateDwsSqlTool(Tool[GenerateDwsSqlParams]):
    """
    DWS层SQL生成工具。
    
    基于字段定义、来源表DDL和加工模式，生成规范化的DWS层DDL和INSERT OVERWRITE SQL。
    遵循Hive SQL编写规范，包括：
    - 表名带 zijie. schema 前缀
    - 使用 INSERT OVERWRITE TABLE ... PARTITION 写入分区表
    - LEFT JOIN 后聚合使用 COALESCE 处理空值
    - 除法使用 NULLIF 防止除零
    """

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "generate_dws_sql"

    @property
    def description(self) -> str:
        return (
            "生成DWS层加工SQL。"
            "输入目标表名、字段定义、来源表DDL和加工模式，"
            "输出完整的DDL建表语句和INSERT OVERWRITE加工SQL。"
            "支持三种加工模式：multi_cte_flag（多CTE打标）、single_cte_flag（单CTE flag）、direct_aggregate（直接聚合）。"
        )

    def get_args_schema(self) -> Type[GenerateDwsSqlParams]:
        return GenerateDwsSqlParams

    async def execute(self, context: ToolContext, args: GenerateDwsSqlParams) -> ToolResult:
        """执行DWS SQL生成。"""
        try:
            validation_notes = []
            
            # 1. 校验输入参数
            validation_errors = self._validate_params(args)
            if validation_errors:
                return ToolResult(
                    success=False,
                    result_for_llm=f"参数校验失败：\n" + "\n".join(validation_errors),
                    ui_component=UiComponent(
                        rich_component=StatusBarUpdateComponent(
                            status="error",
                            message="参数校验失败",
                            detail="\n".join(validation_errors)
                        ),
                        simple_component=None
                    ),
                    error="参数校验失败"
                )
            
            # 2. 生成DDL
            ddl = self._generate_ddl(args)
            
            # 3. 根据加工模式生成INSERT SQL
            if args.process_pattern == ProcessPattern.MULTI_CTE_FLAG.value:
                insert_sql = self._generate_multi_cte_sql(args)
                validation_notes.append("多CTE打标模式：请确认各CTE的打标逻辑是否正确")
            elif args.process_pattern == ProcessPattern.SINGLE_CTE_FLAG.value:
                insert_sql = self._generate_single_cte_sql(args)
                validation_notes.append("单CTE flag模式：请确认打标条件是否完整")
            else:  # direct_aggregate
                insert_sql = self._generate_direct_aggregate_sql(args)
                validation_notes.append("直接聚合模式：请确认聚合粒度是否正确")
            
            # 4. 添加通用校验提醒
            validation_notes.extend([
                "请检查：表名是否带 zijie. 前缀",
                "请检查：LEFT JOIN 聚合字段是否使用 COALESCE 处理空值",
                "请检查：分区条件 ds='${bizdate}' 是否在 WHERE 最前面",
                "请检查：字段名是否与来源表一致",
            ])
            
            # 5. 组装完整结果
            full_result = f"""=== DDL 建表语句 ===

{ddl}

=== INSERT OVERWRITE 加工SQL ===

{insert_sql}

=== 校验清单 ===
{chr(10).join(f"- {note}" for note in validation_notes)}
"""
            
            return ToolResult(
                success=True,
                result_for_llm=full_result,
                ui_component=UiComponent(
                    rich_component=CardComponent(
                        title="🛠️ DWS SQL 生成完成",
                        content=f"**目标表**: `{args.table_name}`\n\n"
                                f"**加工模式**: {self._get_pattern_label(args.process_pattern)}\n\n"
                                f"**字段数量**: {len(args.fields)} 个\n\n"
                                f"**来源表数量**: {len(args.source_ddls)} 个\n\n"
                                "---\n\n"
                                "已生成完整的 DDL 和 INSERT OVERWRITE SQL，请查看详情。",
                        icon="✅",
                        status="success",
                        collapsible=True,
                        collapsed=False,
                        markdown=True
                    ),
                    simple_component=None
                ),
                metadata={
                    "table_name": args.table_name,
                    "process_pattern": args.process_pattern,
                    "field_count": len(args.fields),
                    "source_count": len(args.source_ddls),
                }
            )
            
        except Exception as e:
            logger.error(f"生成DWS SQL失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result_for_llm=f"生成DWS SQL失败: {str(e)}",
                ui_component=UiComponent(
                    rich_component=StatusBarUpdateComponent(
                        status="error",
                        message="生成失败",
                        detail=str(e)
                    ),
                    simple_component=None
                ),
                error=str(e)
            )

    def _validate_params(self, args: GenerateDwsSqlParams) -> List[str]:
        """校验输入参数。"""
        errors = []
        
        # 校验表名格式
        if not args.table_name.startswith("zijie.dws_"):
            errors.append(f"表名 '{args.table_name}' 不符合规范，应以 'zijie.dws_' 开头")
        
        if not args.table_name.endswith("_df"):
            errors.append(f"表名 '{args.table_name}' 不符合规范，应以 '_df' 结尾")
        
        # 校验加工模式
        valid_patterns = [p.value for p in ProcessPattern]
        if args.process_pattern not in valid_patterns:
            errors.append(f"无效的加工模式 '{args.process_pattern}'，支持: {valid_patterns}")
        
        # 校验字段
        if not args.fields:
            errors.append("字段定义列表不能为空")
        
        dimension_fields = [f for f in args.fields if f.is_dimension]
        if not dimension_fields:
            errors.append("至少需要一个维度字段（GROUP BY字段）")
        
        # 校验来源表
        if not args.source_ddls:
            errors.append("来源表DDL列表不能为空")
        
        if len(args.source_ddls) != len(args.source_aliases):
            errors.append("来源表DDL数量与别名数量不一致")
        
        # 多表场景校验关联条件
        if len(args.source_ddls) > 1 and not args.join_conditions:
            errors.append("多表场景必须提供关联条件 join_conditions")
        
        return errors

    def _generate_ddl(self, args: GenerateDwsSqlParams) -> str:
        """生成DDL建表语句。"""
        # 构建字段定义
        field_lines = []
        for field in args.fields:
            if field.name == args.partition_field:
                continue  # 分区字段单独处理
            field_lines.append(f"    {field.name} {field.data_type} COMMENT '{field.comment}'")
        
        fields_sql = ",\n".join(field_lines)
        
        # 提取来源表名列表
        source_tables = []
        for ddl, alias in zip(args.source_ddls, args.source_aliases):
            # 简单提取表名（从DDL中）
            table_name = self._extract_table_name_from_ddl(ddl)
            if table_name:
                source_tables.append(table_name)
        source_tables_str = ", ".join(source_tables) if source_tables else "待补充"
        
        ddl = f"""-- DWS层建表语句
-- 来源表: {source_tables_str}
CREATE TABLE IF NOT EXISTS {args.table_name} (
{fields_sql}
) COMMENT '{args.table_comment}'
PARTITIONED BY ({args.partition_field} STRING COMMENT '日期分区')
STORED AS ORC;"""
        
        return ddl

    def _generate_direct_aggregate_sql(self, args: GenerateDwsSqlParams) -> str:
        """生成直接聚合模式的SQL。"""
        # 构建SELECT字段
        select_fields = self._build_select_fields(args)
        
        # 构建FROM子句
        from_clause = self._build_from_clause(args)
        
        # 构建WHERE子句
        where_clause = self._build_where_clause(args)
        
        # 构建GROUP BY子句
        group_by_clause = self._build_group_by_clause(args)
        
        sql = f"""-- DWS层加工SQL（直接聚合模式）
INSERT OVERWRITE TABLE {args.table_name}
PARTITION ({args.partition_field}='{args.partition_value}')
SELECT
{select_fields}
{from_clause}
{where_clause}
{group_by_clause};"""
        
        return sql

    def _generate_single_cte_sql(self, args: GenerateDwsSqlParams) -> str:
        """生成单CTE flag模式的SQL。"""
        # 构建CTE
        cte_name = "flagged_data"
        cte_select = self._build_flag_cte_select(args)
        
        # 构建主查询SELECT字段
        select_fields = self._build_select_fields_from_cte(args, cte_name)
        
        # 构建GROUP BY子句
        group_by_fields = [f.name for f in args.fields if f.is_dimension]
        group_by_clause = "GROUP BY\n    " + ",\n    ".join(group_by_fields)
        
        sql = f"""-- DWS层加工SQL（单CTE flag模式）
WITH {cte_name} AS (
{cte_select}
)
INSERT OVERWRITE TABLE {args.table_name}
PARTITION ({args.partition_field}='{args.partition_value}')
SELECT
{select_fields}
FROM {cte_name}
{group_by_clause};"""
        
        return sql

    def _generate_multi_cte_sql(self, args: GenerateDwsSqlParams) -> str:
        """生成多CTE打标模式的SQL。"""
        # 如果用户提供了自定义CTE，使用用户定义
        if args.cte_definitions:
            cte_block = ",\n\n".join(args.cte_definitions)
        else:
            # 为每个来源表生成CTE
            cte_parts = []
            for i, (ddl, alias) in enumerate(zip(args.source_ddls, args.source_aliases)):
                table_name = self._extract_table_name_from_ddl(ddl)
                cte_name = f"cte_{alias}"
                cte_parts.append(f"""{cte_name} AS (
    -- 来源表 {table_name} 的打标逻辑
    SELECT
        -- TODO: 补充维度字段和打标逻辑
        *
    FROM {table_name or '待补充表名'} {alias}
    WHERE {alias}.{args.partition_field} = '{args.partition_value}'
)""")
            cte_block = ",\n\n".join(cte_parts)
        
        # 构建主查询
        select_fields = self._build_select_fields(args)
        
        # 构建JOIN逻辑
        join_clause = self._build_cte_join_clause(args)
        
        # 构建GROUP BY子句
        group_by_clause = self._build_group_by_clause(args)
        
        sql = f"""-- DWS层加工SQL（多CTE打标模式）
WITH
{cte_block}

INSERT OVERWRITE TABLE {args.table_name}
PARTITION ({args.partition_field}='{args.partition_value}')
SELECT
{select_fields}
{join_clause}
{group_by_clause};"""
        
        return sql

    def _build_select_fields(self, args: GenerateDwsSqlParams) -> str:
        """构建SELECT字段列表。"""
        field_lines = []
        for field in args.fields:
            if field.name == args.partition_field:
                continue
            
            if field.is_dimension:
                # 维度字段
                source = field.source_field or field.name
                field_lines.append(f"    {source} AS {field.name}")
            else:
                # 聚合字段
                source = field.source_field or field.name
                agg_type = field.aggregate_type.upper()
                
                if agg_type == "NONE":
                    field_lines.append(f"    {source} AS {field.name}")
                elif agg_type == "COUNT_DISTINCT":
                    field_lines.append(f"    COUNT(DISTINCT {source}) AS {field.name}")
                elif agg_type in ("SUM", "COUNT", "MAX", "MIN", "AVG"):
                    if field.nullable_handling and agg_type == "SUM":
                        field_lines.append(f"    SUM(COALESCE({source}, 0)) AS {field.name}")
                    else:
                        field_lines.append(f"    {agg_type}({source}) AS {field.name}")
                else:
                    field_lines.append(f"    {agg_type}({source}) AS {field.name}")
        
        return ",\n".join(field_lines)

    def _build_select_fields_from_cte(self, args: GenerateDwsSqlParams, cte_name: str) -> str:
        """从CTE构建SELECT字段列表。"""
        field_lines = []
        for field in args.fields:
            if field.name == args.partition_field:
                continue
            
            if field.is_dimension:
                field_lines.append(f"    {cte_name}.{field.name}")
            else:
                agg_type = field.aggregate_type.upper()
                source = f"{cte_name}.{field.source_field}" if field.source_field else f"{cte_name}.{field.name}"
                
                if agg_type == "NONE":
                    field_lines.append(f"    {source} AS {field.name}")
                elif agg_type == "COUNT_DISTINCT":
                    field_lines.append(f"    COUNT(DISTINCT {source}) AS {field.name}")
                elif agg_type in ("SUM", "COUNT", "MAX", "MIN", "AVG"):
                    if field.nullable_handling and agg_type == "SUM":
                        field_lines.append(f"    SUM(COALESCE({source}, 0)) AS {field.name}")
                    else:
                        field_lines.append(f"    {agg_type}({source}) AS {field.name}")
                else:
                    field_lines.append(f"    {agg_type}({source}) AS {field.name}")
        
        return ",\n".join(field_lines)

    def _build_flag_cte_select(self, args: GenerateDwsSqlParams) -> str:
        """构建打标CTE的SELECT语句。"""
        # 获取第一个来源表
        if args.source_ddls:
            table_name = self._extract_table_name_from_ddl(args.source_ddls[0])
            alias = args.source_aliases[0] if args.source_aliases else "a"
        else:
            table_name = "待补充表名"
            alias = "a"
        
        # 构建字段
        field_lines = []
        for field in args.fields:
            if field.name == args.partition_field:
                continue
            if field.is_dimension:
                source = field.source_field or f"{alias}.{field.name}"
                field_lines.append(f"        {source} AS {field.name}")
            else:
                # 非维度字段，可能需要打标
                source = field.source_field or f"1"  # 默认打标值为1
                field_lines.append(f"        {source} AS {field.name}")
        
        fields_sql = ",\n".join(field_lines)
        where_clause = self._build_where_clause(args).strip()
        if not where_clause:
            where_clause = f"WHERE {alias}.{args.partition_field} = '{args.partition_value}'"
        
        return f"""    SELECT
{fields_sql}
    FROM {table_name or '待补充表名'} {alias}
    {where_clause}"""

    def _build_from_clause(self, args: GenerateDwsSqlParams) -> str:
        """构建FROM子句。"""
        if not args.source_ddls:
            return "FROM 待补充表名"
        
        # 第一个表
        first_table = self._extract_table_name_from_ddl(args.source_ddls[0])
        first_alias = args.source_aliases[0] if args.source_aliases else "a"
        from_parts = [f"FROM {first_table or '待补充表名'} {first_alias}"]
        
        # JOIN子句
        if args.join_conditions:
            for join in args.join_conditions:
                # 找到对应的表名
                right_idx = args.source_aliases.index(join.right_table_alias) if join.right_table_alias in args.source_aliases else -1
                if right_idx >= 0 and right_idx < len(args.source_ddls):
                    right_table = self._extract_table_name_from_ddl(args.source_ddls[right_idx])
                else:
                    right_table = "待补充表名"
                from_parts.append(f"{join.join_type} {right_table or '待补充表名'} {join.right_table_alias}")
                from_parts.append(f"    ON {join.on_condition}")
        
        return "\n".join(from_parts)

    def _build_cte_join_clause(self, args: GenerateDwsSqlParams) -> str:
        """构建CTE JOIN子句。"""
        if len(args.source_aliases) == 1:
            return f"FROM cte_{args.source_aliases[0]}"
        
        parts = [f"FROM cte_{args.source_aliases[0]}"]
        
        if args.join_conditions:
            for join in args.join_conditions:
                left_cte = f"cte_{join.left_table_alias}"
                right_cte = f"cte_{join.right_table_alias}"
                # 替换关联条件中的别名
                on_condition = join.on_condition
                for alias in args.source_aliases:
                    on_condition = on_condition.replace(f"{alias}.", f"cte_{alias}.")
                parts.append(f"{join.join_type} {right_cte}")
                parts.append(f"    ON {on_condition}")
        else:
            # 默认生成JOIN提示
            for alias in args.source_aliases[1:]:
                parts.append(f"LEFT JOIN cte_{alias}")
                parts.append(f"    ON /* TODO: 补充关联条件 */")
        
        return "\n".join(parts)

    def _build_where_clause(self, args: GenerateDwsSqlParams) -> str:
        """构建WHERE子句。"""
        conditions = []
        
        # 分区条件放在最前面
        first_alias = args.source_aliases[0] if args.source_aliases else "a"
        conditions.append(f"{first_alias}.{args.partition_field} = '{args.partition_value}'")
        
        # 用户自定义条件
        if args.where_conditions:
            conditions.extend(args.where_conditions)
        
        return "WHERE\n    " + "\n    AND ".join(conditions)

    def _build_group_by_clause(self, args: GenerateDwsSqlParams) -> str:
        """构建GROUP BY子句。"""
        dimension_fields = []
        for field in args.fields:
            if field.is_dimension and field.name != args.partition_field:
                source = field.source_field or field.name
                dimension_fields.append(source)
        
        if not dimension_fields:
            return ""
        
        return "GROUP BY\n    " + ",\n    ".join(dimension_fields)

    def _extract_table_name_from_ddl(self, ddl: str) -> Optional[str]:
        """从DDL中提取表名。"""
        import re
        # 匹配 CREATE TABLE [IF NOT EXISTS] table_name
        match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\S+)', ddl, re.IGNORECASE)
        if match:
            table_name = match.group(1).strip('`"')
            return table_name
        return None

    def _get_pattern_label(self, pattern: str) -> str:
        """获取加工模式的中文标签。"""
        labels = {
            ProcessPattern.MULTI_CTE_FLAG.value: "多CTE打标",
            ProcessPattern.SINGLE_CTE_FLAG.value: "单CTE flag",
            ProcessPattern.DIRECT_AGGREGATE.value: "直接聚合",
        }
        return labels.get(pattern, pattern)

"""
ADS层SQL生成工具。

提供工具化、规范化的ADS层加工SQL生成能力。
基于输入的目标表名、时间粒度和来源DWS表，生成完整的DDL和INSERT OVERWRITE SQL。
ADS层为应用数据层，从DWS层汇总数据，面向具体应用场景。
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

class TimeGranularity(str, Enum):
    """时间粒度枚举。"""
    DAY = "day"      # 日粒度
    WEEK = "week"    # 周粒度
    MONTH = "month"  # 月粒度


class AdsAggregateType(str, Enum):
    """ADS层聚合类型枚举。"""
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

class AdsFieldDef(BaseModel):
    """ADS层字段定义模型。"""
    name: str = Field(description="字段名，使用小写蛇形命名（snake_case）")
    data_type: str = Field(description="字段数据类型，如 STRING、BIGINT、DECIMAL(18,2) 等")
    comment: str = Field(description="字段中文注释说明")
    source_field: Optional[str] = Field(
        default=None,
        description="来源字段表达式，如 'dws.user_id' 或 'CASE WHEN ... END'"
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


class GenerateAdsSqlParams(BaseModel):
    """生成ADS SQL的参数。"""
    table_name: str = Field(
        description="目标ADS表名，需符合命名规范：zijie.ads_<主题域>_<业务描述>_<时间粒度>_df"
    )
    time_granularity: str = Field(
        description="时间粒度: day/week/month"
    )
    dws_table: str = Field(
        description="来源DWS表名，如 zijie.dws_credit_user_stats_df"
    )
    table_comment: Optional[str] = Field(
        default=None,
        description="表注释说明，不填则自动生成"
    )
    fields: Optional[List[AdsFieldDef]] = Field(
        default=None,
        description="字段定义列表，不填则生成示例模板"
    )
    where_conditions: Optional[List[str]] = Field(
        default=None,
        description="WHERE过滤条件列表，如 [\"dws.status = 'ACTIVE'\"]"
    )
    partition_field: str = Field(
        default="ds",
        description="分区字段名，默认为 ds"
    )
    partition_value: str = Field(
        default="${bizdate}",
        description="分区值变量，默认为 ${bizdate}"
    )
    time_dimension_field: Optional[str] = Field(
        default=None,
        description="用于时间粒度聚合的日期字段，默认为分区字段"
    )


class GenerateAdsSqlResult(BaseModel):
    """生成结果模型。"""
    ddl: str = Field(description="生成的DDL语句")
    insert_sql: str = Field(description="生成的INSERT OVERWRITE SQL语句")
    validation_notes: List[str] = Field(description="校验和注意事项")


# ============================================================
# ADS SQL 生成工具
# ============================================================

class GenerateAdsSqlTool(Tool[GenerateAdsSqlParams]):
    """
    ADS层SQL生成工具。
    
    基于目标表名、时间粒度和来源DWS表，生成规范化的ADS层DDL和INSERT OVERWRITE SQL。
    遵循Hive SQL编写规范，包括：
    - 表名带 zijie. schema 前缀
    - 使用 INSERT OVERWRITE TABLE ... PARTITION 写入分区表
    - 支持日/周/月不同时间粒度的聚合
    - 聚合使用 COALESCE 处理空值
    - 除法使用 NULLIF 防止除零
    """

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "generate_ads_sql"

    @property
    def description(self) -> str:
        return (
            "生成ADS层加工SQL。"
            "输入目标表名、时间粒度（day/week/month）和来源DWS表，"
            "输出完整的DDL建表语句和INSERT OVERWRITE加工SQL。"
            "ADS层为应用数据层，从DWS层聚合汇总数据，面向具体业务应用场景。"
        )

    def get_args_schema(self) -> Type[GenerateAdsSqlParams]:
        return GenerateAdsSqlParams

    async def execute(self, context: ToolContext, args: GenerateAdsSqlParams) -> ToolResult:
        """执行ADS SQL生成。"""
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
            
            # 2. 如果没有提供字段定义，生成示例模板
            if not args.fields:
                template_result = self._generate_template(args)
                return ToolResult(
                    success=True,
                    result_for_llm=template_result,
                    ui_component=UiComponent(
                        rich_component=CardComponent(
                            title="📋 ADS SQL 模板已生成",
                            content=f"**目标表**: `{args.table_name}`\n\n"
                                    f"**时间粒度**: {self._get_granularity_label(args.time_granularity)}\n\n"
                                    f"**来源表**: `{args.dws_table}`\n\n"
                                    "---\n\n"
                                    "已生成 ADS 层 SQL 模板，请根据实际需求补充字段定义后重新调用。",
                            icon="📝",
                            status="info",
                            collapsible=True,
                            collapsed=False,
                            markdown=True
                        ),
                        simple_component=None
                    ),
                    metadata={
                        "table_name": args.table_name,
                        "time_granularity": args.time_granularity,
                        "is_template": True,
                    }
                )
            
            # 3. 生成DDL
            ddl = self._generate_ddl(args)
            
            # 4. 根据时间粒度生成INSERT SQL
            insert_sql = self._generate_insert_sql(args)
            
            # 5. 添加校验提醒
            validation_notes.extend([
                f"时间粒度: {self._get_granularity_label(args.time_granularity)}",
                "请检查：表名是否带 zijie. 前缀",
                "请检查：ADS表名是否以 'zijie.ads_' 开头",
                "请检查：聚合字段是否使用 COALESCE 处理空值",
                "请检查：分区条件 ds='${bizdate}' 是否正确",
                "请检查：字段名是否与来源DWS表一致",
            ])
            
            if args.time_granularity == TimeGranularity.WEEK.value:
                validation_notes.append("周粒度：请确认周的起始日（默认周一）是否符合业务需求")
            elif args.time_granularity == TimeGranularity.MONTH.value:
                validation_notes.append("月粒度：请确认是否需要处理跨月数据")
            
            # 6. 组装完整结果
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
                        title="🛠️ ADS SQL 生成完成",
                        content=f"**目标表**: `{args.table_name}`\n\n"
                                f"**时间粒度**: {self._get_granularity_label(args.time_granularity)}\n\n"
                                f"**来源DWS表**: `{args.dws_table}`\n\n"
                                f"**字段数量**: {len(args.fields)} 个\n\n"
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
                    "time_granularity": args.time_granularity,
                    "dws_table": args.dws_table,
                    "field_count": len(args.fields),
                }
            )
            
        except Exception as e:
            logger.error(f"生成ADS SQL失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result_for_llm=f"生成ADS SQL失败: {str(e)}",
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

    def _validate_params(self, args: GenerateAdsSqlParams) -> List[str]:
        """校验输入参数。"""
        errors = []
        
        # 校验表名格式
        if not args.table_name.startswith("zijie.ads_"):
            errors.append(f"表名 '{args.table_name}' 不符合规范，应以 'zijie.ads_' 开头")
        
        if not args.table_name.endswith("_df"):
            errors.append(f"表名 '{args.table_name}' 不符合规范，应以 '_df' 结尾")
        
        # 校验时间粒度
        valid_granularities = [g.value for g in TimeGranularity]
        if args.time_granularity not in valid_granularities:
            errors.append(f"无效的时间粒度 '{args.time_granularity}'，支持: {valid_granularities}")
        
        # 校验来源DWS表
        if not args.dws_table:
            errors.append("来源DWS表名不能为空")
        elif not args.dws_table.startswith("zijie."):
            errors.append(f"来源DWS表名 '{args.dws_table}' 应带 'zijie.' 前缀")
        
        # 校验字段（如果提供了）
        if args.fields:
            dimension_fields = [f for f in args.fields if f.is_dimension]
            if not dimension_fields:
                errors.append("至少需要一个维度字段（GROUP BY字段）")
        
        return errors

    def _generate_template(self, args: GenerateAdsSqlParams) -> str:
        """生成ADS层SQL模板（未提供字段定义时）。"""
        granularity_label = self._get_granularity_label(args.time_granularity)
        time_field = args.time_dimension_field or args.partition_field
        
        # 根据时间粒度生成时间维度字段
        if args.time_granularity == TimeGranularity.DAY.value:
            time_dim_expr = f"dws.{time_field}"
            time_dim_name = "stat_date"
            time_dim_comment = "统计日期"
        elif args.time_granularity == TimeGranularity.WEEK.value:
            time_dim_expr = f"DATE_FORMAT(DATE_SUB(dws.{time_field}, PMOD(DATEDIFF(dws.{time_field}, '1900-01-01'), 7)), 'yyyy-MM-dd')"
            time_dim_name = "stat_week"
            time_dim_comment = "统计周（周一日期）"
        else:  # month
            time_dim_expr = f"DATE_FORMAT(dws.{time_field}, 'yyyy-MM')"
            time_dim_name = "stat_month"
            time_dim_comment = "统计月（yyyy-MM）"
        
        table_comment = args.table_comment or f"ADS层{granularity_label}汇总表"
        
        template = f"""=== ADS 层 SQL 模板 ===

【说明】
- 目标表: {args.table_name}
- 时间粒度: {granularity_label}
- 来源DWS表: {args.dws_table}

请根据以下模板，补充字段定义后重新调用工具。

---

【字段定义示例】

fields = [
    # 时间维度字段（必须）
    AdsFieldDef(
        name="{time_dim_name}",
        data_type="STRING",
        comment="{time_dim_comment}",
        source_field="{time_dim_expr}",
        is_dimension=True
    ),
    # 业务维度字段（按需添加）
    AdsFieldDef(
        name="业务维度字段名",
        data_type="STRING",
        comment="业务维度注释",
        source_field="dws.字段名",
        is_dimension=True
    ),
    # 指标字段（聚合字段）
    AdsFieldDef(
        name="指标字段名",
        data_type="BIGINT",
        comment="指标注释",
        source_field="dws.来源字段",
        aggregate_type="SUM"
    ),
]

---

【DDL 模板】

CREATE TABLE IF NOT EXISTS {args.table_name} (
    {time_dim_name} STRING COMMENT '{time_dim_comment}',
    -- TODO: 添加业务维度字段
    -- TODO: 添加指标字段
) COMMENT '{table_comment}'
PARTITIONED BY ({args.partition_field} STRING COMMENT '日期分区')
STORED AS ORC;

---

【INSERT SQL 模板】

INSERT OVERWRITE TABLE {args.table_name}
PARTITION ({args.partition_field}='{args.partition_value}')
SELECT
    {time_dim_expr} AS {time_dim_name},
    -- TODO: 添加业务维度字段
    -- TODO: 添加聚合指标
FROM {args.dws_table} dws
WHERE dws.{args.partition_field} = '{args.partition_value}'
GROUP BY
    {time_dim_expr}
    -- TODO: 添加业务维度字段
;
"""
        return template

    def _generate_ddl(self, args: GenerateAdsSqlParams) -> str:
        """生成DDL建表语句。"""
        # 构建字段定义
        field_lines = []
        for field in args.fields:
            if field.name == args.partition_field:
                continue  # 分区字段单独处理
            field_lines.append(f"    {field.name} {field.data_type} COMMENT '{field.comment}'")
        
        fields_sql = ",\n".join(field_lines)
        
        table_comment = args.table_comment or f"ADS层{self._get_granularity_label(args.time_granularity)}汇总表"
        
        ddl = f"""-- ADS层建表语句
-- 来源表: {args.dws_table}
-- 时间粒度: {self._get_granularity_label(args.time_granularity)}
CREATE TABLE IF NOT EXISTS {args.table_name} (
{fields_sql}
) COMMENT '{table_comment}'
PARTITIONED BY ({args.partition_field} STRING COMMENT '日期分区')
STORED AS ORC;"""
        
        return ddl

    def _generate_insert_sql(self, args: GenerateAdsSqlParams) -> str:
        """生成INSERT OVERWRITE SQL。"""
        time_field = args.time_dimension_field or args.partition_field
        granularity = args.time_granularity
        
        # 构建SELECT字段
        select_fields = self._build_select_fields(args)
        
        # 构建WHERE子句
        where_clause = self._build_where_clause(args)
        
        # 构建GROUP BY子句
        group_by_clause = self._build_group_by_clause(args)
        
        # 添加时间粒度相关的注释
        granularity_comment = self._get_granularity_sql_comment(granularity, time_field)
        
        sql = f"""-- ADS层加工SQL（{self._get_granularity_label(granularity)}粒度）
{granularity_comment}
INSERT OVERWRITE TABLE {args.table_name}
PARTITION ({args.partition_field}='{args.partition_value}')
SELECT
{select_fields}
FROM {args.dws_table} dws
{where_clause}
{group_by_clause};"""
        
        return sql

    def _build_select_fields(self, args: GenerateAdsSqlParams) -> str:
        """构建SELECT字段列表。"""
        field_lines = []
        for field in args.fields:
            if field.name == args.partition_field:
                continue
            
            if field.is_dimension:
                # 维度字段
                source = field.source_field or f"dws.{field.name}"
                field_lines.append(f"    {source} AS {field.name}")
            else:
                # 聚合字段
                source = field.source_field or f"dws.{field.name}"
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

    def _build_where_clause(self, args: GenerateAdsSqlParams) -> str:
        """构建WHERE子句。"""
        conditions = []
        
        # 分区条件放在最前面
        conditions.append(f"dws.{args.partition_field} = '{args.partition_value}'")
        
        # 用户自定义条件
        if args.where_conditions:
            conditions.extend(args.where_conditions)
        
        return "WHERE\n    " + "\n    AND ".join(conditions)

    def _build_group_by_clause(self, args: GenerateAdsSqlParams) -> str:
        """构建GROUP BY子句。"""
        dimension_fields = []
        for field in args.fields:
            if field.is_dimension and field.name != args.partition_field:
                source = field.source_field or f"dws.{field.name}"
                dimension_fields.append(source)
        
        if not dimension_fields:
            return ""
        
        return "GROUP BY\n    " + ",\n    ".join(dimension_fields)

    def _get_granularity_label(self, granularity: str) -> str:
        """获取时间粒度的中文标签。"""
        labels = {
            TimeGranularity.DAY.value: "日",
            TimeGranularity.WEEK.value: "周",
            TimeGranularity.MONTH.value: "月",
        }
        return labels.get(granularity, granularity)

    def _get_granularity_sql_comment(self, granularity: str, time_field: str) -> str:
        """获取时间粒度相关的SQL注释。"""
        if granularity == TimeGranularity.DAY.value:
            return f"-- 日粒度聚合：按 {time_field} 字段直接聚合"
        elif granularity == TimeGranularity.WEEK.value:
            return f"""-- 周粒度聚合：按周一日期聚合
-- 周一计算公式：DATE_SUB({time_field}, PMOD(DATEDIFF({time_field}, '1900-01-01'), 7))"""
        else:  # month
            return f"""-- 月粒度聚合：按月份聚合
-- 月份格式：DATE_FORMAT({time_field}, 'yyyy-MM')"""

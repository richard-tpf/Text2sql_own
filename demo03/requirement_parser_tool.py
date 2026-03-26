"""
需求文档解析工具。

从需求文档中提取结构化的指标定义信息，输出：
- 需求概述（名称、背景）
- 指标定义列表（指标名称、字段性质、统计方式、取值来源、取值规则、展示格式、备注）
- 涉及的表/字段清单（供后续验证工具使用）
- 解析状态和潜在问题

解析结果为结构化 JSON，便于后续流程自动化处理。
"""

import logging
import re
from typing import List, Optional, Type, Dict, Any

from pydantic import BaseModel, Field

from vanna.core.tool import Tool, ToolContext, ToolResult
from vanna.components import UiComponent, CardComponent, StatusBarUpdateComponent

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型定义
# ============================================================

class SourceReference(BaseModel):
    """取值来源引用。"""
    table_name: str = Field(default="", description="来源表名")
    fields: List[str] = Field(default_factory=list, description="涉及字段列表")
    join_condition: str = Field(default="", description="关联条件（多表时）")
    raw_text: str = Field(default="", description="原始取值来源文本")


class MetricDefinition(BaseModel):
    """指标定义。"""
    metric_name: str = Field(description="指标名称")
    field_type: str = Field(
        default="",
        description="字段性质: 维度/原子指标/派生指标/复合指标"
    )
    aggregation_method: str = Field(
        default="",
        description="统计方式: 计数/计数（去重）/求和/平均值/最大值/最小值/比率/—"
    )
    source_reference: SourceReference = Field(
        default_factory=SourceReference,
        description="取值来源"
    )
    calculation_rule: str = Field(default="", description="取值规则/计算公式")
    display_format: str = Field(default="", description="展示格式")
    remarks: str = Field(default="", description="备注")
    # 解析状态
    has_issues: bool = Field(default=False, description="是否存在解析问题")
    issues: List[str] = Field(default_factory=list, description="解析问题列表")


class RequirementOverview(BaseModel):
    """需求概述。"""
    requirement_name: str = Field(default="", description="需求名称")
    requirement_background: str = Field(default="", description="需求背景")
    requester: str = Field(default="", description="需求提出人")
    expected_date: str = Field(default="", description="期望上线日期")
    other_notes: str = Field(default="", description="其他说明")


class ParsedRequirementDoc(BaseModel):
    """解析后的需求文档。"""
    overview: RequirementOverview = Field(description="需求概述")
    metrics: List[MetricDefinition] = Field(default_factory=list, description="指标定义列表")
    # 汇总信息（供后续验证工具使用）
    all_source_tables: List[str] = Field(default_factory=list, description="所有涉及的来源表")
    all_source_fields: List[str] = Field(default_factory=list, description="所有涉及的字段")
    dimension_count: int = Field(default=0, description="维度数量")
    atomic_metric_count: int = Field(default=0, description="原子指标数量")
    derived_metric_count: int = Field(default=0, description="派生指标数量")
    # 解析状态
    parse_success: bool = Field(default=True, description="解析是否成功")
    parse_warnings: List[str] = Field(default_factory=list, description="解析警告")


# ============================================================
# 工具参数定义
# ============================================================

class ParseRequirementParams(BaseModel):
    """解析需求文档的参数。"""
    document: str = Field(description="需求文档原文（Markdown 格式）")
    strict_mode: bool = Field(
        default=False,
        description="严格模式：为 True 时，取值来源为空的指标标记为异常"
    )


# ============================================================
# 解析逻辑
# ============================================================

class RequirementDocParser:
    """需求文档解析器。"""

    # 字段性质标准值
    FIELD_TYPES = {"维度", "原子指标", "派生指标", "复合指标"}

    # 统计方式标准值
    AGGREGATION_METHODS = {
        "计数", "计数（去重）", "计数(去重)", "去重计数",
        "求和", "sum", "SUM",
        "平均值", "avg", "AVG", "平均",
        "最大值", "max", "MAX",
        "最小值", "min", "MIN",
        "比率", "比例", "占比",
        "—", "-", ""
    }

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.warnings: List[str] = []

    def parse(self, document: str) -> ParsedRequirementDoc:
        """解析需求文档。"""
        self.warnings = []

        overview = self._parse_overview(document)
        metrics = self._parse_metrics_table(document)
        other_notes = self._parse_other_notes(document)
        overview.other_notes = other_notes

        # 汇总统计
        all_tables = set()
        all_fields = set()
        dim_count = 0
        atomic_count = 0
        derived_count = 0

        for m in metrics:
            # 收集表和字段
            if m.source_reference.table_name:
                for t in m.source_reference.table_name.split("、"):
                    all_tables.add(t.strip().strip("`").strip("'").strip('"'))
            for f in m.source_reference.fields:
                all_fields.add(f.strip().strip("`").strip("'").strip('"'))

            # 统计各类型数量
            if m.field_type == "维度":
                dim_count += 1
            elif m.field_type == "原子指标":
                atomic_count += 1
            elif m.field_type in ("派生指标", "复合指标"):
                derived_count += 1

        return ParsedRequirementDoc(
            overview=overview,
            metrics=metrics,
            all_source_tables=sorted(list(all_tables)),
            all_source_fields=sorted(list(all_fields)),
            dimension_count=dim_count,
            atomic_metric_count=atomic_count,
            derived_metric_count=derived_count,
            parse_success=True,
            parse_warnings=self.warnings,
        )

    def _parse_overview(self, document: str) -> RequirementOverview:
        """解析需求概述部分。"""
        overview = RequirementOverview()

        # 解析需求名称
        name_match = re.search(r"\*\*需求名称\*\*[：:]\s*(.+?)(?:\n|$)", document)
        if name_match:
            overview.requirement_name = name_match.group(1).strip()
        else:
            # 尝试从标题提取
            title_match = re.search(r"^#\s+(.+?)(?:\n|$)", document, re.MULTILINE)
            if title_match:
                overview.requirement_name = title_match.group(1).strip()

        # 解析需求背景
        bg_match = re.search(r"\*\*需求背景\*\*[：:]\s*(.+?)(?:\n-|\n#|\n---|\Z)", document, re.DOTALL)
        if bg_match:
            overview.requirement_background = bg_match.group(1).strip()

        # 解析需求提出人
        requester_match = re.search(r"\*\*需求提出人\*\*[：:]\s*(.+?)(?:\n|$)", document)
        if requester_match:
            overview.requester = requester_match.group(1).strip()

        # 解析期望上线日期
        date_match = re.search(r"\*\*期望上线日期\*\*[：:]\s*(.+?)(?:\n|$)", document)
        if date_match:
            overview.expected_date = date_match.group(1).strip()

        return overview

    def _parse_metrics_table(self, document: str) -> List[MetricDefinition]:
        """解析指标定义表格。"""
        metrics = []

        # 按行分割文档
        lines = document.split("\n")
        
        # 查找表格行（以 | 开头的行）
        table_lines = []
        in_table = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                table_lines.append(stripped)
                in_table = True
            elif in_table and stripped.startswith("|"):
                # 可能是没有结尾 | 的行
                table_lines.append(stripped)
            elif in_table and not stripped.startswith("|"):
                # 表格结束
                if table_lines:
                    break

        if not table_lines:
            self.warnings.append("未找到指标定义表格")
            return metrics

        # 至少需要表头 + 分隔行 + 1行数据
        if len(table_lines) < 3:
            self.warnings.append(f"指标定义表格行数不足，仅有 {len(table_lines)} 行")
            return metrics

        # 解析表头
        header_line = table_lines[0]
        headers = [h.strip() for h in header_line.split("|") if h.strip()]
        
        # 检查是否包含必需的列
        if "指标名称" not in headers:
            self.warnings.append(f"表格表头缺少'指标名称'列，当前表头: {headers}")
            return metrics

        # 跳过分隔行（第2行通常是 |---|---|...）
        # 检测分隔行
        separator_idx = 1
        if len(table_lines) > 1 and re.match(r"^\|[\s\-:|]+\|$", table_lines[1]):
            separator_idx = 1
        else:
            self.warnings.append("未找到表格分隔行")
            separator_idx = 0  # 没有分隔行，直接从第2行开始

        data_lines = table_lines[separator_idx + 1:]

        for line_num, line in enumerate(data_lines, start=separator_idx + 2):
            if not line.strip() or line.strip() == "|":
                continue

            # 分割单元格，注意处理空单元格
            # 移除首尾的 |
            inner = line.strip()
            if inner.startswith("|"):
                inner = inner[1:]
            if inner.endswith("|"):
                inner = inner[:-1]
            
            cells = inner.split("|")
            cells = [c.strip() for c in cells]

            if len(cells) < 2:
                continue

            # 跳过占位行（如"（补充指标）"）
            first_cell = cells[0] if cells else ""
            if first_cell.startswith("（") or first_cell.startswith("("):
                continue
            
            # 跳过空行或分隔行
            if all(c in ("-", "—", "") or re.match(r"^[:\-]+$", c) for c in cells):
                continue

            metric = self._parse_metric_row(headers, cells, line_num)
            if metric:
                metrics.append(metric)

        if not metrics:
            self.warnings.append(f"未解析到有效的指标定义，共处理 {len(data_lines)} 行数据")

        return metrics

    def _parse_metric_row(
        self, headers: List[str], cells: List[str], line_num: int
    ) -> Optional[MetricDefinition]:
        """解析单行指标定义。"""
        # 创建表头到单元格的映射
        cell_map: Dict[str, str] = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                cell_map[header] = cells[i]
            else:
                cell_map[header] = ""

        metric_name = cell_map.get("指标名称", "").strip()
        if not metric_name:
            return None

        # 解析各字段
        field_type = cell_map.get("字段性质", "").strip()
        aggregation = cell_map.get("统计方式", "").strip()
        source_raw = cell_map.get("取值来源", "").strip()
        calc_rule = cell_map.get("取值规则", "").strip()
        display_fmt = cell_map.get("展示格式", "").strip()
        remarks = cell_map.get("备注", "").strip()

        # 解析取值来源
        source_ref = self._parse_source_reference(source_raw)

        # 验证并记录问题
        issues = []
        has_issues = False

        # 字段性质验证
        if field_type and field_type not in self.FIELD_TYPES:
            issues.append(f"字段性质 '{field_type}' 不在标准值范围内")

        # 取值来源验证
        if self.strict_mode:
            if not source_ref.table_name and field_type != "维度":
                issues.append("取值来源为空，无法追溯数据来源")
                has_issues = True

        # 派生指标需要有计算公式
        if field_type in ("派生指标", "复合指标") and not calc_rule:
            issues.append("派生指标缺少取值规则/计算公式")

        # 构建指标定义
        return MetricDefinition(
            metric_name=metric_name,
            field_type=field_type,
            aggregation_method=aggregation,
            source_reference=source_ref,
            calculation_rule=calc_rule,
            display_format=display_fmt,
            remarks=remarks,
            has_issues=has_issues,
            issues=issues,
        )

    def _parse_source_reference(self, raw_text: str) -> SourceReference:
        """解析取值来源文本。

        支持格式：
        - 来源表：`表名`；字段：`字段名`
        - 来源表：`表A`、`表B`；字段：`字段1`、`字段2`
        - 来源表：`表A` LEFT JOIN `表B` ON ...
        - 同"其他指标名"
        """
        ref = SourceReference(raw_text=raw_text)

        if not raw_text or raw_text in ("—", "-", "同上"):
            return ref

        # 提取来源表
        table_match = re.search(r"来源表[：:]\s*(.+?)(?:；|;|$)", raw_text)
        if table_match:
            table_text = table_match.group(1).strip()
            # 处理多表情况
            tables = []
            # 匹配反引号包裹的表名
            backtick_tables = re.findall(r"`([^`]+)`", table_text)
            if backtick_tables:
                tables.extend(backtick_tables)
            else:
                # 尝试匹配中文表名
                chinese_tables = re.findall(r"[\u4e00-\u9fa5]+[表]", table_text)
                if chinese_tables:
                    tables.extend(chinese_tables)
                else:
                    # 按顿号或逗号分割
                    tables = [t.strip() for t in re.split(r"[、,，]", table_text) if t.strip()]

            ref.table_name = "、".join(tables)

        # 提取字段
        field_match = re.search(r"字段[：:]\s*(.+?)(?:；|;|关联|$)", raw_text)
        if field_match:
            field_text = field_match.group(1).strip()
            # 匹配反引号包裹的字段
            backtick_fields = re.findall(r"`([^`]+)`", field_text)
            if backtick_fields:
                ref.fields = backtick_fields
            else:
                # 按顿号或逗号分割
                ref.fields = [f.strip() for f in re.split(r"[、,，]", field_text) if f.strip()]

        # 提取关联条件
        join_match = re.search(r"关联方式[：:]\s*(.+?)(?:；|;|$)", raw_text)
        if join_match:
            ref.join_condition = join_match.group(1).strip()
        else:
            # 尝试匹配 JOIN ON 格式
            join_on_match = re.search(r"((?:LEFT|RIGHT|INNER|FULL)?\s*JOIN\s+.+?\s+ON\s+.+?)(?:；|;|字段|$)", raw_text, re.IGNORECASE)
            if join_on_match:
                ref.join_condition = join_on_match.group(1).strip()

        return ref

    def _parse_other_notes(self, document: str) -> str:
        """解析其他说明部分。"""
        # 查找 "## 三、其他说明" 或类似标题后的内容
        notes_match = re.search(
            r"##\s*(?:三、)?其他说明\s*\n+([\s\S]*?)(?:\n##|\n---|\Z)",
            document
        )
        if notes_match:
            notes = notes_match.group(1).strip()
            # 移除列表前缀的 "-"
            lines = []
            for line in notes.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:]
                if line:
                    lines.append(line)
            return "\n".join(lines)
        return ""


# ============================================================
# 工具实现
# ============================================================

class ParseRequirementDocTool(Tool[ParseRequirementParams]):
    """解析需求文档的工具。

    从需求文档中提取结构化的指标定义信息，供后续开发流程使用。
    """

    @property
    def name(self) -> str:
        return "parse_requirement_doc"

    @property
    def description(self) -> str:
        return (
            "解析需求文档，提取结构化的指标定义信息。"
            "输入：需求文档原文（Markdown 格式）。"
            "输出：需求概述、指标定义列表（指标名称、字段性质、统计方式、取值来源、取值规则、展示格式）、"
            "涉及的表/字段清单。供后续验证表结构、生成开发文档使用。"
        )

    def get_args_schema(self) -> Type[ParseRequirementParams]:
        return ParseRequirementParams

    async def execute(
        self, context: ToolContext, args: ParseRequirementParams
    ) -> ToolResult:
        """执行需求文档解析。"""
        try:
            parser = RequirementDocParser(strict_mode=args.strict_mode)
            result = parser.parse(args.document)

            # 生成 LLM 可读的结果文本
            llm_text = self._format_result_for_llm(result)

            # 生成 UI 展示
            ui_content = self._format_result_for_ui(result)

            return ToolResult(
                success=True,
                result_for_llm=llm_text,
                ui_component=UiComponent(
                    rich_component=CardComponent(
                        title="📋 需求文档解析结果",
                        content=ui_content,
                        icon="📋",
                        status="success" if result.parse_success else "warning",
                        collapsible=True,
                        collapsed=False,
                        markdown=True,
                    ),
                    simple_component=None,
                ),
                metadata={
                    "parsed_result": result.model_dump(),
                    "metric_count": len(result.metrics),
                    "table_count": len(result.all_source_tables),
                },
            )

        except Exception as e:
            error_msg = f"解析需求文档失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ToolResult(
                success=False,
                result_for_llm=error_msg,
                ui_component=UiComponent(
                    rich_component=StatusBarUpdateComponent(
                        status="error",
                        message="解析失败",
                        detail=str(e),
                    ),
                    simple_component=None,
                ),
                error=str(e),
            )

    def _format_result_for_llm(self, result: ParsedRequirementDoc) -> str:
        """格式化结果供 LLM 使用。"""
        lines = []

        # 需求概述
        lines.append("=" * 60)
        lines.append("需求文档解析结果")
        lines.append("=" * 60)
        lines.append("")
        lines.append("【需求概述】")
        lines.append(f"需求名称：{result.overview.requirement_name}")
        if result.overview.requirement_background:
            lines.append(f"需求背景：{result.overview.requirement_background}")
        lines.append("")

        # 统计汇总
        lines.append("【指标统计】")
        lines.append(f"总计 {len(result.metrics)} 个指标：")
        lines.append(f"  - 维度：{result.dimension_count} 个")
        lines.append(f"  - 原子指标：{result.atomic_metric_count} 个")
        lines.append(f"  - 派生指标：{result.derived_metric_count} 个")
        lines.append("")

        # 涉及的表
        lines.append("【涉及来源表】")
        if result.all_source_tables:
            for t in result.all_source_tables:
                lines.append(f"  - {t}")
        else:
            lines.append("  （无）")
        lines.append("")

        # 指标明细
        lines.append("【指标定义明细】")
        lines.append("")
        for i, m in enumerate(result.metrics, 1):
            lines.append(f"--- 指标 {i}: {m.metric_name} ---")
            lines.append(f"字段性质：{m.field_type}")
            lines.append(f"统计方式：{m.aggregation_method}")
            lines.append(f"取值来源：{m.source_reference.raw_text}")
            if m.source_reference.table_name:
                lines.append(f"  → 来源表：{m.source_reference.table_name}")
            if m.source_reference.fields:
                lines.append(f"  → 涉及字段：{', '.join(m.source_reference.fields)}")
            if m.source_reference.join_condition:
                lines.append(f"  → 关联条件：{m.source_reference.join_condition}")
            lines.append(f"取值规则：{m.calculation_rule}")
            lines.append(f"展示格式：{m.display_format}")
            if m.remarks:
                lines.append(f"备注：{m.remarks}")
            if m.issues:
                lines.append(f"⚠️ 问题：{'; '.join(m.issues)}")
            lines.append("")

        # 其他说明
        if result.overview.other_notes:
            lines.append("【其他说明】")
            lines.append(result.overview.other_notes)
            lines.append("")

        # 警告信息
        if result.parse_warnings:
            lines.append("【解析警告】")
            for w in result.parse_warnings:
                lines.append(f"⚠️ {w}")

        return "\n".join(lines)

    def _format_result_for_ui(self, result: ParsedRequirementDoc) -> str:
        """格式化结果供 UI 展示。"""
        lines = []

        lines.append(f"**需求名称**：{result.overview.requirement_name}")
        lines.append("")
        lines.append(f"**指标统计**：共 {len(result.metrics)} 个")
        lines.append(f"- 维度：{result.dimension_count} | 原子指标：{result.atomic_metric_count} | 派生指标：{result.derived_metric_count}")
        lines.append("")

        if result.all_source_tables:
            lines.append(f"**涉及来源表**：{', '.join(result.all_source_tables)}")
            lines.append("")

        lines.append("**指标列表**：")
        for i, m in enumerate(result.metrics, 1):
            status_icon = "⚠️" if m.has_issues else "✅"
            lines.append(f"{i}. {status_icon} **{m.metric_name}** [{m.field_type}] - {m.aggregation_method}")

        if result.parse_warnings:
            lines.append("")
            lines.append("**解析警告**：")
            for w in result.parse_warnings:
                lines.append(f"- ⚠️ {w}")

        return "\n".join(lines)

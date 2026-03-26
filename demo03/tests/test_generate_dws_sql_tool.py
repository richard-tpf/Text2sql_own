"""
测试 GenerateDwsSqlTool 工具。

测试三种加工模式的SQL生成功能：
- direct_aggregate: 直接聚合
- single_cte_flag: 单CTE flag
- multi_cte_flag: 多CTE打标

运行方式：
    cd D:\Files\Pycharm\vanna
    python -m demo03.tests.test_generate_dws_sql_tool
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from demo03.generate_dws_sql_tool import (
    GenerateDwsSqlTool,
    GenerateDwsSqlParams,
    FieldDef,
    JoinCondition,
    ProcessPattern,
)
from demo03.NoOpAgentMemory import NoOpAgentMemory
from vanna.core.tool import ToolContext
from vanna.core.user import User


# ============================================================
# 测试数据准备
# ============================================================

# 来源表 DDL 示例
SOURCE_DDL_CREDIT_APPLY = """
CREATE TABLE IF NOT EXISTS zijie.dwd_credit_apply_df (
    apply_id STRING COMMENT '申请ID',
    user_id STRING COMMENT '用户ID',
    product_code STRING COMMENT '产品代码',
    apply_time STRING COMMENT '申请时间',
    apply_amount DECIMAL(18,2) COMMENT '申请金额',
    apply_status STRING COMMENT '申请状态'
) COMMENT '授信申请明细表'
PARTITIONED BY (ds STRING COMMENT '日期分区')
STORED AS ORC;
"""

SOURCE_DDL_CREDIT_RESULT = """
CREATE TABLE IF NOT EXISTS zijie.dwd_credit_result_df (
    apply_id STRING COMMENT '申请ID',
    user_id STRING COMMENT '用户ID',
    approve_time STRING COMMENT '审批时间',
    approve_amount DECIMAL(18,2) COMMENT '审批金额',
    approve_status STRING COMMENT '审批状态'
) COMMENT '授信结果明细表'
PARTITIONED BY (ds STRING COMMENT '日期分区')
STORED AS ORC;
"""


def create_mock_context() -> ToolContext:
    """创建模拟上下文。"""
    mock_user = User(
        id="test_user",
        email="test@example.com",
        group_memberships=["admin"],
    )
    return ToolContext(
        user=mock_user,
        conversation_id="test_conv_001",
        request_id="test_req_001",
        agent_memory=NoOpAgentMemory(),
    )


# ============================================================
# 测试用例 1: 直接聚合模式
# ============================================================

async def test_direct_aggregate_mode():
    """测试直接聚合模式。"""
    print("=" * 70)
    print("测试用例 1: 直接聚合模式 (direct_aggregate)")
    print("=" * 70)
    
    tool = GenerateDwsSqlTool()
    context = create_mock_context()
    
    # 构建参数
    fields = [
        FieldDef(
            name="product_code",
            data_type="STRING",
            comment="产品代码",
            source_field="a.product_code",
            aggregate_type="NONE",
            is_dimension=True,
        ),
        FieldDef(
            name="apply_cnt",
            data_type="BIGINT",
            comment="申请笔数",
            source_field="a.apply_id",
            aggregate_type="COUNT",
            is_dimension=False,
        ),
        FieldDef(
            name="apply_user_cnt",
            data_type="BIGINT",
            comment="申请人数",
            source_field="a.user_id",
            aggregate_type="COUNT_DISTINCT",
            is_dimension=False,
        ),
        FieldDef(
            name="apply_amount_sum",
            data_type="DECIMAL(18,2)",
            comment="申请金额汇总",
            source_field="a.apply_amount",
            aggregate_type="SUM",
            is_dimension=False,
            nullable_handling=True,
        ),
    ]
    
    args = GenerateDwsSqlParams(
        table_name="zijie.dws_credit_apply_day_df",
        table_comment="授信申请日汇总表",
        fields=fields,
        source_ddls=[SOURCE_DDL_CREDIT_APPLY],
        source_aliases=["a"],
        process_pattern=ProcessPattern.DIRECT_AGGREGATE.value,
        where_conditions=["a.apply_status = 'SUCCESS'"],
    )
    
    # 执行
    result = await tool.execute(context, args)
    
    print(f"\n执行结果: {'✅ 成功' if result.success else '❌ 失败'}")
    if result.success:
        print("\n" + "-" * 70)
        print(result.result_for_llm)
    else:
        print(f"错误: {result.error}")
    
    return result


# ============================================================
# 测试用例 2: 单CTE flag模式
# ============================================================

async def test_single_cte_flag_mode():
    """测试单CTE flag模式。"""
    print("\n" + "=" * 70)
    print("测试用例 2: 单CTE flag模式 (single_cte_flag)")
    print("=" * 70)
    
    tool = GenerateDwsSqlTool()
    context = create_mock_context()
    
    # 构建参数 - 单表打标后聚合
    fields = [
        FieldDef(
            name="product_code",
            data_type="STRING",
            comment="产品代码",
            source_field="a.product_code",
            aggregate_type="NONE",
            is_dimension=True,
        ),
        FieldDef(
            name="apply_cnt",
            data_type="BIGINT",
            comment="申请笔数",
            source_field="apply_flag",
            aggregate_type="SUM",
            is_dimension=False,
        ),
        FieldDef(
            name="success_apply_cnt",
            data_type="BIGINT",
            comment="成功申请笔数",
            source_field="success_flag",
            aggregate_type="SUM",
            is_dimension=False,
        ),
    ]
    
    args = GenerateDwsSqlParams(
        table_name="zijie.dws_credit_funnel_day_df",
        table_comment="授信漏斗日汇总表",
        fields=fields,
        source_ddls=[SOURCE_DDL_CREDIT_APPLY],
        source_aliases=["a"],
        process_pattern=ProcessPattern.SINGLE_CTE_FLAG.value,
    )
    
    result = await tool.execute(context, args)
    
    print(f"\n执行结果: {'✅ 成功' if result.success else '❌ 失败'}")
    if result.success:
        print("\n" + "-" * 70)
        print(result.result_for_llm)
    else:
        print(f"错误: {result.error}")
    
    return result


# ============================================================
# 测试用例 3: 多CTE打标模式
# ============================================================

async def test_multi_cte_flag_mode():
    """测试多CTE打标模式。"""
    print("\n" + "=" * 70)
    print("测试用例 3: 多CTE打标模式 (multi_cte_flag)")
    print("=" * 70)
    
    tool = GenerateDwsSqlTool()
    context = create_mock_context()
    
    # 构建参数 - 多表JOIN后聚合
    fields = [
        FieldDef(
            name="product_code",
            data_type="STRING",
            comment="产品代码",
            source_field="a.product_code",
            aggregate_type="NONE",
            is_dimension=True,
        ),
        FieldDef(
            name="apply_cnt",
            data_type="BIGINT",
            comment="申请笔数",
            source_field="a.apply_id",
            aggregate_type="COUNT",
            is_dimension=False,
        ),
        FieldDef(
            name="approve_cnt",
            data_type="BIGINT",
            comment="审批通过笔数",
            source_field="b.apply_id",
            aggregate_type="COUNT",
            is_dimension=False,
        ),
        FieldDef(
            name="approve_amount_sum",
            data_type="DECIMAL(18,2)",
            comment="审批金额汇总",
            source_field="b.approve_amount",
            aggregate_type="SUM",
            is_dimension=False,
            nullable_handling=True,
        ),
    ]
    
    join_conditions = [
        JoinCondition(
            left_table_alias="a",
            right_table_alias="b",
            join_type="LEFT JOIN",
            on_condition="a.apply_id = b.apply_id AND a.ds = b.ds",
        )
    ]
    
    args = GenerateDwsSqlParams(
        table_name="zijie.dws_credit_full_funnel_day_df",
        table_comment="授信全流程漏斗日汇总表",
        fields=fields,
        source_ddls=[SOURCE_DDL_CREDIT_APPLY, SOURCE_DDL_CREDIT_RESULT],
        source_aliases=["a", "b"],
        process_pattern=ProcessPattern.MULTI_CTE_FLAG.value,
        join_conditions=join_conditions,
    )
    
    result = await tool.execute(context, args)
    
    print(f"\n执行结果: {'✅ 成功' if result.success else '❌ 失败'}")
    if result.success:
        print("\n" + "-" * 70)
        print(result.result_for_llm)
    else:
        print(f"错误: {result.error}")
    
    return result


# ============================================================
# 测试用例 4: 参数校验测试
# ============================================================

async def test_validation_errors():
    """测试参数校验。"""
    print("\n" + "=" * 70)
    print("测试用例 4: 参数校验")
    print("=" * 70)
    
    tool = GenerateDwsSqlTool()
    context = create_mock_context()
    
    # 测试 4.1: 无效的表名前缀
    print("\n--- 4.1 测试无效表名前缀 ---")
    args = GenerateDwsSqlParams(
        table_name="invalid_table_name",  # 不以 zijie.dws_ 开头
        table_comment="测试表",
        fields=[
            FieldDef(
                name="user_id",
                data_type="STRING",
                comment="用户ID",
                is_dimension=True,
            )
        ],
        source_ddls=[SOURCE_DDL_CREDIT_APPLY],
        source_aliases=["a"],
        process_pattern="direct_aggregate",
    )
    result = await tool.execute(context, args)
    print(f"结果: {'✅ 符合预期 - 校验失败' if not result.success else '❌ 应该失败但成功了'}")
    if not result.success:
        print(f"错误信息: {result.result_for_llm[:200]}...")
    
    # 测试 4.2: 无效的加工模式
    print("\n--- 4.2 测试无效加工模式 ---")
    args = GenerateDwsSqlParams(
        table_name="zijie.dws_test_day_df",
        table_comment="测试表",
        fields=[
            FieldDef(
                name="user_id",
                data_type="STRING",
                comment="用户ID",
                is_dimension=True,
            )
        ],
        source_ddls=[SOURCE_DDL_CREDIT_APPLY],
        source_aliases=["a"],
        process_pattern="invalid_pattern",  # 无效模式
    )
    result = await tool.execute(context, args)
    print(f"结果: {'✅ 符合预期 - 校验失败' if not result.success else '❌ 应该失败但成功了'}")
    if not result.success:
        print(f"错误信息: {result.result_for_llm[:200]}...")
    
    # 测试 4.3: 缺少维度字段
    print("\n--- 4.3 测试缺少维度字段 ---")
    args = GenerateDwsSqlParams(
        table_name="zijie.dws_test_day_df",
        table_comment="测试表",
        fields=[
            FieldDef(
                name="cnt",
                data_type="BIGINT",
                comment="数量",
                aggregate_type="COUNT",
                is_dimension=False,  # 没有维度字段
            )
        ],
        source_ddls=[SOURCE_DDL_CREDIT_APPLY],
        source_aliases=["a"],
        process_pattern="direct_aggregate",
    )
    result = await tool.execute(context, args)
    print(f"结果: {'✅ 符合预期 - 校验失败' if not result.success else '❌ 应该失败但成功了'}")
    if not result.success:
        print(f"错误信息: {result.result_for_llm[:200]}...")


# ============================================================
# 主函数
# ============================================================

async def main():
    """主测试流程。"""
    print("🚀 GenerateDwsSqlTool 功能测试")
    print("=" * 70)
    print("测试工具的三种加工模式和参数校验功能")
    print("=" * 70)
    
    results = []
    
    # 测试用例 1: 直接聚合
    result1 = await test_direct_aggregate_mode()
    results.append(("直接聚合模式", result1.success))
    
    # 测试用例 2: 单CTE flag
    result2 = await test_single_cte_flag_mode()
    results.append(("单CTE flag模式", result2.success))
    
    # 测试用例 3: 多CTE打标
    result3 = await test_multi_cte_flag_mode()
    results.append(("多CTE打标模式", result3.success))
    
    # 测试用例 4: 参数校验
    await test_validation_errors()
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    
    all_passed = True
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {name}: {status}")
        if not success:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有测试用例通过")
    else:
        print("❌ 存在失败的测试用例")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

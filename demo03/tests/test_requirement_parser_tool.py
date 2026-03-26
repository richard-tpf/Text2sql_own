"""
测试 ParseRequirementDocTool 工具。

从 Milvus 知识库中搜索"客户分层授信指标统计表"需求文档，
然后使用 ParseRequirementDocTool 解析并输出结构化结果。

运行方式：
    cd D:\Files\Pycharm\vanna
    python -m demo03.tests.test_requirement_parser_tool
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from demo03.knowledge_base import DualKnowledgeBaseManager
from demo03.requirement_parser_tool import (
    ParseRequirementDocTool,
    ParseRequirementParams,
    RequirementDocParser,
)
from demo03.NoOpAgentMemory import NoOpAgentMemory
from vanna.core.tool import ToolContext
from vanna.core.user import User


# ============================================================
# Milvus 配置（与 demo03/agent.py 保持一致）
# ============================================================
MILVUS_HOST = "172.16.11.57"
MILVUS_PORT = 19530
SCHEMA_COLLECTION = "dw_schema_kb"
BUSINESS_COLLECTION = "dw_business_kb"


async def test_search_requirement_doc():
    """测试从知识库搜索需求文档。"""
    print("=" * 60)
    print("步骤 1: 从 Milvus 知识库搜索需求文档")
    print("=" * 60)

    kb_manager = DualKnowledgeBaseManager(
        host=MILVUS_HOST,
        port=MILVUS_PORT,
        schema_collection=SCHEMA_COLLECTION,
        business_collection=BUSINESS_COLLECTION,
        dimension=1024,
    )

    # 搜索需求文档
    query = "客户分层授信指标统计表"
    print(f"\n搜索 query: {query}")
    print(f"搜索范围: business (需求文档)")

    results = await kb_manager.search_business(
        query=query,
        limit=1,
        knowledge_type="requirement",
    )

    if not results:
        print("\n❌ 未找到需求文档，尝试不限制 knowledge_type...")
        results = await kb_manager.search_business(
            query=query,
            limit=3,
            similarity_threshold=0.3,
        )

    if not results:
        print("\n❌ 知识库中未找到相关需求文档")
        return None

    print(f"\n✅ 找到 {len(results)} 条结果")
    for r in results:
        print(f"  - 标题: {r.item.title}")
        print(f"    类型: {r.item.knowledge_type}")
        print(f"    相似度: {r.similarity_score:.4f}")
        print(f"    内容长度: {len(r.item.content)} 字符")

    return results[0].item.content


async def test_parse_requirement_doc(document: str):
    """测试解析需求文档。"""
    print("\n" + "=" * 60)
    print("步骤 2: 使用 ParseRequirementDocTool 解析需求文档")
    print("=" * 60)

    # 创建工具实例
    tool = ParseRequirementDocTool()

    # 创建模拟上下文
    mock_user = User(
        id="test_user",
        email="test@example.com",
        group_memberships=["admin"],
    )
    mock_context = ToolContext(
        user=mock_user,
        conversation_id="test_conv_001",
        request_id="test_req_001",
        agent_memory=NoOpAgentMemory(),
    )

    # 创建参数
    args = ParseRequirementParams(
        document=document,
        strict_mode=True,
    )

    # 执行解析
    print("\n正在解析需求文档...")
    result = await tool.execute(mock_context, args)

    print(f"\n解析结果: {'✅ 成功' if result.success else '❌ 失败'}")

    if result.success:
        # 输出 LLM 可见的结果
        print("\n" + "-" * 60)
        print("LLM 可见的解析结果:")
        print("-" * 60)
        print(result.result_for_llm)

        # 输出结构化数据
        if result.metadata:
            print("\n" + "-" * 60)
            print("结构化元数据 (JSON):")
            print("-" * 60)
            parsed = result.metadata.get("parsed_result", {})
            
            # 打印汇总信息
            print(f"\n📊 指标统计:")
            print(f"   - 总指标数: {result.metadata.get('metric_count', 0)}")
            print(f"   - 涉及表数: {result.metadata.get('table_count', 0)}")
            
            # 打印所有来源表
            all_tables = parsed.get("all_source_tables", [])
            if all_tables:
                print(f"\n📋 涉及的来源表 ({len(all_tables)} 张):")
                for t in all_tables:
                    print(f"   - {t}")

            # 打印指标名称列表
            metrics = parsed.get("metrics", [])
            if metrics:
                print(f"\n📈 指标列表 ({len(metrics)} 个):")
                for i, m in enumerate(metrics, 1):
                    status = "⚠️" if m.get("has_issues") else "✅"
                    print(f"   {i}. {status} {m.get('metric_name')} [{m.get('field_type')}]")
                    if m.get("issues"):
                        for issue in m.get("issues", []):
                            print(f"       └─ ⚠️ {issue}")
    else:
        print(f"\n错误信息: {result.error}")

    return result


async def test_parser_directly(document: str):
    """直接测试解析器（不通过 Tool 包装）。"""
    print("\n" + "=" * 60)
    print("步骤 3: 直接测试 RequirementDocParser 解析器")
    print("=" * 60)

    parser = RequirementDocParser(strict_mode=True)
    result = parser.parse(document)

    print(f"\n解析成功: {result.parse_success}")
    print(f"维度数量: {result.dimension_count}")
    print(f"原子指标数量: {result.atomic_metric_count}")
    print(f"派生指标数量: {result.derived_metric_count}")

    print(f"\n涉及来源表: {result.all_source_tables}")

    if result.parse_warnings:
        print(f"\n解析警告:")
        for w in result.parse_warnings:
            print(f"  - {w}")

    return result


async def test_with_local_file():
    """使用本地模板文件测试（备选方案）。"""
    print("\n" + "=" * 60)
    print("备选: 使用本地模板文件测试")
    print("=" * 60)

    template_path = project_root / "demo03" / "templates" / "客户分层授信指标统计表.md"
    if not template_path.exists():
        print(f"❌ 模板文件不存在: {template_path}")
        return None

    with open(template_path, "r", encoding="utf-8") as f:
        document = f.read()

    print(f"✅ 已加载本地模板文件: {template_path}")
    print(f"   文件大小: {len(document)} 字符")

    return document


async def main():
    """主测试流程。"""
    print("🚀 ParseRequirementDocTool 功能测试")
    print("=" * 60)

    # 步骤 1: 尝试从 Milvus 知识库搜索
    document = None
    try:
        document = await test_search_requirement_doc()
    except Exception as e:
        print(f"\n⚠️ 连接 Milvus 失败: {e}")
        print("将使用本地模板文件进行测试...")

    # 如果从知识库未找到，使用本地文件
    if not document:
        document = await test_with_local_file()

    if not document:
        print("\n❌ 无法获取测试文档，测试终止")
        return

    # 步骤 2: 测试 Tool
    await test_parse_requirement_doc(document)

    # 步骤 3: 直接测试 Parser
    await test_parser_directly(document)

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

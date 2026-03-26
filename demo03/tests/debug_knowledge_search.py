"""
调试知识库搜索功能。

排查为什么知识库中存在的表结构搜索不到。
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from demo03.knowledge_base import DualKnowledgeBaseManager

# Milvus 配置
MILVUS_HOST = "172.16.11.57"
MILVUS_PORT = 19530
SCHEMA_COLLECTION = "dw_schema_kb"
BUSINESS_COLLECTION = "dw_business_kb"


async def debug_schema_search():
    """调试表结构搜索。"""
    print("=" * 70)
    print("调试知识库搜索功能")
    print("=" * 70)

    kb_manager = DualKnowledgeBaseManager(
        host=MILVUS_HOST,
        port=MILVUS_PORT,
        schema_collection=SCHEMA_COLLECTION,
        business_collection=BUSINESS_COLLECTION,
        dimension=1024,
    )

    # 测试用例：要搜索的表名
    test_queries = [
        "zijie.dwd_fact_credit_application_df",
        "zijie.dim_credit_node_df",
        "授信申请",
        "授信节点",
        "credit_application",
        "credit_node",
        "授信申请事实表",
        "授信节点维度表",
    ]

    print("\n【测试 1】直接搜索表名（无过滤条件）")
    print("-" * 70)

    for query in test_queries:
        print(f"\n搜索: '{query}'")
        try:
            # 使用较低的阈值
            results = await kb_manager.search_schema(
                query=query,
                limit=3,
                similarity_threshold=0.0,  # 设为0，返回所有结果
            )
            if results:
                print(f"  ✅ 找到 {len(results)} 条结果:")
                for r in results:
                    print(f"     - {r.item.table_name} [层级:{r.item.layer}] 相似度:{r.similarity_score:.4f}")
            else:
                print(f"  ❌ 未找到结果")
        except Exception as e:
            print(f"  ❌ 搜索异常: {e}")

    # 测试按层级过滤
    print("\n\n【测试 2】按层级过滤搜索")
    print("-" * 70)

    layers = ["DWD", "MID", "DWS", "ADS"]
    for layer in layers:
        print(f"\n层级: {layer}")
        try:
            results = await kb_manager.search_schema(
                query="授信",  # 通用关键词
                limit=5,
                similarity_threshold=0.0,
                layer_filter=layer,
            )
            if results:
                print(f"  ✅ 找到 {len(results)} 条结果:")
                for r in results:
                    print(f"     - {r.item.table_name} 相似度:{r.similarity_score:.4f}")
            else:
                print(f"  ❌ 该层级无结果")
        except Exception as e:
            print(f"  ❌ 搜索异常: {e}")

    # 测试列出所有表（通用搜索）
    print("\n\n【测试 3】通用搜索 - 列出知识库中的表")
    print("-" * 70)

    generic_queries = ["表", "table", "dwd", "dim", "fact", "credit"]
    for query in generic_queries:
        print(f"\n搜索: '{query}'")
        try:
            results = await kb_manager.search_schema(
                query=query,
                limit=10,
                similarity_threshold=0.0,
            )
            if results:
                print(f"  ✅ 找到 {len(results)} 条结果:")
                for r in results:
                    print(f"     - {r.item.table_name} [层级:{r.item.layer}] 相似度:{r.similarity_score:.4f}")
            else:
                print(f"  ❌ 未找到结果")
        except Exception as e:
            print(f"  ❌ 搜索异常: {e}")

    # 直接查看 Milvus collection 统计
    print("\n\n【测试 4】直接查看 Milvus Collection 状态")
    print("-" * 70)
    try:
        from pymilvus import connections, Collection, utility

        if not connections.has_connection("default"):
            connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)

        # 检查 schema collection
        if utility.has_collection(SCHEMA_COLLECTION):
            collection = Collection(SCHEMA_COLLECTION)
            collection.load()
            stats = collection.num_entities
            print(f"  表结构知识库 ({SCHEMA_COLLECTION}):")
            print(f"    - 实体数量: {stats}")
            
            # 尝试查询前几条数据
            if stats > 0:
                print("    - 前5条数据:")
                results = collection.query(
                    expr="",
                    limit=5,
                    output_fields=["id", "table_name", "layer"]
                )
                for r in results:
                    print(f"      • {r.get('table_name', 'N/A')} [层级: {r.get('layer', 'N/A')}]")
        else:
            print(f"  ❌ Collection {SCHEMA_COLLECTION} 不存在")

        # 检查 business collection
        if utility.has_collection(BUSINESS_COLLECTION):
            collection = Collection(BUSINESS_COLLECTION)
            collection.load()
            stats = collection.num_entities
            print(f"\n  业务文档知识库 ({BUSINESS_COLLECTION}):")
            print(f"    - 实体数量: {stats}")
            
            if stats > 0:
                print("    - 前5条数据:")
                results = collection.query(
                    expr="",
                    limit=5,
                    output_fields=["id", "title", "knowledge_type"]
                )
                for r in results:
                    print(f"      • {r.get('title', 'N/A')} [类型: {r.get('knowledge_type', 'N/A')}]")
        else:
            print(f"  ❌ Collection {BUSINESS_COLLECTION} 不存在")

    except Exception as e:
        print(f"  ❌ 查询 Milvus 状态异常: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("调试完成")
    print("=" * 70)


async def main():
    await debug_schema_search()


if __name__ == "__main__":
    asyncio.run(main())

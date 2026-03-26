"""
查看知识库中的 DDL 内容，检查中文注释是否完整。
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection

MILVUS_HOST = "172.16.11.57"
MILVUS_PORT = 19530
SCHEMA_COLLECTION = "dw_schema_kb"


async def view_ddl_content():
    """查看表结构 DDL 内容。"""
    print("=" * 70)
    print("查看知识库中的表结构 DDL")
    print("=" * 70)

    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    collection = Collection(SCHEMA_COLLECTION)
    collection.load()

    # 查询所有数据
    results = collection.query(
        expr="",
        limit=10,
        output_fields=["id", "table_name", "layer", "ddl", "source_tables"]
    )

    for r in results:
        table_name = r.get("table_name", "N/A")
        layer = r.get("layer", "N/A")
        ddl = r.get("ddl", "")
        
        print(f"\n{'=' * 70}")
        print(f"表名: {table_name}")
        print(f"层级: {layer}")
        print(f"DDL 长度: {len(ddl)} 字符")
        print("-" * 70)
        # 只显示前 500 字符
        print(ddl[:500] if len(ddl) > 500 else ddl)
        if len(ddl) > 500:
            print("... (省略)")

    print(f"\n{'=' * 70}")
    print(f"共 {len(results)} 张表")


if __name__ == "__main__":
    asyncio.run(view_ddl_content())

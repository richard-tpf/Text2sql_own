"""
重新生成知识库 embedding 脚本。

读取 Milvus 中现有的表结构数据，使用新的 _build_bilingual_text 方法
重新生成 embedding 并更新。

运行方式：
    cd D:\Files\Pycharm\vanna
    python -m demo03.tests.rebuild_embeddings
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection, utility
from langchain_huggingface import HuggingFaceEmbeddings

# Milvus 配置
MILVUS_HOST = "172.16.11.57"
MILVUS_PORT = 19530
SCHEMA_COLLECTION = "dw_schema_kb"
BUSINESS_COLLECTION = "dw_business_kb"


def get_embed_model():
    """获取嵌入模型。"""
    print("正在加载嵌入模型 BAAI/bge-m3 ...")
    return HuggingFaceEmbeddings(model_name="BAAI/bge-m3")


def create_embedding(model, text: str) -> List[float]:
    """生成文本向量。"""
    return model.embed_query(text)


def build_bilingual_text_v2(table_name: str, ddl: str) -> str:
    """新版 _build_bilingual_text 方法：英文表名和字段名优先。
    
    与 knowledge_base.py 中的实现保持一致。
    """
    import re
    parts = []

    # 1. 英文表名放最前面（含 schema 和不含 schema 两种形式）
    parts.append(table_name)  # zijie.dwd_fact_credit_application_df
    short_name = table_name.split(".")[-1] if "." in table_name else table_name
    parts.append(short_name)  # dwd_fact_credit_application_df

    # 2. 提取所有英文字段名（优先放在前面）
    all_fields_pattern = re.compile(
        r'^\s+(\w+)\s+(?:STRING|BIGINT|INT|DECIMAL|DOUBLE|FLOAT|BOOLEAN|DATE|TIMESTAMP)\b',
        re.MULTILINE | re.IGNORECASE,
    )
    all_field_names = [m.group(1) for m in all_fields_pattern.finditer(ddl)]
    if all_field_names:
        parts.extend(all_field_names)

    # 3. 再次加入表名（增加权重）
    parts.append(table_name)
    parts.append(short_name)

    # 4. 提取表级 COMMENT（中文表名）
    table_comment = re.search(r"\)\s*COMMENT\s+'([^']*)'", ddl, re.IGNORECASE)
    if table_comment:
        parts.append(table_comment.group(1))

    # 5. 提取字段级：字段名 + COMMENT（中英文混合）
    field_pattern = re.compile(
        r'^\s+(\w+)\s+\S+.*?COMMENT\s+\'([^\']*)\'\s*,?\s*$',
        re.MULTILINE | re.IGNORECASE,
    )
    for match in field_pattern.finditer(ddl):
        field_name = match.group(1)
        comment = match.group(2)
        parts.append(f"{field_name}:{comment}")

    return " ".join(parts)


def build_business_text(content: str, title: str = "", knowledge_type: str = "") -> str:
    """构建业务文档的 embedding 文本。"""
    parts = []
    if title:
        parts.append(title)
    if knowledge_type:
        parts.append(knowledge_type)
    if content:
        parts.append(content)
    return "\n".join(parts)


async def rebuild_schema_embeddings():
    """重新生成表结构知识库的 embedding。"""
    print("\n" + "=" * 70)
    print("重新生成表结构知识库 embedding")
    print("=" * 70)

    # 连接 Milvus
    if not connections.has_connection("default"):
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)

    if not utility.has_collection(SCHEMA_COLLECTION):
        print(f"❌ Collection {SCHEMA_COLLECTION} 不存在")
        return

    collection = Collection(SCHEMA_COLLECTION)
    collection.load()

    # 查询所有数据
    print(f"\n正在查询 {SCHEMA_COLLECTION} 中的数据...")
    total = collection.num_entities
    print(f"共 {total} 条记录")

    if total == 0:
        print("知识库为空，无需重建")
        return

    # 分批查询所有数据
    all_records = []
    batch_size = 100
    offset = 0

    while offset < total:
        results = collection.query(
            expr="",
            limit=batch_size,
            offset=offset,
            output_fields=["id", "table_name", "layer", "ddl", "source_tables", "timestamp"]
        )
        all_records.extend(results)
        offset += len(results)
        if len(results) < batch_size:
            break

    print(f"已读取 {len(all_records)} 条记录")

    # 加载嵌入模型
    embed_model = get_embed_model()

    # 重新生成 embedding
    print("\n正在重新生成 embedding...")
    updated_records = []
    for i, record in enumerate(all_records):
        table_name = record.get("table_name", "")
        ddl = record.get("ddl", "")
        
        # 使用新方法构建文本
        bilingual_text = build_bilingual_text_v2(table_name, ddl)
        new_embedding = create_embedding(embed_model, bilingual_text)
        
        updated_records.append({
            "id": record["id"],
            "embedding": new_embedding,
            "table_name": table_name,
            "layer": record.get("layer", ""),
            "ddl": ddl,
            "source_tables": record.get("source_tables", ""),
            "timestamp": record.get("timestamp", ""),
        })
        
        print(f"  [{i+1}/{len(all_records)}] {table_name}")

    # 删除旧数据
    print(f"\n正在删除旧数据...")
    ids_to_delete = [r["id"] for r in all_records]
    for record_id in ids_to_delete:
        collection.delete(f'id == "{record_id}"')
    collection.flush()
    print(f"已删除 {len(ids_to_delete)} 条旧记录")

    # 插入新数据
    print(f"\n正在插入新数据...")
    entities = [
        [r["id"] for r in updated_records],
        [r["embedding"] for r in updated_records],
        [r["table_name"] for r in updated_records],
        [r["layer"] for r in updated_records],
        [r["ddl"] for r in updated_records],
        [r["source_tables"] for r in updated_records],
        [r["timestamp"] for r in updated_records],
    ]
    collection.insert(entities)
    collection.flush()
    print(f"已插入 {len(updated_records)} 条新记录")

    print(f"\n✅ 表结构知识库 embedding 重建完成！")


async def rebuild_business_embeddings():
    """重新生成业务文档知识库的 embedding。"""
    print("\n" + "=" * 70)
    print("重新生成业务文档知识库 embedding")
    print("=" * 70)

    # 连接 Milvus
    if not connections.has_connection("default"):
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)

    if not utility.has_collection(BUSINESS_COLLECTION):
        print(f"❌ Collection {BUSINESS_COLLECTION} 不存在")
        return

    collection = Collection(BUSINESS_COLLECTION)
    collection.load()

    # 查询所有数据
    print(f"\n正在查询 {BUSINESS_COLLECTION} 中的数据...")
    total = collection.num_entities
    print(f"共 {total} 条记录")

    if total == 0:
        print("知识库为空，无需重建")
        return

    # 分批查询所有数据
    all_records = []
    batch_size = 100
    offset = 0

    while offset < total:
        results = collection.query(
            expr="",
            limit=batch_size,
            offset=offset,
            output_fields=["id", "content", "knowledge_type", "title", "timestamp"]
        )
        all_records.extend(results)
        offset += len(results)
        if len(results) < batch_size:
            break

    print(f"已读取 {len(all_records)} 条记录")

    # 加载嵌入模型
    embed_model = get_embed_model()

    # 重新生成 embedding
    print("\n正在重新生成 embedding...")
    updated_records = []
    for i, record in enumerate(all_records):
        title = record.get("title", "")
        content = record.get("content", "")
        knowledge_type = record.get("knowledge_type", "")
        
        # 构建文本
        text = build_business_text(content, title, knowledge_type)
        new_embedding = create_embedding(embed_model, text)
        
        updated_records.append({
            "id": record["id"],
            "embedding": new_embedding,
            "content": content,
            "knowledge_type": knowledge_type,
            "title": title,
            "timestamp": record.get("timestamp", ""),
        })
        
        display_title = title[:30] + "..." if len(title) > 30 else title
        print(f"  [{i+1}/{len(all_records)}] {display_title or '(无标题)'}")

    # 删除旧数据
    print(f"\n正在删除旧数据...")
    ids_to_delete = [r["id"] for r in all_records]
    for record_id in ids_to_delete:
        collection.delete(f'id == "{record_id}"')
    collection.flush()
    print(f"已删除 {len(ids_to_delete)} 条旧记录")

    # 插入新数据
    print(f"\n正在插入新数据...")
    entities = [
        [r["id"] for r in updated_records],
        [r["embedding"] for r in updated_records],
        [r["content"] for r in updated_records],
        [r["knowledge_type"] for r in updated_records],
        [r["title"] for r in updated_records],
        [r["timestamp"] for r in updated_records],
    ]
    collection.insert(entities)
    collection.flush()
    print(f"已插入 {len(updated_records)} 条新记录")

    print(f"\n✅ 业务文档知识库 embedding 重建完成！")


async def main():
    """主函数。"""
    print("🚀 知识库 Embedding 重建工具")
    print("=" * 70)
    print("此脚本将重新生成知识库中所有数据的 embedding 向量。")
    print("使用新的匹配策略：英文表名和字段名优先。")
    print("=" * 70)

    # 确认执行
    confirm = input("\n确认执行重建？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    # 重建表结构知识库
    await rebuild_schema_embeddings()

    # 重建业务文档知识库（可选）
    rebuild_business = input("\n是否也重建业务文档知识库？(y/N): ").strip().lower()
    if rebuild_business == "y":
        await rebuild_business_embeddings()

    print("\n" + "=" * 70)
    print("✅ 全部完成！")
    print("=" * 70)
    print("\n请运行 debug_knowledge_search.py 验证搜索效果。")


if __name__ == "__main__":
    asyncio.run(main())

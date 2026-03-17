"""
知识库实现。

基于 Milvus 向量数据库存储和检索建表语句、业务知识等。
使用 HuggingFace 嵌入模型生成向量。
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
from langchain_huggingface import HuggingFaceEmbeddings


class KnowledgeItem(BaseModel):
    """知识条目模型。"""
    knowledge_id: Optional[str] = None
    content: str
    knowledge_type: str  # "ddl" (建表语句) 或 "business" (业务知识)
    title: str = ""
    timestamp: Optional[str] = None


class KnowledgeSearchResult(BaseModel):
    """知识搜索结果。"""
    item: KnowledgeItem
    similarity_score: float
    rank: int


class MilvusKnowledgeBase:
    """基于 Milvus 的知识库实现。"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "knowledge_base",
        alias: str = "default",
        dimension: int = 1024,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.alias = alias
        self.dimension = dimension
        self._collection = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._embed_model = None

    def _get_embed_model(self):
        """懒加载嵌入模型。"""
        if self._embed_model is None:
            self._embed_model = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
        return self._embed_model

    def _create_embedding(self, text: str) -> List[float]:
        """使用 BAAI/bge-m3 生成文本向量。"""
        return self._get_embed_model().embed_query(text)

    def _get_collection(self):
        """获取或创建 Milvus 集合。"""
        if self._collection is None:
            connections.connect(alias=self.alias, host=self.host, port=self.port)

            if not utility.has_collection(self.collection_name):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=30000),
                    FieldSchema(name="knowledge_type", dtype=DataType.VARCHAR, max_length=50),
                    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
                    FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=50),
                ]

                schema = CollectionSchema(fields=fields, description="知识库")
                collection = Collection(name=self.collection_name, schema=schema)

                index_params = {
                    "index_type": "IVF_FLAT",
                    "metric_type": "IP",
                    "params": {"nlist": 128},
                }
                collection.create_index(field_name="embedding", index_params=index_params)
                self._collection = collection
            else:
                self._collection = Collection(self.collection_name)

            self._collection.load()

        return self._collection

    async def save_knowledge(
        self,
        content: str,
        knowledge_type: str,
        title: str = "",
    ) -> KnowledgeItem:
        """保存知识到向量数据库。

        Args:
            content: 知识内容（建表语句或业务知识文本）
            knowledge_type: 知识类型，"ddl" 或 "business"
            title: 知识标题（可选）
        """
        def _save():
            collection = self._get_collection()

            knowledge_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            embedding = self._create_embedding(content)

            entities = [
                [knowledge_id],
                [embedding],
                [content],
                [knowledge_type],
                [title],
                [timestamp],
            ]

            collection.insert(entities)
            collection.flush()

            return KnowledgeItem(
                knowledge_id=knowledge_id,
                content=content,
                knowledge_type=knowledge_type,
                title=title,
                timestamp=timestamp,
            )

        return await asyncio.get_event_loop().run_in_executor(self._executor, _save)

    async def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.5,
        knowledge_type: Optional[str] = None,
    ) -> List[KnowledgeSearchResult]:
        """搜索知识库。

        Args:
            query: 搜索查询文本
            limit: 最大返回数量
            similarity_threshold: 最低相似度阈值
            knowledge_type: 可选，按类型过滤 ("ddl" 或 "business")
        """
        def _search():
            collection = self._get_collection()

            embedding = self._create_embedding(query)

            expr = None
            if knowledge_type:
                expr = f'knowledge_type == "{knowledge_type}"'

            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}

            results = collection.search(
                data=[embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["id", "content", "knowledge_type", "title", "timestamp"],
            )

            search_results = []
            for hits in results:
                for rank, hit in enumerate(hits):
                    if hit.distance >= similarity_threshold:
                        item = KnowledgeItem(
                            knowledge_id=hit.entity.get("id"),
                            content=hit.entity.get("content", ""),
                            knowledge_type=hit.entity.get("knowledge_type", ""),
                            title=hit.entity.get("title", ""),
                            timestamp=hit.entity.get("timestamp"),
                        )
                        search_results.append(
                            KnowledgeSearchResult(
                                item=item,
                                similarity_score=hit.distance,
                                rank=rank + 1,
                            )
                        )

            return search_results

        return await asyncio.get_event_loop().run_in_executor(self._executor, _search)

    async def delete_knowledge(self, knowledge_id: str) -> bool:
        """根据 ID 删除知识条目。"""
        def _delete():
            collection = self._get_collection()
            try:
                collection.delete(f'id == "{knowledge_id}"')
                return True
            except Exception:
                return False

        return await asyncio.get_event_loop().run_in_executor(self._executor, _delete)

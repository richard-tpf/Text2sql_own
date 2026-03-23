"""
双知识库实现。

基于 Milvus 向量数据库，分别管理「表结构知识库」和「业务文档知识库」。
两个知识库使用不同的 Milvus connection alias 和 collection，互不干扰。
"""

import re
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
from pymilvus.exceptions import MilvusException
from langchain_huggingface import HuggingFaceEmbeddings


class SchemaItem(BaseModel):
    """表结构知识条目模型。"""
    knowledge_id: Optional[str] = None
    table_name: str          # 库名.表名，如 zijie.dwd_credit_apply_df
    layer: str = ""          # 所属层级：DWD / MID / DWS / ADS
    ddl: str                 # 建表语句原文
    source_tables: str = ""  # 来源表列表，逗号分隔
    timestamp: Optional[str] = None


class SchemaSearchResult(BaseModel):
    """表结构搜索结果。"""
    item: SchemaItem
    similarity_score: float
    rank: int


class KnowledgeItem(BaseModel):
    """业务文档知识条目模型。"""
    knowledge_id: Optional[str] = None
    content: str
    knowledge_type: str  # "business" / "requirement" / "standard"
    title: str = ""
    timestamp: Optional[str] = None


class KnowledgeSearchResult(BaseModel):
    """业务文档搜索结果。"""
    item: KnowledgeItem
    similarity_score: float
    rank: int


class MilvusSchemaKnowledgeBase:
    """表结构专用 Milvus 知识库。字段：table_name, ddl, source_tables。"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "dw_schema_kb",
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
        self._metric_type: Optional[str] = None  # collection index's metric_type (IP/COSINE)

    def _get_embed_model(self):
        if self._embed_model is None:
            self._embed_model = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
        return self._embed_model

    def _create_embedding(self, text: str) -> List[float]:
        return self._get_embed_model().embed_query(text)

    @staticmethod
    def _build_bilingual_text(table_name: str, ddl: str) -> str:
        """从 DDL 中提取字段名和中文 COMMENT，构建中英文混合文本用于 embedding。

        例如 DDL 中 `apply_id STRING COMMENT '申请ID'` 会生成 `apply_id:申请ID`，
        最终拼接为 `表名 字段名:注释 字段名:注释 ...` 的格式，
        使得中文搜索（如"申请金额"）和英文搜索（如"apply_amount"）都能命中。
        """
        parts = [table_name]

        # 提取表级 COMMENT
        table_comment = re.search(r"\)\s*COMMENT\s+'([^']*)'", ddl, re.IGNORECASE)
        if table_comment:
            parts.append(table_comment.group(1))

        # 提取字段级：字段名 + COMMENT
        field_pattern = re.compile(
            r'^\s+(\w+)\s+\S+.*?COMMENT\s+\'([^\']*)\'\s*,?\s*$',
            re.MULTILINE | re.IGNORECASE,
        )
        for match in field_pattern.finditer(ddl):
            field_name = match.group(1)
            comment = match.group(2)
            parts.append(f"{field_name}:{comment}")

        # 同时也提取没有 COMMENT 的字段名
        all_fields_pattern = re.compile(
            r'^\s+(\w+)\s+(?:STRING|BIGINT|INT|DECIMAL|DOUBLE|FLOAT|BOOLEAN|DATE|TIMESTAMP)\b',
            re.MULTILINE | re.IGNORECASE,
        )
        field_names_with_comment = {m.group(1) for m in field_pattern.finditer(ddl)}
        for match in all_fields_pattern.finditer(ddl):
            field_name = match.group(1)
            if field_name not in field_names_with_comment:
                parts.append(field_name)

        return " ".join(parts)

    def _get_collection(self):
        if self._collection is None:
            # 共用 default 连接，避免重复连接
            if not connections.has_connection(self.alias):
                connections.connect(alias=self.alias, host=self.host, port=self.port)
            if not utility.has_collection(self.collection_name, using=self.alias):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                    FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=500),
                    FieldSchema(name="layer", dtype=DataType.VARCHAR, max_length=20),
                    FieldSchema(name="ddl", dtype=DataType.VARCHAR, max_length=30000),
                    FieldSchema(name="source_tables", dtype=DataType.VARCHAR, max_length=5000),
                    FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=50),
                ]
                schema = CollectionSchema(fields=fields, description="表结构知识库")
                collection = Collection(name=self.collection_name, schema=schema, using=self.alias)
                index_params = {
                    "index_type": "IVF_FLAT",
                    "metric_type": "IP",
                    "params": {"nlist": 128},
                }
                collection.create_index(field_name="embedding", index_params=index_params)
                self._metric_type = index_params.get("metric_type")
                self._collection = collection
            else:
                self._collection = Collection(self.collection_name, using=self.alias)
            self._collection.load()
            # For existing collections, index metric_type may not be IP (e.g. COSINE).
            # Detect it so search won't fail with "metric type not match".
            if self._metric_type is None:
                try:
                    indexes = getattr(self._collection, "indexes", None) or []
                    for idx in indexes:
                        mt = getattr(idx, "metric_type", None)
                        if mt:
                            self._metric_type = mt
                            break
                        if isinstance(idx, dict) and idx.get("metric_type"):
                            self._metric_type = idx["metric_type"]
                            break
                except Exception:
                    # Keep default; search params can still fall back to IP.
                    pass
        return self._collection

    async def save_schema(
        self,
        table_name: str,
        ddl: str,
        layer: str = "",
        source_tables: str = "",
    ) -> SchemaItem:
        """保存表结构到向量数据库。向量基于中英文混合文本生成，支持双语搜索。"""
        def _save():
            collection = self._get_collection()
            knowledge_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            # 构建中英文混合文本：表名 + 字段名:中文注释，提升双语检索效果
            bilingual_text = self._build_bilingual_text(table_name, ddl)
            embedding = self._create_embedding(bilingual_text)
            entities = [
                [knowledge_id],
                [embedding],
                [table_name],
                [layer],
                [ddl],
                [source_tables],
                [timestamp],
            ]
            collection.insert(entities)
            collection.flush()
            return SchemaItem(
                knowledge_id=knowledge_id,
                table_name=table_name,
                layer=layer,
                ddl=ddl,
                source_tables=source_tables,
                timestamp=timestamp,
            )
        return await asyncio.get_event_loop().run_in_executor(self._executor, _save)

    async def search_schema(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.5,
        table_name_filter: Optional[str] = None,
        layer_filter: Optional[str] = None,
    ) -> List[SchemaSearchResult]:
        """搜索表结构知识库。可按 table_name 精确过滤，可按 layer 过滤。"""
        def _search():
            collection = self._get_collection()
            embedding = self._create_embedding(query)
            exprs = []
            if table_name_filter:
                exprs.append(f'table_name == "{table_name_filter}"')
            if layer_filter:
                exprs.append(f'layer == "{layer_filter}"')
            expr = " and ".join(exprs) if exprs else None
            # 先不显式传 metric_type，避免与已有集合 index 不一致导致失败。
            search_params = {"params": {"nprobe": 10}}
            try:
                results = collection.search(
                    data=[embedding],
                    anns_field="embedding",
                    param=search_params,
                    limit=limit,
                    expr=expr,
                    output_fields=[
                        "id",
                        "table_name",
                        "layer",
                        "ddl",
                        "source_tables",
                        "timestamp",
                    ],
                )
            except MilvusException as e:
                # 如果返回 "expected=XXX][actual=YYY"，自动提取 expected 作为 retry metric_type
                msg = str(e)
                m = re.search(r"expected=([A-Za-z]+).*actual=([A-Za-z]+)", msg)
                if not m:
                    raise
                expected_metric = m.group(1)
                retry_params = {"metric_type": expected_metric, "params": {"nprobe": 10}}
                results = collection.search(
                    data=[embedding],
                    anns_field="embedding",
                    param=retry_params,
                    limit=limit,
                    expr=expr,
                    output_fields=[
                        "id",
                        "table_name",
                        "layer",
                        "ddl",
                        "source_tables",
                        "timestamp",
                    ],
                )
            search_results = []
            for hits in results:
                for rank, hit in enumerate(hits):
                    if hit.distance >= similarity_threshold:
                        item = SchemaItem(
                            knowledge_id=hit.entity.get("id"),
                            table_name=hit.entity.get("table_name", ""),
                            layer=hit.entity.get("layer", ""),
                            ddl=hit.entity.get("ddl", ""),
                            source_tables=hit.entity.get("source_tables", ""),
                            timestamp=hit.entity.get("timestamp"),
                        )
                        search_results.append(
                            SchemaSearchResult(item=item, similarity_score=hit.distance, rank=rank + 1)
                        )
            return search_results
        return await asyncio.get_event_loop().run_in_executor(self._executor, _search)

    async def delete_schema(self, knowledge_id: str) -> bool:
        def _delete():
            collection = self._get_collection()
            try:
                collection.delete(f'id == "{knowledge_id}"')
                return True
            except Exception:
                return False
        return await asyncio.get_event_loop().run_in_executor(self._executor, _delete)


class MilvusBusinessKnowledgeBase:
    """业务文档专用 Milvus 知识库实例。"""

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
        self._metric_type: Optional[str] = None  # collection index's metric_type (IP/COSINE)

    def _get_embed_model(self):
        """懒加载嵌入模型（全局共享）。"""
        if self._embed_model is None:
            self._embed_model = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
        return self._embed_model

    def _create_embedding(self, text: str) -> List[float]:
        """生成文本向量。"""
        return self._get_embed_model().embed_query(text)

    @staticmethod
    def _build_embedding_text(content: str, title: str = "", knowledge_type: str = "") -> str:
        """构建用于向量化的文本，合并标题+类型+正文，提升按标题检索命中率。"""
        parts = []
        if title:
            parts.append(title)
        if knowledge_type:
            parts.append(knowledge_type)
        if content:
            parts.append(content)
        return "\n".join(parts)

    def _get_collection(self):
        """获取或创建 Milvus 集合。"""
        if self._collection is None:
            # 共用 default 连接，避免重复连接
            if not connections.has_connection(self.alias):
                connections.connect(alias=self.alias, host=self.host, port=self.port)

            if not utility.has_collection(self.collection_name, using=self.alias):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=30000),
                    FieldSchema(name="knowledge_type", dtype=DataType.VARCHAR, max_length=50),
                    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
                    FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=50),
                ]
                schema = CollectionSchema(fields=fields, description=f"知识库: {self.collection_name}")
                collection = Collection(
                    name=self.collection_name, schema=schema, using=self.alias
                )
                index_params = {
                    "index_type": "IVF_FLAT",
                    "metric_type": "IP",
                    "params": {"nlist": 128},
                }
                collection.create_index(field_name="embedding", index_params=index_params)
                self._metric_type = index_params.get("metric_type")
                self._collection = collection
            else:
                self._collection = Collection(self.collection_name, using=self.alias)

            self._collection.load()
            # For existing collections, detect index metric_type so search matches.
            if self._metric_type is None:
                try:
                    indexes = getattr(self._collection, "indexes", None) or []
                    for idx in indexes:
                        mt = getattr(idx, "metric_type", None)
                        if mt:
                            self._metric_type = mt
                            break
                        if isinstance(idx, dict) and idx.get("metric_type"):
                            self._metric_type = idx["metric_type"]
                            break
                except Exception:
                    pass
        return self._collection

    async def save_knowledge(
        self,
        content: str,
        knowledge_type: str,
        title: str = "",
    ) -> KnowledgeItem:
        """保存知识到向量数据库。"""
        def _save():
            collection = self._get_collection()
            knowledge_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            embedding_text = self._build_embedding_text(
                content=content, title=title, knowledge_type=knowledge_type
            )
            embedding = self._create_embedding(embedding_text)
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
        similarity_threshold: float = 0.35,
        knowledge_type: Optional[str] = None,
    ) -> List[KnowledgeSearchResult]:
        """搜索知识库。"""
        def _search():
            collection = self._get_collection()
            embedding = self._create_embedding(query)
            expr = None
            if knowledge_type:
                expr = f'knowledge_type == "{knowledge_type}"'
            # 先不显式传 metric_type，避免与已有集合 index 不一致导致失败。
            search_params = {"params": {"nprobe": 10}}
            try:
                results = collection.search(
                    data=[embedding],
                    anns_field="embedding",
                    param=search_params,
                    limit=limit,
                    expr=expr,
                    output_fields=[
                        "id",
                        "content",
                        "knowledge_type",
                        "title",
                        "timestamp",
                    ],
                )
            except MilvusException as e:
                msg = str(e)
                m = re.search(r"expected=([A-Za-z]+).*actual=([A-Za-z]+)", msg)
                if not m:
                    raise
                expected_metric = m.group(1)
                retry_params = {"metric_type": expected_metric, "params": {"nprobe": 10}}
                results = collection.search(
                    data=[embedding],
                    anns_field="embedding",
                    param=retry_params,
                    limit=limit,
                    expr=expr,
                    output_fields=[
                        "id",
                        "content",
                        "knowledge_type",
                        "title",
                        "timestamp",
                    ],
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


class DualKnowledgeBaseManager:
    """
    双知识库管理器。

    - schema_kb: 表结构知识库（MilvusSchemaKnowledgeBase），字段: table_name, ddl, source_tables
    - business_kb: 业务文档知识库（MilvusBusinessKnowledgeBase），字段: content, knowledge_type, title
    """

    # 业务文档知识库支持的类型
    BUSINESS_TYPES = {"business", "requirement", "standard"}

    # 类型中文标签
    TYPE_LABELS = {
        "business": "业务知识",
        "requirement": "需求文档",
        "standard": "开发规范",
    }

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        schema_collection: str = "dw_schema_kb",
        business_collection: str = "dw_business_kb",
        dimension: int = 1024,
    ):
        self.schema_kb = MilvusSchemaKnowledgeBase(
            host=host,
            port=port,
            collection_name=schema_collection,
            alias="default",
            dimension=dimension,
        )
        self.business_kb = MilvusBusinessKnowledgeBase(
            host=host,
            port=port,
            collection_name=business_collection,
            alias="default",
            dimension=dimension,
        )

    # ---- 表结构知识库操作 ----

    async def save_schema(
        self,
        table_name: str,
        ddl: str,
        layer: str = "",
        source_tables: str = "",
    ) -> SchemaItem:
        """保存表结构到表结构知识库。"""
        return await self.schema_kb.save_schema(table_name, ddl, layer, source_tables)

    async def search_schema(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.5,
        table_name_filter: Optional[str] = None,
        layer_filter: Optional[str] = None,
    ) -> List[SchemaSearchResult]:
        """搜索表结构知识库。"""
        return await self.schema_kb.search_schema(query, limit, similarity_threshold, table_name_filter, layer_filter)

    # ---- 业务文档知识库操作 ----

    async def save_business(
        self,
        content: str,
        knowledge_type: str,
        title: str = "",
    ) -> KnowledgeItem:
        """保存业务文档到业务文档知识库。"""
        if knowledge_type not in self.BUSINESS_TYPES:
            raise ValueError(f"不支持的业务知识类型: {knowledge_type}，支持: {', '.join(self.BUSINESS_TYPES)}")
        return await self.business_kb.save_knowledge(content, knowledge_type, title)

    async def search_business(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.35,
        knowledge_type: Optional[str] = None,
    ) -> List[KnowledgeSearchResult]:
        """搜索业务文档知识库。"""
        return await self.business_kb.search_knowledge(query, limit, similarity_threshold, knowledge_type)

    # ---- 联合搜索 ----

    async def search_all(
        self,
        query: str,
        limit: int = 5,
        similarity_threshold: float = 0.5,
    ) -> dict:
        """
        同时搜索两个知识库，返回分类结果。

        Returns:
            {"schema": List[SchemaSearchResult], "business": List[KnowledgeSearchResult]}
        """
        schema_results = await self.schema_kb.search_schema(query, limit, similarity_threshold)
        business_results = await self.business_kb.search_knowledge(query, limit, similarity_threshold)
        return {"schema": schema_results, "business": business_results}

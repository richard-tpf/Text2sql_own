"""
自定义 Milvus 向量记忆实现。

使用 HuggingFace 嵌入模型生成向量，存储到 Milvus 向量数据库中。
"""

import uuid
import json
from typing import List
from datetime import datetime

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
from langchain_huggingface import HuggingFaceEmbeddings

from vanna.integrations.milvus import MilvusAgentMemory
from vanna.capabilities.agent_memory import (
    AgentMemory,
    TextMemory,
    TextMemorySearchResult,
    ToolMemory,
    ToolMemorySearchResult,
)
from vanna.core.tool import ToolContext


class MyMilvusAgentMemory(MilvusAgentMemory):
    """自定义 Milvus 记忆实现，使用 HuggingFace 嵌入模型生成向量。"""

    def _create_embedding(self, text: str) -> List[float]:
        """使用 BAAI/bge-m3 嵌入模型生成文本向量。"""
        embed_model = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
        return embed_model.embed_query(text)

    def _get_collection(self):
        """获取或创建 Milvus 集合，扩大了 question 字段长度。"""
        if self._collection is None:
            connections.connect(alias=self.alias, host=self.host, port=self.port)

            if not utility.has_collection(self.collection_name):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                    FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=10000),
                    FieldSchema(name="tool_name", dtype=DataType.VARCHAR, max_length=200),
                    FieldSchema(name="args_json", dtype=DataType.VARCHAR, max_length=5000),
                    FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=50),
                    FieldSchema(name="success", dtype=DataType.BOOL),
                    FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=5000),
                ]

                schema = CollectionSchema(fields=fields, description="工具使用记忆")
                collection = Collection(name=self.collection_name, schema=schema)

                # 创建向量索引
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

"""
数仓开发助手 Agent 入口。

基于双知识库（表结构 + 业务文档）的数仓加工 SQL 开发助手。
开发范围：DWD → DWS → ADS 分层架构。
使用 DeepSeek-R1 模型 + 双 Milvus 知识库。
启动后访问 http://localhost:8000
"""

from demo02.DWSystemPromptBuilder import DWSystemPromptBuilder
from demo02.LoggingLifecycleHook import LoggingLifecycleHook
from demo02.LoggingLlmMiddleware import LoggingLlmMiddleware
from demo02.LoggingObservabilityProvider import LoggingObservabilityProvider
from demo02.NoOpAgentMemory import NoOpAgentMemory
from demo02.knowledge_base import DualKnowledgeBaseManager
from demo02.knowledge_tools import SaveKnowledgeTool, SearchKnowledgeTool

from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.core.agent.config import AgentConfig
from vanna.servers.fastapi import VannaFastAPIServer
from vanna.integrations.openai import OpenAILlmService


# ============================================================
# 1. 配置 LLM（DeepSeek-R1，通过 SiliconFlow）
# ============================================================
llm = OpenAILlmService(
    model="deepseek-ai/DeepSeek-V3.2",
    base_url="https://api.siliconflow.cn/v1",
    api_key="sk-mtagmphpopbjpgngeludixffwdeicktszmsxtovwgslswlng"  # TODO: 替换为你的 API Key
)


# ============================================================
# 2. 配置双 Milvus 知识库
# ============================================================
kb_manager = DualKnowledgeBaseManager(
    host="172.16.11.57",
    port=19530,
    schema_collection="dw_schema_kb",      # 表结构知识库
    business_collection="dw_business_kb",   # 业务文档知识库
    dimension=1024,  # 与 BAAI/bge-m3 输出维度匹配
)


# ============================================================
# 3. 配置用户认证
# ============================================================
class SimpleUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        user_email = request_context.get_cookie('vanna_email') or 'guest@example.com'
        group = 'admin' if user_email == 'admin@example.com' else 'user'
        return User(id=user_email, email=user_email, group_memberships=[group])


# ============================================================
# 4. 组装 Agent
# ============================================================
user_resolver = SimpleUserResolver()
system_prompt_builder = DWSystemPromptBuilder()

# 注册知识库工具（使用双知识库管理器）
tools = ToolRegistry()
tools.register_local_tool(SaveKnowledgeTool(kb_manager), access_groups=['admin', 'user'])
tools.register_local_tool(SearchKnowledgeTool(kb_manager), access_groups=['admin', 'user'])

agent_config = AgentConfig(
    temperature=0.0,
    stream_responses=True,
)

agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=user_resolver,
    config=agent_config,
    system_prompt_builder=system_prompt_builder,
    agent_memory=NoOpAgentMemory(),
    observability_provider=LoggingObservabilityProvider(),
    lifecycle_hooks=[LoggingLifecycleHook()],
    llm_middlewares=[LoggingLlmMiddleware()],
)


# ============================================================
# 5. 启动 FastAPI 服务（双知识库上传 API 和页面）
# ============================================================
server = VannaFastAPIServer(agent)
app = server.create_app()

import logging
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel as PydanticBaseModel
from typing import List
import os

logger = logging.getLogger(__name__)

from demo02.schema_upload_page import get_schema_upload_html
from demo02.business_upload_page import get_business_upload_html
from demo02.custom_index_page import get_custom_index_html

# 移除框架默认的 "/" 路由，用自定义主页替换
app.routes[:] = [
    r for r in app.routes
    if not (isinstance(r, APIRoute) and r.path == "/")
]


class SchemaUploadRequest(PydanticBaseModel):
    """表结构上传请求体。"""
    table_name: str
    layer: str = ""
    ddl: str
    source_tables: str = ""


class KnowledgeUploadRequest(PydanticBaseModel):
    """业务文档上传请求体。"""
    content: str
    knowledge_type: str
    title: str = ""


class KnowledgeUploadResponse(PydanticBaseModel):
    """知识上传响应体。"""
    success: bool
    knowledge_id: str = ""
    message: str = ""


@app.get("/", response_class=HTMLResponse)
async def custom_index():
    """自定义主页，包含双知识库入口。"""
    return get_custom_index_html()


@app.get("/knowledge/schema", response_class=HTMLResponse)
async def schema_upload_page():
    """表结构知识上传页面。"""
    return get_schema_upload_html()


@app.get("/knowledge/business", response_class=HTMLResponse)
async def business_upload_page():
    """业务文档知识上传页面。"""
    return get_business_upload_html()


# 模板文件目录
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

# 模板文件映射：URL 参数 → 文件名 + 下载文件名
_TEMPLATES = {
    "schema": ("schema_template.md", "表结构知识库导入模板.md"),
    "requirement": ("requirement_template.md", "需求文档模板.md"),
    "development": ("development_template.md", "开发文档模板.md"),
}


@app.get("/api/templates/{template_name}")
async def download_template(template_name: str):
    """下载模板文件。"""
    if template_name not in _TEMPLATES:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")
    filename, download_name = _TEMPLATES[template_name]
    filepath = os.path.join(_TEMPLATE_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail=f"模板文件未找到: {filename}")
    return FileResponse(
        path=filepath,
        filename=download_name,
        media_type="text/markdown; charset=utf-8",
    )


@app.post("/api/knowledge/schema/upload", response_model=KnowledgeUploadResponse)
async def upload_schema_knowledge(req: SchemaUploadRequest):
    """上传表结构（table_name + ddl + source_tables）到表结构知识库。"""
    if not req.table_name or not req.ddl:
        raise HTTPException(status_code=400, detail="table_name 和 ddl 为必填字段")
    try:
        item = await kb_manager.save_schema(
            table_name=req.table_name,
            ddl=req.ddl,
            layer=req.layer,
            source_tables=req.source_tables,
        )
        return KnowledgeUploadResponse(
            success=True,
            knowledge_id=item.knowledge_id or "",
            message=f"已成功保存表结构 {item.table_name} 到表结构知识库",
        )
    except Exception as e:
        logger.error(f"上传表结构失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@app.post("/api/knowledge/business/upload", response_model=KnowledgeUploadResponse)
async def upload_business_knowledge(req: KnowledgeUploadRequest):
    """上传业务文档知识到业务文档知识库。"""
    valid_types = DualKnowledgeBaseManager.BUSINESS_TYPES
    if req.knowledge_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的知识类型: {req.knowledge_type}，支持: {', '.join(valid_types)}"
        )
    try:
        item = await kb_manager.save_business(
            content=req.content,
            knowledge_type=req.knowledge_type,
            title=req.title,
        )
        type_label = DualKnowledgeBaseManager.TYPE_LABELS.get(req.knowledge_type, req.knowledge_type)
        return KnowledgeUploadResponse(
            success=True,
            knowledge_id=item.knowledge_id or "",
            message=f"已成功保存{type_label}到业务文档知识库",
        )
    except Exception as e:
        logger.error(f"上传业务文档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@app.post("/api/knowledge/schema/upload_batch", response_model=List[KnowledgeUploadResponse])
async def upload_schema_batch(items: List[SchemaUploadRequest]):
    """批量上传表结构知识。"""
    results = []
    for req in items:
        if not req.table_name or not req.ddl:
            results.append(KnowledgeUploadResponse(success=False, message="table_name 和 ddl 为必填字段"))
            continue
        try:
            item = await kb_manager.save_schema(
                table_name=req.table_name, ddl=req.ddl,
                layer=req.layer, source_tables=req.source_tables,
            )
            results.append(KnowledgeUploadResponse(
                success=True, knowledge_id=item.knowledge_id or "",
                message=f"已成功保存表结构 {item.table_name} 到表结构知识库",
            ))
        except Exception as e:
            logger.error(f"批量上传表结构失败 [{req.table_name}]: {e}", exc_info=True)
            results.append(KnowledgeUploadResponse(success=False, message=f"保存失败: {str(e)}"))
    return results


@app.post("/api/knowledge/business/upload_batch", response_model=List[KnowledgeUploadResponse])
async def upload_business_batch(items: List[KnowledgeUploadRequest]):
    """批量上传业务文档知识。"""
    valid_types = DualKnowledgeBaseManager.BUSINESS_TYPES
    results = []
    for req in items:
        if req.knowledge_type not in valid_types:
            results.append(KnowledgeUploadResponse(
                success=False, message=f"无效的知识类型: {req.knowledge_type}，支持: {', '.join(valid_types)}",
            ))
            continue
        try:
            item = await kb_manager.save_business(
                content=req.content, knowledge_type=req.knowledge_type, title=req.title,
            )
            type_label = DualKnowledgeBaseManager.TYPE_LABELS.get(req.knowledge_type, req.knowledge_type)
            results.append(KnowledgeUploadResponse(
                success=True, knowledge_id=item.knowledge_id or "",
                message=f"已成功保存{type_label}到业务文档知识库",
            ))
        except Exception as e:
            logger.error(f"批量上传业务文档失败 [{req.title}]: {e}", exc_info=True)
            results.append(KnowledgeUploadResponse(success=False, message=f"保存失败: {str(e)}"))
    return results


# --- 启动服务 ---
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")  # 访问 http://localhost:8000

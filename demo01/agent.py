"""
知识库驱动的 Vanna Agent 入口。

使用 DeepSeek-R1 模型（通过 SiliconFlow API）+ Milvus 知识库。
去除了历史记忆搜索和 SQL 执行功能，专注于知识库管理和问答。
启动后访问 http://localhost:8000
"""

from demo01.KnowledgeSystemPromptBuilder import KnowledgeSystemPromptBuilder
from demo01.LoggingLifecycleHook import LoggingLifecycleHook
from demo01.LoggingLlmMiddleware import LoggingLlmMiddleware
from demo01.NoOpAgentMemory import NoOpAgentMemory
from demo01.knowledge_base import MilvusKnowledgeBase
from demo01.knowledge_tools import SaveKnowledgeTool, SearchKnowledgeTool

from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.core.agent.config import AgentConfig
from vanna.servers.fastapi import VannaFastAPIServer
from vanna.integrations.openai import OpenAILlmService


# ============================================================
# 1. 配置 LLM（DeepSeek-R1，通过 SiliconFlow 的 OpenAI 兼容接口）
# ============================================================
llm = OpenAILlmService(
    model="deepseek-ai/DeepSeek-R1",
    base_url="https://api.siliconflow.cn/v1",
    api_key="sk-mtagmphpopbjpgngeludixffwdeicktszmsxtovwgslswlng"  # TODO: 替换为你的 API Key
)


# ============================================================
# 2. 配置 Milvus 知识库
# ============================================================
knowledge_base = MilvusKnowledgeBase(
    host="172.16.11.57",
    port=19530,
    collection_name="vanna_knowledge_base",
    dimension=1024  # 与 BAAI/bge-m3 输出维度匹配
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
system_prompt_builder = KnowledgeSystemPromptBuilder()

# 注册知识库工具
tools = ToolRegistry()
tools.register_local_tool(SaveKnowledgeTool(knowledge_base), access_groups=['admin', 'user'])
tools.register_local_tool(SearchKnowledgeTool(knowledge_base), access_groups=['admin', 'user'])

# Agent 配置
agent_config = AgentConfig(
    temperature=0.0,       # DeepSeek-R1 推理模型建议低温度
    stream_responses=False  # 非流式响应，兼容性更好
)

agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=user_resolver,
    config=agent_config,
    system_prompt_builder=system_prompt_builder,
    agent_memory=NoOpAgentMemory(),  # 不使用历史记忆，传入空实现
    lifecycle_hooks=[LoggingLifecycleHook()],
    llm_middlewares=[LoggingLlmMiddleware()],
)


# ============================================================
# 5. 启动 FastAPI 服务（附加知识上传 API 和页面）
# ============================================================
server = VannaFastAPIServer(agent)
app = server.create_app()

# 替换框架默认的 "/" 路由为自定义主页（带知识管理按钮）
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel as PydanticBaseModel
from typing import Optional, List

from demo01.knowledge_upload_page import get_knowledge_upload_html
from demo01.custom_index_page import get_custom_index_html

# 移除框架注册的 "/" 路由，用自定义主页替换
app.routes[:] = [
    r for r in app.routes
    if not (isinstance(r, APIRoute) and r.path == "/")
]


@app.get("/", response_class=HTMLResponse)
async def custom_index():
    """自定义主页，包含知识管理入口按钮。"""
    return get_custom_index_html()


class KnowledgeUploadRequest(PydanticBaseModel):
    """知识上传请求体。"""
    content: str
    knowledge_type: str  # ddl / business / table-connect
    title: str = ""


class KnowledgeUploadResponse(PydanticBaseModel):
    """知识上传响应体。"""
    success: bool
    knowledge_id: str = ""
    message: str = ""


@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge_upload_page():
    """知识上传页面。"""
    return get_knowledge_upload_html()


@app.post("/api/knowledge/upload", response_model=KnowledgeUploadResponse)
async def upload_knowledge(req: KnowledgeUploadRequest):
    """直接上传知识到知识库（不经过 Agent）。"""
    valid_types = {"ddl", "business", "table-connect"}
    if req.knowledge_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的知识类型: {req.knowledge_type}，支持: {', '.join(valid_types)}"
        )
    try:
        item = await knowledge_base.save_knowledge(
            content=req.content,
            knowledge_type=req.knowledge_type,
            title=req.title,
        )
        type_labels = {"ddl": "建表语句", "business": "业务定义", "table-connect": "表关联定义"}
        return KnowledgeUploadResponse(
            success=True,
            knowledge_id=item.knowledge_id or "",
            message=f"已成功保存{type_labels[req.knowledge_type]}到知识库",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存知识失败: {str(e)}")


@app.post("/api/knowledge/upload_batch", response_model=List[KnowledgeUploadResponse])
async def upload_knowledge_batch(items: List[KnowledgeUploadRequest]):
    """批量上传知识到知识库。"""
    valid_types = {"ddl", "business", "table-connect"}
    results = []
    for req in items:
        if req.knowledge_type not in valid_types:
            results.append(KnowledgeUploadResponse(
                success=False,
                message=f"无效的知识类型: {req.knowledge_type}",
            ))
            continue
        try:
            item = await knowledge_base.save_knowledge(
                content=req.content,
                knowledge_type=req.knowledge_type,
                title=req.title,
            )
            type_labels = {"ddl": "建表语句", "business": "业务定义", "table-connect": "表关联定义"}
            results.append(KnowledgeUploadResponse(
                success=True,
                knowledge_id=item.knowledge_id or "",
                message=f"已成功保存{type_labels[req.knowledge_type]}到知识库",
            ))
        except Exception as e:
            results.append(KnowledgeUploadResponse(
                success=False,
                message=f"保存失败: {str(e)}",
            ))
    return results


# --- 启动服务 ---
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")  # 访问 http://localhost:8000

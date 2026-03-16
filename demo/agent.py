"""
自定义 Vanna Agent 入口。

使用 DeepSeek-R1 模型（通过 SiliconFlow API）+ Milvus 向量数据库。
启动后访问 http://localhost:8000
"""

from demo.MyMilvusAgentMemory import MyMilvusAgentMemory
from demo.MySystemPromptBuilder import MySystemPromptBuilder
from demo.LoggingLifecycleHook import LoggingLifecycleHook
from demo.LoggingLlmMiddleware import LoggingLlmMiddleware
from demo.LoggingObservabilityProvider import LoggingObservabilityProvider

from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.core.agent.config import AgentConfig
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
    SaveTextMemoryTool,
)
from vanna.servers.fastapi import VannaFastAPIServer
from vanna.integrations.openai import OpenAILlmService


# ============================================================
# 1. 配置 LLM（DeepSeek-R1，通过 SiliconFlow 的 OpenAI 兼容接口）
# ============================================================
llm = OpenAILlmService(
    model="deepseek-ai/DeepSeek-R1",
    base_url="https://api.siliconflow.cn/v1",
    api_key="sk-mtagmphpopbjpgngeludixffwdeicktszmsxtovwgslswlng"  # TODO: 在此填写你的 SiliconFlow API Key
)


# ============================================================
# 2. 配置 MySQL 数据库连接
# ============================================================
from vanna.integrations.mysql import MySQLRunner
db_tool = RunSqlTool(
    sql_runner=MySQLRunner(
        host="rm-wz9686w82tlcql2qm.mysql.rds.aliyuncs.com",       # TODO: 填写你的 MySQL 地址
        database="jd01_rpm",   # TODO: 填写你的数据库名
        user="root",       # TODO: 填写你的用户名
        password="HRdXK3TelK6bgGyg",   # TODO: 填写你的密码
        port=3306
    )
)


# ============================================================
# 3. 配置 Milvus 向量记忆
# ============================================================
agent_memory = MyMilvusAgentMemory(
    host="172.16.11.57",
    port=19530,
    collection_name="t_loan_order_vector",
    dimension=1024  # 与 BAAI/bge-m3 输出维度匹配
)


# ============================================================
# 4. 配置用户认证
# ============================================================
class SimpleUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        user_email = request_context.get_cookie('vanna_email') or 'guest@example.com'
        group = 'admin' if user_email == 'admin@example.com' else 'user'
        return User(id=user_email, email=user_email, group_memberships=[group])


# ============================================================
# 5. 组装 Agent
# ============================================================
user_resolver = SimpleUserResolver()
system_prompt_builder = MySystemPromptBuilder()

# 注册工具
tools = ToolRegistry()
tools.register_local_tool(db_tool, access_groups=['admin', 'user'])
tools.register_local_tool(SaveQuestionToolArgsTool(), access_groups=['admin'])
tools.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=['admin', 'user'])
tools.register_local_tool(SaveTextMemoryTool(), access_groups=['admin', 'user'])
tools.register_local_tool(VisualizeDataTool(), access_groups=['admin', 'user'])

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
    agent_memory=agent_memory,
    lifecycle_hooks=[LoggingLifecycleHook()],
    llm_middlewares=[LoggingLlmMiddleware()],
    # observability_provider=LoggingObservabilityProvider(),  # 按需开启
)


# ============================================================
# 6. 启动 FastAPI 服务
# ============================================================
server = VannaFastAPIServer(agent)
server.run()  # 访问 http://localhost:8000

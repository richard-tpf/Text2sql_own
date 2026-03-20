"""
日志 LLM 中间件（复用 demo01）。
"""

from vanna.core.llm import LlmRequest
from vanna.core.middleware import LlmMiddleware


class LoggingLlmMiddleware(LlmMiddleware):
    """记录 LLM 请求和响应的中间件。"""

    async def before_llm_request(self, request: "LlmRequest") -> "LlmRequest":
        print("===== LLM 请求 =====")
        for field_name, field_value in request.__dict__.items():
            print(f"  {field_name}: {field_value}")
        return request

    async def after_llm_response(
        self, request: "LlmRequest", response: "LlmResponse"
    ) -> "LlmResponse":
        print("===== LLM 响应 =====")
        for field_name, field_value in response.__dict__.items():
            print(f"  {field_name}: {field_value}")
        return response

"""
Minimal connection test for demo03.

Only validates connectivity:
1) LLM connectivity (SiliconFlow compatible endpoint)
2) Embedding connectivity (loads embedding model + runs embed_query once)

No Milvus access, no tool-calling.

Environment variables:
  SILICONFLOW_API_KEY      (required)
  SILICONFLOW_BASE_URL     (default: https://api.siliconflow.cn/v1)
  SILICONFLOW_MODEL        (default: deepseek-ai/DeepSeek-R1)
"""

from __future__ import annotations

import json
import os
import re
import traceback
from datetime import datetime
from typing import Any, Dict, Optional


def _get_embed_model_name_from_demo03() -> str:
    """
    Extract HuggingFaceEmbeddings model_name from demo03/knowledge_base.py
    without importing demo03 modules (avoid dependency/import issues).
    """
    default_name = "BAAI/bge-m3"
    kb_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "knowledge_base.py")
    )
    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception:
        return default_name

    m = re.search(
        r'HuggingFaceEmbeddings\(\s*model_name\s*=\s*"([^"]+)"\s*\)',
        src,
    )
    if not m:
        return default_name
    return m.group(1)


def _maybe_write_report(report_path: str, payload: Dict[str, Any]) -> None:
    md = f"""# demo03 Minimal Connection Test Result

Generated at: {datetime.now().isoformat()}

```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)


def _test_llm_connection(*, api_key: str, base_url: str, model: str) -> Dict[str, Any]:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "ping"},
            ],
            stream=False,
            temperature=0.0,
            max_tokens=24,
        )

        content: Optional[str] = None
        if resp and getattr(resp, "choices", None):
            choice0 = resp.choices[0]
            content = getattr(getattr(choice0, "message", None), "content", None)

        return {
            "ok": True,
            "model": model,
            "reply_preview": (content[:200] if content else None),
        }
    except Exception as e:
        return {
            "ok": False,
            "model": model,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }


def _test_embedding_connection(*, embed_model_name: str) -> Dict[str, Any]:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        emb = HuggingFaceEmbeddings(model_name=embed_model_name)
        vec = emb.embed_query("test connection")

        dim = None
        if isinstance(vec, list):
            dim = len(vec)

        return {
            "ok": True,
            "embed_model_name": embed_model_name,
            "vector_dim": dim,
        }
    except Exception as e:
        return {
            "ok": False,
            "embed_model_name": embed_model_name,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }


def main() -> None:
    api_key = os.getenv("SILICONFLOW_API_KEY", "sk-Ffxhvvk6z78RAeqUS9qq13RzeXe1rTUNMDGWNzRzXfZ1OT4C").strip()
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://yibuapi.com/v1").strip()
    model = os.getenv("SILICONFLOW_MODEL", "claude-opus-4-6").strip()

    report_path = os.path.join(
        os.path.dirname(__file__), "min_connection_test_result.md"
    )

    embed_model_name = _get_embed_model_name_from_demo03()

    if not api_key:
        payload = {
            "ok": False,
            "reason": "Missing SILICONFLOW_API_KEY",
            "base_url": base_url,
            "model": model,
            "embed_model_name_in_demo03": embed_model_name,
            "llm": {"ok": False, "error_type": "MissingAPIKey"},
        }
        _maybe_write_report(report_path, payload)
        print(f"[min_llm_model_test_runner] wrote: {report_path} (API key missing).")
        return

    llm_res = _test_llm_connection(api_key=api_key, base_url=base_url, model=model)
    embed_res = _test_embedding_connection(embed_model_name=embed_model_name)

    payload = {
        "started_at": datetime.now().isoformat(),
        "base_url": base_url,
        "model": model,
        "embed_model_name_in_demo03": embed_model_name,
        "llm": llm_res,
        "embedding": embed_res,
        "ok": bool(llm_res.get("ok")) and bool(embed_res.get("ok")),
    }
    _maybe_write_report(report_path, payload)
    print(f"[min_llm_model_test_runner] wrote: {report_path}")


if __name__ == "__main__":
    main()


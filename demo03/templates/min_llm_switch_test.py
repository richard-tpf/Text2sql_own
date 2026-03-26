"""
LLM 模型切换测试脚本。

用于测试变更 LLM 模型时的连通性和响应质量，Embedding 模型保持不变。
LLM 和 Embedding 使用独立的 URL 和 API Key。

使用方式：
    1. 直接运行：python min_llm_switch_test.py
    2. 指定模型：python min_llm_switch_test.py --model gpt-4o
    3. 批量测试：python min_llm_switch_test.py --batch
    4. 跳过 Embedding 测试：python min_llm_switch_test.py --skip-embedding

配置说明：
    - 修改 LLM_CONFIGS 字典添加新的 LLM 模型配置
    - 修改 EMBEDDING_CONFIG 配置 Embedding 服务（保持不变）
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# ============================================================
# Embedding 模型配置（保持不变）
# ============================================================
EMBEDDING_CONFIG = {
    "name": "BAAI/bge-m3",
    "model": "BAAI/bge-m3",           # 本地 HuggingFace 模型名
    "dimension": 1024,
    "type": "huggingface",            # 类型：huggingface（本地）或 api（远程）
    # 如果使用远程 Embedding API，配置以下字段：
    # "type": "api",
    # "base_url": "https://your-embedding-api.com/v1",
    # "api_key": "your-embedding-api-key",
}

# ============================================================
# LLM 模型配置区（修改这里切换模型）
# ============================================================

# 当前默认使用的 LLM 配置
DEFAULT_LLM_CONFIG = {
    "name": "claude-opus-4-6",
    "model": "claude-opus-4-6",
    "base_url": "https://yibuapi.com/v1",
    "api_key": "sk-mtagmphpopbjpgngeludixffwdeicktszmsxtovwgslswlng",
}

# 可选的 LLM 模型配置列表（用于批量测试或快速切换）
LLM_CONFIGS: Dict[str, Dict[str, str]] = {
    "claude-opus": {
        "name": "claude-opus-4-6",
        "model": "claude-opus-4-6",
        "base_url": "https://yibuapi.com/v1",
        "api_key": "sk-mtagmphpopbjpgngeludixffwdeicktszmsxtovwgslswlng",
    },
}

# ============================================================
# 测试用例
# ============================================================

TEST_PROMPTS = [
    {
        "name": "简单问答",
        "system": "你是一个简洁的助手。",
        "user": "你好，请用一句话介绍你自己。",
    },
    {
        "name": "SQL生成",
        "system": "你是一个数仓SQL开发专家，请根据需求生成SQL。",
        "user": "查询最近7天每天的订单数量，表名为 dwd_order_df，日期字段是 dt。",
    },
]


def test_llm_connection(
    *,
    model: str,
    base_url: str,
    api_key: str,
    test_prompt: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """测试 LLM 连通性和响应。"""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        
        prompt = test_prompt or TEST_PROMPTS[0]
        
        start_time = time.time()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            stream=False,
            temperature=0.0,
            max_tokens=512,
        )
        elapsed = time.time() - start_time

        content: Optional[str] = None
        if resp and getattr(resp, "choices", None):
            choice0 = resp.choices[0]
            content = getattr(getattr(choice0, "message", None), "content", None)

        # 提取 token 使用信息
        usage = {}
        if hasattr(resp, "usage") and resp.usage:
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "total_tokens": getattr(resp.usage, "total_tokens", None),
            }

        return {
            "ok": True,
            "model": model,
            "base_url": base_url,
            "test_name": prompt["name"],
            "response": content,
            "response_time_sec": round(elapsed, 2),
            "usage": usage,
        }
    except Exception as e:
        import traceback
        return {
            "ok": False,
            "model": model,
            "base_url": base_url,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }


def test_embedding_connection() -> Dict[str, Any]:
    """测试 Embedding 模型连通性。"""
    config = EMBEDDING_CONFIG
    embed_type = config.get("type", "huggingface")
    
    try:
        start_time = time.time()
        
        if embed_type == "huggingface":
            # 本地 HuggingFace 模型
            from langchain_huggingface import HuggingFaceEmbeddings
            emb = HuggingFaceEmbeddings(model_name=config["model"])
            vec = emb.embed_query("测试连接")
        elif embed_type == "api":
            # 远程 Embedding API（OpenAI 兼容接口）
            from openai import OpenAI
            client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"],
            )
            resp = client.embeddings.create(
                model=config["model"],
                input="测试连接",
            )
            vec = resp.data[0].embedding
        else:
            return {
                "ok": False,
                "error_message": f"不支持的 Embedding 类型: {embed_type}",
            }
        
        elapsed = time.time() - start_time
        dim = len(vec) if isinstance(vec, list) else None
        
        return {
            "ok": True,
            "type": embed_type,
            "model": config["model"],
            "base_url": config.get("base_url", "local"),
            "vector_dim": dim,
            "expected_dim": config.get("dimension"),
            "dim_match": dim == config.get("dimension"),
            "response_time_sec": round(elapsed, 2),
            "status": "unchanged (验证通过)",
        }
    except Exception as e:
        import traceback
        return {
            "ok": False,
            "type": embed_type,
            "model": config["model"],
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }


def run_single_test(config: Dict[str, str], verbose: bool = True) -> Dict[str, Any]:
    """运行单个 LLM 模型测试。"""
    name = config.get("name", config["model"])
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"测试 LLM 模型: {name}")
        print(f"  - model: {config['model']}")
        print(f"  - base_url: {config['base_url']}")
        print(f"{'='*60}")
    
    results = []
    for prompt in TEST_PROMPTS:
        result = test_llm_connection(
            model=config["model"],
            base_url=config["base_url"],
            api_key=config["api_key"],
            test_prompt=prompt,
        )
        results.append(result)
        
        if verbose:
            status = "✓ 成功" if result["ok"] else "✗ 失败"
            print(f"\n[{prompt['name']}] {status}")
            if result["ok"]:
                print(f"  响应时间: {result['response_time_sec']}s")
                print(f"  响应内容: {result['response'][:200] if result['response'] else 'N/A'}...")
            else:
                print(f"  错误: {result.get('error_message', 'Unknown')}")
    
    return {
        "config_name": name,
        "model": config["model"],
        "base_url": config["base_url"],
        "tests": results,
        "all_passed": all(r["ok"] for r in results),
    }


def run_batch_test(verbose: bool = True) -> List[Dict[str, Any]]:
    """批量测试所有配置的 LLM 模型。"""
    all_results = []
    
    for config_name, config in LLM_CONFIGS.items():
        result = run_single_test(config, verbose=verbose)
        all_results.append(result)
    
    return all_results


def generate_report(
    results: List[Dict[str, Any]],
    output_path: str,
    embed_status: Optional[Dict[str, Any]] = None,
) -> None:
    """生成测试报告。"""
    embed_info = embed_status or {}
    embed_ok = "✓ 通过" if embed_info.get("ok") else "✗ 失败"
    if embed_info.get("status") == "skipped":
        embed_ok = "跳过"
    
    report_lines = [
        "# LLM 模型切换测试报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Embedding 模型状态",
        "",
        f"- **模型**: `{EMBEDDING_CONFIG['model']}`",
        f"- **类型**: {EMBEDDING_CONFIG.get('type', 'huggingface')}",
        f"- **配置维度**: {EMBEDDING_CONFIG.get('dimension')}",
        f"- **测试状态**: {embed_ok}",
    ]
    
    if embed_info.get("ok") and embed_info.get("vector_dim"):
        report_lines.append(f"- **实际维度**: {embed_info['vector_dim']}")
        report_lines.append(f"- **响应时间**: {embed_info.get('response_time_sec', 'N/A')}s")
    elif not embed_info.get("ok") and embed_info.get("status") != "skipped":
        report_lines.append(f"- **错误**: {embed_info.get('error_message', 'Unknown')}")
    
    report_lines.extend([
        "",
        "## LLM 模型测试结果",
        "",
    ])
    
    for result in results:
        status = "✓ 全部通过" if result["all_passed"] else "✗ 存在失败"
        report_lines.extend([
            f"### {result['config_name']} {status}",
            "",
            f"- **model**: `{result['model']}`",
            f"- **base_url**: `{result['base_url']}`",
            "",
            "| 测试项 | 状态 | 响应时间 | 响应预览 |",
            "|--------|------|----------|----------|",
        ])
        
        for test in result["tests"]:
            if test["ok"]:
                preview = (test["response"] or "")[:50].replace("\n", " ")
                report_lines.append(
                    f"| {test['test_name']} | ✓ | {test['response_time_sec']}s | {preview}... |"
                )
            else:
                report_lines.append(
                    f"| {test['test_name']} | ✗ | - | {test.get('error_type', 'Error')} |"
                )
        
        report_lines.append("")
    
    # 添加原始 JSON 数据
    report_lines.extend([
        "## 原始测试数据",
        "",
        "```json",
        json.dumps(results, ensure_ascii=False, indent=2),
        "```",
    ])
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print(f"\n测试报告已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="LLM 模型切换测试脚本")
    parser.add_argument(
        "--model",
        type=str,
        help="指定要测试的模型配置名称（在 LLM_CONFIGS 中定义）",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="批量测试所有配置的 LLM 模型",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="min_llm_switch_test_result.md",
        help="测试报告输出路径（默认: min_llm_switch_test_result.md）",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式，只输出报告",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="跳过 Embedding 测试（仅测试 LLM）",
    )
    
    args = parser.parse_args()
    verbose = not args.quiet
    
    print("=" * 60)
    print("LLM 模型切换测试")
    print(f"Embedding 模型: {EMBEDDING_CONFIG['model']} (保持不变)")
    print("=" * 60)
    
    # 测试 Embedding 连通性（除非跳过）
    embed_status = None
    if not getattr(args, 'skip_embedding', False):
        if verbose:
            print(f"\n测试 Embedding 模型: {EMBEDDING_CONFIG['model']}")
            print(f"  - type: {EMBEDDING_CONFIG.get('type', 'huggingface')}")
            if EMBEDDING_CONFIG.get('base_url'):
                print(f"  - base_url: {EMBEDDING_CONFIG['base_url']}")
        
        embed_status = test_embedding_connection()
        
        if verbose:
            if embed_status["ok"]:
                print(f"  ✓ 连接成功，维度: {embed_status['vector_dim']}，耗时: {embed_status['response_time_sec']}s")
            else:
                print(f"  ✗ 连接失败: {embed_status.get('error_message', 'Unknown')}")
    else:
        embed_status = {
            "ok": True,
            "model": EMBEDDING_CONFIG["model"],
            "status": "skipped",
            "note": "用户跳过 Embedding 测试",
        }
        if verbose:
            print(f"\n[Embedding] 跳过测试: {EMBEDDING_CONFIG['model']}")
    
    results = []
    
    if args.batch:
        # 批量测试
        if not LLM_CONFIGS:
            print("\n警告: LLM_CONFIGS 为空，请先配置要测试的模型")
            return
        results = run_batch_test(verbose=verbose)
    elif args.model:
        # 测试指定模型
        if args.model not in LLM_CONFIGS:
            print(f"\n错误: 未找到模型配置 '{args.model}'")
            print(f"可用配置: {list(LLM_CONFIGS.keys())}")
            return
        result = run_single_test(LLM_CONFIGS[args.model], verbose=verbose)
        results.append(result)
    else:
        # 测试默认配置
        result = run_single_test(DEFAULT_LLM_CONFIG, verbose=verbose)
        results.append(result)
    
    # 生成报告
    import os
    report_path = os.path.join(os.path.dirname(__file__), args.report)
    generate_report(results, report_path, embed_status)
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    for r in results:
        status = "✓ PASS" if r["all_passed"] else "✗ FAIL"
        print(f"  {r['config_name']}: {status}")


if __name__ == "__main__":
    main()

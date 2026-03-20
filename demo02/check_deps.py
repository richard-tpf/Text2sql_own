"""
demo02 项目依赖检查脚本。

用法：python demo02/check_deps.py
"""

import importlib
import sys

# demo02 项目所需的第三方包列表
# 格式：(import 名称, pip 安装名称, 用途说明)
REQUIRED_PACKAGES = [
    ("pydantic", "pydantic>=2.0.0", "数据模型定义"),
    ("pymilvus", "pymilvus", "Milvus 向量数据库客户端"),
    ("langchain_huggingface", "langchain-huggingface", "HuggingFace embedding 模型封装"),
    ("fastapi", "fastapi>=0.68.0", "Web 框架"),
    ("uvicorn", "uvicorn>=0.15.0", "ASGI 服务器"),
    ("openai", "openai", "OpenAI 兼容 LLM 调用（DeepSeek）"),
    ("vanna", "vanna（本项目，需 pip install -e .）", "Agent 框架本体"),
]

# langchain-huggingface 的关键子依赖（自动安装，但也检查一下）
SUB_DEPENDENCIES = [
    ("transformers", "transformers", "HuggingFace 模型加载"),
    ("sentence_transformers", "sentence-transformers", "句向量模型"),
    ("torch", "torch", "PyTorch 深度学习框架"),
    ("langchain_core", "langchain-core", "LangChain 核心库"),
]


def check_package(import_name: str, pip_name: str, desc: str) -> bool:
    """检查单个包是否可导入，返回是否成功。"""
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "未知版本")
        print(f"  ✅ {import_name} ({version}) — {desc}")
        return True
    except ImportError:
        print(f"  ❌ {import_name} — 未安装！安装命令: pip install {pip_name}")
        return False


def main():
    print("=" * 60)
    print("demo02 项目依赖检查")
    print("=" * 60)

    print("\n【核心依赖】")
    core_ok = 0
    core_fail = 0
    for import_name, pip_name, desc in REQUIRED_PACKAGES:
        if check_package(import_name, pip_name, desc):
            core_ok += 1
        else:
            core_fail += 1

    print("\n【子依赖（由 langchain-huggingface 自动安装）】")
    sub_ok = 0
    sub_fail = 0
    for import_name, pip_name, desc in SUB_DEPENDENCIES:
        if check_package(import_name, pip_name, desc):
            sub_ok += 1
        else:
            sub_fail += 1

    # 额外检查：BAAI/bge-m3 模型是否已下载
    print("\n【Embedding 模型检查】")
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        print("  ⏳ 正在检查 BAAI/bge-m3 模型是否可加载（首次可能需要下载）...")
        model = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
        vec = model.embed_query("测试")
        print(f"  ✅ BAAI/bge-m3 模型加载成功，向量维度: {len(vec)}")
    except ImportError:
        print("  ⚠️  跳过模型检查（langchain-huggingface 未安装）")
    except Exception as e:
        print(f"  ❌ BAAI/bge-m3 模型加载失败: {e}")
        print("     可能原因：网络不通、磁盘空间不足、模型未下载")

    # 额外检查：Milvus 连接
    print("\n【Milvus 连接检查】")
    try:
        from pymilvus import connections
        connections.connect(alias="check_test", host="172.16.11.57", port=19530, timeout=5)
        print("  ✅ Milvus 连接成功 (172.16.11.57:19530)")
        connections.disconnect("check_test")
    except ImportError:
        print("  ⚠️  跳过连接检查（pymilvus 未安装）")
    except Exception as e:
        print(f"  ❌ Milvus 连接失败: {e}")
        print("     请确认 Milvus 服务已启动且网络可达")

    # 汇总
    total_fail = core_fail + sub_fail
    print("\n" + "=" * 60)
    print(f"核心依赖: {core_ok} 通过, {core_fail} 缺失")
    print(f"子依赖:   {sub_ok} 通过, {sub_fail} 缺失")
    if total_fail == 0:
        print("\n🎉 所有依赖检查通过！")
    else:
        print(f"\n⚠️  共 {total_fail} 个包缺失，请按上面提示安装。")
        print("\n快速安装所有核心依赖：")
        print("  pip install pydantic pymilvus langchain-huggingface fastapi uvicorn openai")
        print("  pip install -e .  # 安装 vanna 本体")
    print("=" * 60)

    sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    main()

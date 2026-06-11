"""
Agent 测试脚本

用法:
    python test.py                              # 默认测试
    python test.py "如何更换滤网"                # 指定问题
    python test.py --mode stream "今天天气"      # 流式输出测试
    python test.py --mode search "WIFI设置"     # 知识库检索测试
    python test.py --mode full "扫地机器人"      # 完整测试（流式 + 检索）
"""

import argparse
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def test_stream(query: str, history: list[dict] | None = None):
    """测试流式输出：逐帧打印，每帧带序号和耗时。"""
    from agent.react_agent import ReactAgent

    agent = ReactAgent()

    print(f"\n{'=' * 60}")
    print(f"  流式输出测试")
    print(f"{'=' * 60}")
    print(f"  问题: {query}")
    print(f"  History: {len(history or [])} 条")
    print(f"{'─' * 60}")

    chunk_count = 0
    total_chars = 0
    t0 = time.time()

    for chunk in agent.execute_stream(query, history=history):
        chunk_count += 1
        total_chars += len(chunk)
        print(chunk, end="", flush=True)

    elapsed = time.time() - t0
    print(f"\n{'─' * 60}")
    print(f"  帧数: {chunk_count}  字符数: {total_chars}  耗时: {elapsed:.2f}s")
    print(f"{'=' * 60}\n")


def test_non_stream(query: str, history: list[dict] | None = None):
    """测试非流式输出：一次性返回完整回答。"""
    from agent.react_agent import ReactAgent

    agent = ReactAgent()

    print(f"\n{'=' * 60}")
    print(f"  非流式输出测试")
    print(f"{'=' * 60}")
    print(f"  问题: {query}")
    print(f"{'─' * 60}")

    t0 = time.time()
    answer = agent.execute(query, history=history)
    elapsed = time.time() - t0

    print(answer)
    print(f"{'─' * 60}")
    print(f"  字符数: {len(answer)}  耗时: {elapsed:.2f}s")
    print(f"{'=' * 60}\n")


def test_search(query: str):
    """测试知识库检索：打印匹配结果。"""
    from rag.rag_service import get_rag_service

    rag = get_rag_service()

    print(f"\n{'=' * 60}")
    print(f"  知识库检索测试")
    print(f"{'=' * 60}")
    print(f"  查询: {query}")
    print(f"{'─' * 60}")

    t0 = time.time()
    results = rag.search(query)
    elapsed = time.time() - t0

    if not results:
        print("  未检索到相关参考资料。")
    else:
        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] 相似度: {r['score']:.3f}  |  分类: {r['category']}  |  {r['source']}")
            print(f"      {r['content'][:120]}...")

    print(f"\n{'─' * 60}")
    print(f"  结果数: {len(results)}  耗时: {elapsed:.2f}s")
    print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Agent 测试工具")
    parser.add_argument("query", nargs="?", default="如何更换扫地机器人的滤网", help="测试问题")
    parser.add_argument("--mode", "-m", choices=["stream", "non-stream", "search", "full"],
                        default="stream", help="测试模式 (默认: stream)")
    parser.add_argument("--history", "-H", action="store_true", help="附带模拟对话历史")
    args = parser.parse_args()

    history = None
    if args.history:
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！我是扫地机器人智能客服，有什么可以帮你的？"},
        ]

    if args.mode in ("stream", "full"):
        test_stream(args.query, history)
    if args.mode in ("non-stream", "full"):
        test_non_stream(args.query, history)
    if args.mode in ("search", "full"):
        test_search(args.query)


if __name__ == "__main__":
    main()

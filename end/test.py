"""
Agent 流式输出测试

用法:
    python test.py                              # 默认问题
    python test.py "如何更换滤网"                 # 指定问题
    python test.py -m chat_only "今天心情不错"    # 仅聊天模式
    python test.py -H "我刚才问了什么"            # 附带对话历史
"""

import argparse
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SEP = "-" * 60
BOLD = "=" * 60


def main():
    parser = argparse.ArgumentParser(description="Agent 流式输出测试")
    parser.add_argument("query", nargs="?", default="如何更换扫地机器人的滤网", help="测试问题")
    parser.add_argument("--mode", "-m", choices=["chat", "chat_only"], default="chat", help="Agent 模式")
    parser.add_argument("--history", "-H", action="store_true", help="附带模拟对话历史")
    args = parser.parse_args()

    history = None
    if args.history:
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！我是扫地机器人智能客服，有什么可以帮你的？"},
        ]

    from agent.react_agent import ReactAgent

    agent = ReactAgent()

    print(f"\n{BOLD}")
    print(f"  流式测试 [mode={args.mode}]")
    print(f"{BOLD}")
    print(f"  问题: {args.query}")
    print(f"  History: {len(history or [])} 条")
    print(SEP)

    frames, chars, t0 = 0, 0, time.time()
    last_t = t0

    for chunk in agent.execute_stream(args.query, history=history, mode=args.mode):
        dt = time.time() - last_t
        frames += 1
        chars += len(chunk)
        if dt > 1:
            print(f"\n[{frames}|+{dt:.1f}s] ", end="", flush=True)
        print(chunk, end="", flush=True)
        last_t = time.time()

    elapsed = time.time() - t0
    print(f"\n{SEP}")
    print(f"  帧数: {frames}  字符数: {chars}  耗时: {elapsed:.2f}s")
    print(f"{BOLD}\n")


if __name__ == "__main__":
    main()

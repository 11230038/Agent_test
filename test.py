import argparse
from agent.react_agent import ReactAgent


def main():
    parser = argparse.ArgumentParser(description="测试 ReactAgent 的流式输出")
    parser.add_argument(
        "query",
        nargs="?",
        default="请先介绍一下你自己，再告诉我北京今天天气怎么样。",
        help="发送给智能客服的测试问题",
    )
    args = parser.parse_args()

    agent = ReactAgent()

    print(f"测试问题：{args.query}")
    print("模型回复：")
    print("-" * 40)

    for chunk in agent.execute_stream(args.query):
        print(chunk, end="", flush=True)

    print("\n" + "-" * 40)
    print("测试完成")


if __name__ == "__main__":
    main()

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from model.factor import get_chat_model
from utils.prompt_loader import load_system_prompts, load_chat_prompts
from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, get_user_id,
                                     get_user_profile, get_current_date, fetch_external_data,
                                     save_user_note, fill_context_for_report,
                                     set_user_context, clear_user_context)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from utils.logger_handler import loggers

# 超过此阈值自动压缩历史
HISTORY_COMPRESS_LIMIT = 15
HISTORY_KEEP_RECENT = 8

COMPRESS_PROMPT = """请用 2-3 句话总结以下对话的关键信息，包括用户的需求、偏好、已讨论的问题和结论：

{dialogue}

总结："""


class AgentInitializationError(RuntimeError):
    pass


class AgentExecutionError(RuntimeError):
    pass


class ReactAgent:
    def __init__(self):
        try:
            system_prompt = load_system_prompts()
            if not system_prompt:
                raise ValueError("系统提示词加载失败")

            self.agent = create_agent(
                model=get_chat_model(),
                system_prompt=system_prompt,
                tools=[rag_summarize, get_weather, get_user_location, get_user_id,
                       get_user_profile, get_current_date, fetch_external_data, save_user_note,
                       fill_context_for_report],
                middleware=[monitor_tool, log_before_model, report_prompt_switch],
            )

            chat_prompt = load_chat_prompts()
            if not chat_prompt:
                raise ValueError("聊天提示词加载失败")

            self.chat_agent = create_agent(
                model=get_chat_model(),
                system_prompt=chat_prompt,
                tools=[],
                middleware=[log_before_model],
            )
        except Exception as e:
            raise AgentInitializationError(f"Agent 初始化失败:{e}") from e

    def _compress_history(self, history: list[dict]) -> list[dict]:
        """压缩长历史：将旧消息浓缩为摘要，保留近期消息。"""
        if len(history) <= HISTORY_COMPRESS_LIMIT:
            return history

        old_part = history[:-HISTORY_KEEP_RECENT]
        recent_part = history[-HISTORY_KEEP_RECENT:]

        dialogue = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:200]}"
            for m in old_part
        )
        try:
            model = get_chat_model()
            summary = model.invoke(COMPRESS_PROMPT.format(dialogue=dialogue)).content
            loggers.info(f"历史压缩: {len(old_part)} 条 → {len(summary)} 字摘要")
        except Exception:
            summary = f"之前的对话涵盖了大量关于扫地机器人的咨询。"
            loggers.warning("历史压缩失败，使用默认摘要")

        return [{"role": "assistant", "content": f"[对话摘要] 之前聊了这些内容：{summary}"}] + recent_part

    def execute(self, query: str, history: list[dict] | None = None, trace_id: str | None = None, user_context: dict | None = None, mode: str = "chat"):
        parts = []
        for chunk in self.execute_stream(query, history=history, trace_id=trace_id, user_context=user_context, mode=mode):
            parts.append(chunk)
        return "".join(parts)

    def execute_stream(self, query: str, history: list[dict] | None = None, trace_id: str | None = None, user_context: dict | None = None, mode: str = "chat"):
        set_user_context(user_context)
        try:
            messages = []

            if history:
                history = self._compress_history(history)
                for msg in history:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role and content:
                        messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": query})

            input_dict = {"messages": messages}

            if trace_id:
                loggers.info(f"[{trace_id}] Agent 开始执行, messages_count={len(messages)}")

            # stream_mode="values" 返回完整状态，包含思考过程的中间消息
            # 只输出最终回答的增量，过滤掉思考步骤
            last_content = ""
            agent = self.chat_agent if mode == "chat_only" else self.agent
            is_report = mode == "report"
            for chunk in agent.stream(input_dict, stream_mode="values", context={"report": is_report}):
                latest_message = chunk["messages"][-1]
                # 跳过非 AI 消息和带 tool_calls 的中间推理步骤
                if not isinstance(latest_message, AIMessage):
                    continue
                if hasattr(latest_message, "tool_calls") and latest_message.tool_calls:
                    last_content = ""  # 新一轮回答开始，重置
                    continue
                content = latest_message.content or ""
                if content and content != last_content:
                    delta = content[len(last_content):]
                    last_content = content
                    yield delta
        except Exception as e:
            raise AgentExecutionError(f"Agent 执行失败:{e}") from e
        finally:
            clear_user_context()


if __name__ == '__main__':
    agent = ReactAgent()

    for chunk in agent.execute_stream("给我生成我的使用报告"):
        print(chunk, end="", flush=True)

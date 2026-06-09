from langchain.agents.middleware import wrap_tool_call,before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from typing import Callable
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from utils.logger_handler import loggers
from langchain.agents import AgentState
from langgraph.runtime import Runtime

from utils.path_tool import get_abs_path
from utils.prompt_loader import load_report_prompts,load_system_prompts


#监控工具执行
@wrap_tool_call
def monitor_tool(
        # 请求数据
        request:ToolCallRequest,
        #执行的函数
        handler:Callable[[ToolCallRequest],ToolMessage|Command],
):
    loggers.info(f"工具执行开始:{request.tool_call['name']}")
    loggers.info(f"工具执行参数:{request.tool_call['args']}")
    try:
          loggers.info(f"工具执行结束:{request.tool_call['name']}")
          if request.tool_call["name"]=="fill_context_for_report":
              request.runtime.context["report"]=True
          return  handler(request)
    except Exception as e:
        loggers.error(f"工具执行出错:{request.tool_call['name']},错误信息:{e}")
        raise e

#在模型执行前输出日志
@before_model
def log_before_model(
        #状态记录
        state:AgentState,
        #上下文信息
        runtime:Runtime,
):
    loggers.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息。")

    loggers.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content.strip()}")

    return None

#动态切换提示词
@dynamic_prompt # 生成提示词前调用此函数
def report_prompt_switch(request:ModelRequest):
    is_report = request.runtime.context.get("report", False)
    if is_report:
        #返回报告生成提示词
        return load_report_prompts()
    return load_system_prompts()




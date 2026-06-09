from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import loggers

def load_system_prompts():
    try:
        system_prompt_path=get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        loggers.error(f"系统提示出错:{e}")
        return None
    try:
        return open(system_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        loggers.error(f"系统提示出错:{e}")
        return None

def load_rag_prompts():
    try:
        rag_prompt_path=get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        loggers.error(f"RAG提示出错:{e}")
        return None
    try:
       return open(rag_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        loggers.error(f"RAG提示出错:{e}")
        return None

def load_report_prompts():
    try:
        report_prompt_path=get_abs_path(prompts_conf["report_prompt_path"])
    except KeyError as e:
        loggers.error(f"报告提示出错:{e}")
        return None
    try:
       return open(report_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        loggers.error(f"报告提示出错:{e}")
        return None

if __name__=="__main__":
    print(load_system_prompts())
    print(load_rag_prompts())
    print(load_report_prompts())
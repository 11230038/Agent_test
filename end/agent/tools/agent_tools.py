from langchain_core.tools import tool
from rag.rag_service import rag
import random
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
import os
from utils.logger_handler import loggers

external_data={}

@tool(description="从向量存储中检索参考资料")
def rag_summarize(query:str)->str:
    return rag.rag_summarize(query)

@tool(description="获取天气信息")
def get_weather(city:str)->str:
    return f"今天{city}的天气是雨夹雪"

@tool(description="获取用户所在城市")
def get_user_location()->str:
    return random.choice(["北京","天津","青岛"])

@tool(description="获取用户ID")
def get_user_id()->str:
    return random.choice(["1001","1002","1003","1004","1005","1006","1007","1008","1009","1010"])

@tool(description="获取当前月份")
def get_current_month()->str:
    return random.choice(["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"])

def generate_external_data():
    if not external_data:
        external_data_path=get_abs_path(agent_conf["external_data"])
        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"未找到外部数据目录:{external_data_path}")
        with open(external_data_path,"r",encoding="utf-8")as f:
            for line in f.readlines()[1:]:
                arr:list[str]=line.strip().split(",")
                user_id:str=arr[0].replace('"',"")
                feature:str=arr[1].replace('"',"")
                efficiency:str=arr[2].replace('"',"")
                consumables:str=arr[3].replace('"',"")
                comparison:str=arr[4].replace('"', "")
                time:str=arr[5].replace('"',"")
                if user_id not in external_data:
                    external_data[user_id] = {}
                external_data[user_id][time]={
                        "特征":feature,
                        "效率":efficiency,
                        "耗材":consumables,
                        "对比":comparison,
                    }

@tool(description="获取用户使用记录")
def fetch_external_data(user_id:str,month:str)->str:
    generate_external_data()
    try:
        return external_data[user_id][month]
    except KeyError:
        loggers.error(f"用户使用记录不存在:{user_id}")
        return ""

@tool(description="为提示词切换提供上下文")
def fill_context_for_report():
    return "fill_context_for_report已调用"

if __name__=="__main__":
    print(fetch_external_data.invoke({"user_id": "1004", "month": "2025-02"}))

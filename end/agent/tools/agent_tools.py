from langchain_core.tools import tool
from rag.rag_service import get_rag_service
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
from utils import session_store
import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from utils.logger_handler import loggers

external_data = {}
_user_context: dict = {}
_last_rag_sources: list[dict] = []


def get_last_rag_sources() -> list[dict]:
    return _last_rag_sources


def set_user_context(ctx: dict | None):
    global _user_context
    _user_context = ctx or {}


def clear_user_context():
    global _user_context
    _user_context = {}


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    global _last_rag_sources
    try:
        result = get_rag_service().rag_summarize(query)
        _last_rag_sources = result.get("sources", [])
        return result.get("answer", "未检索到相关参考资料。")
    except Exception as e:
        loggers.error(f"RAG调用失败,错误信息:{e}")
        _last_rag_sources = []
        return "知识库暂不可用，请稍后重试。"


def _fetch_real_weather(city: str) -> str | None:
    try:
        encoded_city = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded_city}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "RobotAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        current = data.get("current_condition", [{}])[0]
        desc = current.get("weatherDesc", [{}])[0].get("value", "未知")
        temp = current.get("temp_C", "?")
        humidity = current.get("humidity", "?")

        return f"今天{city}的天气：{desc}，气温{temp}°C，湿度{humidity}%"
    except Exception as e:
        loggers.warning(f"获取真实天气失败({city}):{e}")
        return None


@tool(description="获取天气信息")
def get_weather(city: str) -> str:
    real = _fetch_real_weather(city)
    if real:
        return real
    return f"今天{city}的天气是雨夹雪（天气服务暂不可用，以下为默认数据）"


def _fetch_ip_location() -> str | None:
    try:
        url = "http://ip-api.com/json/"
        req = urllib.request.Request(url, headers={"User-Agent": "RobotAgent/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") != "success":
            return None

        city = data.get("city", "")
        country = data.get("country", "")
        if not city:
            return None

        if country and country != "China":
            return f"{country} {city}"
        return city
    except Exception as e:
        loggers.warning(f"IP定位失败:{e}")
        return None


@tool(description="获取用户所在城市")
def get_user_location() -> str:
    city = _user_context.get("city")
    if city:
        return city
    ip_city = _fetch_ip_location()
    if ip_city:
        return ip_city
    return "未知城市"


@tool(description="获取用户ID")
def get_user_id() -> str:
    user_id = _user_context.get("user_id")
    if user_id:
        return user_id
    return "未知用户"


@tool(description="获取当前用户的完整画像，包括城市、性别、年龄、偏好等")
def get_user_profile() -> str:
    user_id = _user_context.get("user_id", "")
    if not user_id or user_id == "未知用户":
        return "暂无用户画像：用户ID未知"
    profile = session_store.get_profile(user_id)
    if not profile:
        return "暂无用户画像"
    return json.dumps({
        "city": profile.get("city", ""),
        "gender": profile.get("gender", ""),
        "age": profile.get("age", 0),
        "preferences": profile.get("preferences", {}),
    }, ensure_ascii=False)


@tool(description="获取当前日期")
def get_current_date() -> str:
    month = _user_context.get("month")
    if month:
        return month
    return datetime.now().strftime("%Y-%m-%d")


def generate_external_data():
    if not external_data:
        external_data_path = get_abs_path(agent_conf["external_data"])
        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"未找到外部数据目录:{external_data_path}")
        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")
                user_id: str = arr[0].replace('"', "")
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                comparison: str = arr[4].replace('"', "")
                time: str = arr[5].replace('"', "")
                if user_id not in external_data:
                    external_data[user_id] = {}
                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }


@tool(description="获取用户使用记录")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()
    try:
        return external_data[user_id][month]
    except KeyError:
        loggers.error(f"用户使用记录不存在:{user_id}")
        return ""


@tool(description="记住用户说的偏好、需求或备注，key 是分类标签，value 是具体内容")
def save_user_note(key: str, value: str) -> str:
    user_id = _user_context.get("user_id", "")
    if not user_id or user_id == "未知用户":
        return "无法保存：用户ID未知，请先确认用户身份"
    try:
        session_store.merge_profile(user_id, new_prefs={key: value})
        loggers.info(f"用户备注已保存: user={user_id} {key}={value}")
        return f"已记住：{key} → {value}"
    except Exception as e:
        loggers.error(f"保存用户备注失败:{e}")
        return f"保存失败：{e}"


@tool(description="为提示词切换提供上下文")
def fill_context_for_report():
    return "fill_context_for_report已调用"


if __name__ == "__main__":
    print(fetch_external_data.invoke({"user_id": "1004", "month": "2025-02"}))

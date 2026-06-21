"""会话持久化存储（MySQL）：对话历史 + 用户画像。"""

import os
import json
import time
import pymysql
from utils.config_handler import api_conf
from utils.logger_handler import loggers

_DB = None


def _get_db():
    global _DB
    if _DB is None:
        cfg = api_conf.get("mysql", {})
        _DB = {
            "host": cfg.get("host", "127.0.0.1"),
            "port": cfg.get("port", 3306),
            "user": cfg.get("user", "root"),
            "password": cfg.get("password", "root"),
            "database": cfg.get("database", "robot_agent"),
            "charset": "utf8mb4",
            "auth_plugin_map": {"mysql_native_password": None, "caching_sha2_password": None},
        }
    return _DB


def _connect():
    db = _get_db()
    try:
        conn = pymysql.connect(**db)
        loggers.debug(f"MySQL 连接成功: {db['host']}:{db['port']}/{db['database']}")
        return conn
    except Exception as e:
        loggers.error(f"MySQL 连接失败: {db['host']}:{db['port']}/{db['database']} - {e}")
        raise


def _init():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    role VARCHAR(16) NOT NULL,
                    content TEXT NOT NULL,
                    created_at DOUBLE NOT NULL,
                    mode VARCHAR(32) DEFAULT 'chat',
                    INDEX idx_session (session_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id VARCHAR(64) PRIMARY KEY,
                    city VARCHAR(64) DEFAULT '',
                    gender VARCHAR(8) DEFAULT '',
                    age INT DEFAULT 0,
                    preferences TEXT,
                    updated_at DOUBLE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


def save_message(session_id: str, role: str, content: str, mode: str = "chat"):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (session_id, role, content, created_at, mode) VALUES (%s, %s, %s, %s, %s)",
                (session_id, role, content, time.time(), mode),
            )
        conn.commit()
        loggers.debug(f"DB INSERT messages: {session_id} {role} len={len(content)} mode={mode}")
    finally:
        conn.close()


def get_session_history(session_id: str, limit: int = 50) -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC LIMIT %s",
                (session_id, limit),
            )
            rows = cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]
    finally:
        conn.close()


def list_sessions(limit: int = 20, mode: str = "") -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            if mode:
                cur.execute("""
                    SELECT m.session_id, COUNT(*) as msg_count, MAX(m.created_at) as last_active,
                        (SELECT content FROM messages WHERE session_id = m.session_id AND role = 'user'
                         ORDER BY created_at ASC LIMIT 1) as preview
                    FROM messages m
                    WHERE m.session_id IN (SELECT DISTINCT session_id FROM messages WHERE mode = %s)
                    GROUP BY m.session_id
                    ORDER BY last_active DESC LIMIT %s
                """, (mode, limit))
            else:
                cur.execute("""
                    SELECT m.session_id, COUNT(*) as msg_count, MAX(m.created_at) as last_active,
                        (SELECT content FROM messages WHERE session_id = m.session_id AND role = 'user'
                         ORDER BY created_at ASC LIMIT 1) as preview
                    FROM messages m
                    GROUP BY m.session_id
                    ORDER BY last_active DESC LIMIT %s
                """, (limit,))
            rows = cur.fetchall()
        return [{"session_id": r[0], "msg_count": r[1], "last_active": r[2], "preview": r[3] or ""} for r in rows]
    finally:
        conn.close()


def delete_session(session_id: str):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


def save_profile(user_id: str, city: str = "", gender: str = "", age: int = 0, preferences: dict | None = None):
    conn = _connect()
    try:
        prefs = json.dumps(preferences or {}, ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO profiles (user_id, city, gender, age, preferences, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE city=VALUES(city), gender=VALUES(gender), "
                "age=VALUES(age), preferences=VALUES(preferences), updated_at=VALUES(updated_at)",
                (user_id, city, gender, age, prefs, time.time()),
            )
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


def merge_profile(user_id: str, city: str = "", gender: str = "", age: int = 0, new_prefs: dict | None = None):
    existing = get_profile(user_id)
    if existing:
        merged_prefs = existing.get("preferences", {})
        merged_city = city or existing.get("city", "")
        merged_gender = gender or existing.get("gender", "")
        merged_age = age or existing.get("age", 0)
    else:
        merged_prefs = {}
        merged_city = city
        merged_gender = gender
        merged_age = age
    if new_prefs:
        merged_prefs.update(new_prefs)
    save_profile(user_id, merged_city, merged_gender, merged_age, merged_prefs)


# ── 反馈存储 ──

def _init_feedback():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    rating VARCHAR(16) NOT NULL,
                    comment TEXT,
                    created_at DOUBLE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


def save_feedback(session_id: str, rating: str, comment: str = ""):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (session_id, rating, comment, created_at) VALUES (%s, %s, %s, %s)",
                (session_id, rating, comment, time.time()),
            )
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


def get_feedback_stats() -> dict:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM feedback")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'like'")
            likes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'dislike'")
            dislikes = cur.fetchone()[0]
            cur.execute("SELECT session_id, rating, comment, created_at FROM feedback ORDER BY created_at DESC LIMIT 20")
            recent = cur.fetchall()
        return {
            "total": total,
            "likes": likes,
            "dislikes": dislikes,
            "recent": [{"session_id": r[0], "rating": r[1], "comment": r[2], "created_at": r[3]} for r in recent],
        }
    finally:
        conn.close()


# ── 偏好提取规则 ──

def extract_demographics(text: str) -> dict:
    result = {}
    for kw in ["我是男生", "我是男的", "男用户", "先生", "帅哥"]:
        if kw in text: result["gender"] = "男"; break
    for kw in ["我是女生", "我是女的", "女用户", "女士", "美女", "小姐"]:
        if kw in text: result["gender"] = "女"; break
    import re
    m = re.search(r"(\d{1,3})\s*岁", text)
    if m:
        age = int(m.group(1))
        if 0 < age < 150: result["age"] = age
    return result


PREFERENCE_RULES = [
    (["大户型", "大面积", "大平层", "别墅", "复式"], "house_type", "大户型"),
    (["小户型", "小面积", "公寓", "单间"], "house_type", "小户型"),
    (["有猫", "养猫", "猫咪", "有狗", "养狗", "宠物", "掉毛"], "has_pets", True),
    (["扫拖一体", "扫拖", "拖地"], "robot_type", "扫拖一体"),
    (["扫地机器人", "扫地机", "只扫地"], "robot_type", "扫地机器人"),
    (["自动集尘", "集尘袋", "集尘"], "need_auto_dust", True),
    (["自动洗拖布", "洗拖布", "自清洁"], "need_self_clean", True),
    (["小孩", "宝宝", "婴儿", "儿童"], "has_children", True),
    (["老人", "长辈", "爸妈"], "has_elderly", True),
    (["安静", "噪音", "低噪", "不吵"], "care_noise", True),
]


def extract_preferences(text: str) -> dict:
    prefs = {}
    if not text: return prefs
    for keywords, field, value in PREFERENCE_RULES:
        for kw in keywords:
            if kw in text: prefs[field] = value; break
    return prefs


def get_profile(user_id: str) -> dict | None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT city, gender, age, preferences, updated_at FROM profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
        if not row: return None
        try: prefs = json.loads(row[3])
        except (json.JSONDecodeError, TypeError): prefs = {}
        return {"user_id": user_id, "city": row[0], "gender": row[1], "age": row[2], "preferences": prefs, "updated_at": row[4]}
    finally:
        conn.close()


# ── 系统配置 ──

DEFAULT_GREETINGS = {
    "chat": "你好，我是扫地机器人智能客服。你可以直接问我产品功能、使用问题或清洁建议。",
    "chat_only": "嗨～我是小扫，你的扫地机器人聊天伙伴！我们可以随便聊聊，有什么想说的吗？😊",
    "search": "输入关键词搜索知识库，例如'滤网更换'、'WIFI设置'，我会返回匹配的参考资料。",
}
DEFAULT_TITLES = {"chat": "扫地机器人智能客服", "chat_only": "小扫 · 聊聊天", "search": "知识库检索"}
DEFAULT_SUBTITLES = {"chat": "智能问答 · RAG + 工具", "chat_only": "纯聊天模式 · 轻松对话", "search": "知识库检索 · 直接搜索"}
DEFAULT_PLACEHOLDERS = {"chat": "请输入你的问题，例如：如何设置扫地机器人定时清扫？", "chat_only": "随意聊聊吧，例如：今天过得怎么样？", "search": "输入关键词搜索知识库，例如：滤网更换、WIFI设置"}

_config_loaded = False


def _init_config():
    global _config_loaded
    if _config_loaded: return
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    scope VARCHAR(32) NOT NULL,
                    mode VARCHAR(32) NOT NULL,
                    content TEXT NOT NULL,
                    PRIMARY KEY (scope, mode)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            for scope, mapping in [("greeting", DEFAULT_GREETINGS), ("title", DEFAULT_TITLES),
                                    ("subtitle", DEFAULT_SUBTITLES), ("placeholder", DEFAULT_PLACEHOLDERS)]:
                for mode, text in mapping.items():
                    cur.execute(
                        "INSERT IGNORE INTO system_config (scope, mode, content) VALUES (%s, %s, %s)",
                        (scope, mode, text),
                    )
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()
    _config_loaded = True


def get_all_config() -> dict[str, dict[str, str]]:
    _init_config()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT scope, mode, content FROM system_config")
            rows = cur.fetchall()
        result = {}
        for row in rows: result.setdefault(row[0], {})[row[1]] = row[2]
        return result
    finally:
        conn.close()


def set_config(scope: str, mode: str, content: str):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO system_config (scope, mode, content) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE content=VALUES(content)",
                (scope, mode, content),
            )
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


# ── 自定义 Mode ──

def _init_modes():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS custom_modes (
                    id VARCHAR(32) PRIMARY KEY,
                    title VARCHAR(128) NOT NULL,
                    greeting TEXT,
                    subtitle TEXT,
                    placeholder TEXT,
                    prompt_path TEXT,
                    data_dir TEXT,
                    enabled TINYINT DEFAULT 1,
                    created_at DOUBLE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


def get_all_modes() -> list[dict]:
    _init_modes()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, greeting, subtitle, placeholder, prompt_path, data_dir, enabled FROM custom_modes ORDER BY created_at")
            rows = cur.fetchall()
        result = []
        for r in rows:
            data_dir = r[6]
            data_files = []
            if data_dir and os.path.isdir(data_dir):
                data_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
            prompt_path = r[5]
            prompt_name = os.path.basename(prompt_path) if prompt_path else ""
            result.append({
                "id": r[0], "title": r[1], "greeting": r[2], "subtitle": r[3],
                "placeholder": r[4], "prompt_path": prompt_path, "prompt_name": prompt_name,
                "enabled": bool(r[7]) if len(r) > 7 else True,
                "data_dir": data_dir, "data_files": data_files,
            })
        return result
    finally:
        conn.close()


def get_mode(mode_id: str) -> dict | None:
    _init_modes()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, greeting, subtitle, placeholder, prompt_path, data_dir FROM custom_modes WHERE id = %s", (mode_id,))
            row = cur.fetchone()
        if not row: return None
        return {"id": row[0], "title": row[1], "greeting": row[2], "subtitle": row[3],
                "placeholder": row[4], "prompt_path": row[5], "data_dir": row[6]}
    finally:
        conn.close()


def create_mode(mode_id: str, title: str, greeting: str, subtitle: str, placeholder: str, prompt_path: str, data_dir: str):
    _init_modes()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO custom_modes (id, title, greeting, subtitle, placeholder, prompt_path, data_dir, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "title=VALUES(title), greeting=VALUES(greeting), subtitle=VALUES(subtitle), "
                "placeholder=VALUES(placeholder), prompt_path=VALUES(prompt_path), data_dir=VALUES(data_dir)",
                (mode_id, title, greeting, subtitle, placeholder, prompt_path, data_dir, time.time()),
            )
        conn.commit()
        loggers.info(f"DB write: {cur.rowcount} rows affected")
    finally:
        conn.close()


def delete_mode(mode_id: str) -> dict | None:
    _init_modes()
    if mode_id in ("chat", "chat_only", "search"): return None
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT prompt_path, data_dir FROM custom_modes WHERE id = %s", (mode_id,))
            row = cur.fetchone()
            if not row: return None
            info = {"prompt_path": row[0], "data_dir": row[1]}
            cur.execute("DELETE FROM custom_modes WHERE id = %s", (mode_id,))
        conn.commit()
        return info
    finally:
        conn.close()


def toggle_mode(mode_id: str) -> dict | None:
    _init_modes()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT enabled FROM custom_modes WHERE id = %s", (mode_id,))
            row = cur.fetchone()
            if not row: return None
            new_val = 0 if row[0] else 1
            cur.execute("UPDATE custom_modes SET enabled = %s WHERE id = %s", (new_val, mode_id))
        conn.commit()
        return {"id": mode_id, "enabled": bool(new_val)}
    finally:
        conn.close()


# ── LLM 画像提取 ──

EXTRACT_PROFILE_PROMPT = """从以下客服对话中提取用户信息，严格输出JSON，不要加任何解释文字：
---
{dialogue}
---
JSON格式：{{"gender":"男/女/未知","age":数字或0,"preferences":{{"house_type":"大户型/小户型","has_pets":true/false,"robot_type":"扫拖一体/扫地机器人","care_noise":true/false,"has_children":true/false,"has_elderly":true/false,"need_auto_dust":true/false,"need_self_clean":true/false}}}}
只输出JSON："""


def extract_profile_with_llm(dialogue: str) -> dict | None:
    try:
        from model.factor import get_chat_model
        model = get_chat_model()
        result = model.invoke(EXTRACT_PROFILE_PROMPT.format(dialogue=dialogue[:2000])).content
        text = result.strip()
        if text.startswith("```"): text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception:
        return None


# 模块导入时自动初始化
_init()
_init_feedback()
_init_config()
_init_modes()
loggers.info("MySQL 存储模块初始化完成，所有表已就绪")

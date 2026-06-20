"""会话持久化存储（SQLite）：对话历史 + 用户画像。"""

import sqlite3
import json
import threading
import time
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"
DB_PATH = DB_DIR / "store.db"

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init():
    with _lock:
        conn = _connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                mode TEXT DEFAULT 'chat'
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                city TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                age INTEGER DEFAULT 0,
                preferences TEXT DEFAULT '{}',
                updated_at REAL NOT NULL
            );
        """)
        # 兼容旧表结构
        for col, col_def in [("gender", "TEXT DEFAULT ''"), ("age", "INTEGER DEFAULT 0")]:
            try:
                conn.execute(f"ALTER TABLE profiles ADD COLUMN {col} {col_def}")
            except Exception:
                pass
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN mode TEXT DEFAULT 'chat'")
        except Exception:
            pass
        conn.commit()
        conn.close()


def save_message(session_id: str, role: str, content: str, mode: str = "chat"):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at, mode) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, time.time(), mode),
        )
        conn.commit()
        conn.close()


def get_session_history(session_id: str, limit: int = 50) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]


def list_sessions(limit: int = 20, mode: str = "") -> list[dict]:
    conn = _connect()
    if mode:
        rows = conn.execute("""
            SELECT
                m.session_id,
                COUNT(*) as msg_count,
                MAX(m.created_at) as last_active,
                (SELECT content FROM messages WHERE session_id = m.session_id AND role = 'user'
                 ORDER BY created_at ASC LIMIT 1) as preview
            FROM messages m
            WHERE m.session_id IN (SELECT DISTINCT session_id FROM messages WHERE mode = ?)
            GROUP BY m.session_id
            ORDER BY last_active DESC LIMIT ?
        """, (mode, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT
                m.session_id,
                COUNT(*) as msg_count,
                MAX(m.created_at) as last_active,
                (SELECT content FROM messages WHERE session_id = m.session_id AND role = 'user'
                 ORDER BY created_at ASC LIMIT 1) as preview
            FROM messages m
            GROUP BY m.session_id
            ORDER BY last_active DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [{"session_id": r[0], "msg_count": r[1], "last_active": r[2], "preview": r[3] or ""} for r in rows]


def delete_session(session_id: str):
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()


def save_profile(user_id: str, city: str = "", gender: str = "", age: int = 0, preferences: dict | None = None):
    with _lock:
        conn = _connect()
        prefs = json.dumps(preferences or {}, ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO profiles (user_id, city, gender, age, preferences, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, city, gender, age, prefs, time.time()),
        )
        conn.commit()
        conn.close()


def merge_profile(user_id: str, city: str = "", gender: str = "", age: int = 0, new_prefs: dict | None = None):
    """增量更新画像：合并偏好，不覆盖已有数据。"""
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
    with _lock:
        conn = _connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                rating TEXT NOT NULL,
                comment TEXT DEFAULT '',
                created_at REAL NOT NULL
            );
        """)
        conn.commit()
        conn.close()


def save_feedback(session_id: str, rating: str, comment: str = ""):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO feedback (session_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
            (session_id, rating, comment, time.time()),
        )
        conn.commit()
        conn.close()


def get_feedback_stats() -> dict:
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    likes = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'like'").fetchone()[0]
    dislikes = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'dislike'").fetchone()[0]
    recent = conn.execute(
        "SELECT session_id, rating, comment, created_at FROM feedback ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "likes": likes,
        "dislikes": dislikes,
        "recent": [
            {"session_id": r[0], "rating": r[1], "comment": r[2], "created_at": r[3]}
            for r in recent
        ],
    }


# ── 偏好提取规则 ──

# ── 性别和年龄提取 ──

def extract_demographics(text: str) -> dict:
    """从文本中提取性别和年龄。"""
    result = {}
    # 性别
    for kw in ["我是男生", "我是男的", "男用户", "先生", "帅哥"]:
        if kw in text:
            result["gender"] = "男"
            break
    for kw in ["我是女生", "我是女的", "女用户", "女士", "美女", "小姐"]:
        if kw in text:
            result["gender"] = "女"
            break
    # 年龄
    import re
    m = re.search(r"(\d{1,3})\s*岁", text)
    if m:
        age = int(m.group(1))
        if 0 < age < 150:
            result["age"] = age
    return result


PREFERENCE_RULES = [
    # (关键词列表, 偏好字段, 值)
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
    """从文本中提取用户偏好。"""
    prefs = {}
    if not text:
        return prefs
    for keywords, field, value in PREFERENCE_RULES:
        for kw in keywords:
            if kw in text:
                prefs[field] = value
                break
    return prefs


def get_profile(user_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT city, gender, age, preferences, updated_at FROM profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        prefs = json.loads(row[3])
    except (json.JSONDecodeError, TypeError):
        prefs = {}
    return {
        "user_id": user_id,
        "city": row[0],
        "gender": row[1],
        "age": row[2],
        "preferences": prefs,
        "updated_at": row[4],
    }


# ── 问候语 ──

DEFAULT_GREETINGS = {
    "chat": "你好，我是扫地机器人智能客服。你可以直接问我产品功能、使用问题或清洁建议。",
    "chat_only": "嗨～我是小扫，你的扫地机器人聊天伙伴！我们可以随便聊聊，有什么想说的吗？😊",
    "search": "输入关键词搜索知识库，例如'滤网更换'、'WIFI设置'，我会返回匹配的参考资料。",
}

DEFAULT_TITLES = {
    "chat": "扫地机器人智能客服",
    "chat_only": "小扫 · 聊聊天",
    "search": "知识库检索",
}

DEFAULT_SUBTITLES = {
    "chat": "智能问答 · RAG + 工具",
    "chat_only": "纯聊天模式 · 轻松对话",
    "search": "知识库检索 · 直接搜索",
}

DEFAULT_PLACEHOLDERS = {
    "chat": "请输入你的问题，例如：如何设置扫地机器人定时清扫？",
    "chat_only": "随意聊聊吧，例如：今天过得怎么样？",
    "search": "输入关键词搜索知识库，例如：滤网更换、WIFI设置",
}

_config_cache: dict[str, dict[str, str]] = {}
_config_loaded = False


def _init_config():
    global _config_loaded
    if _config_loaded:
        return
    with _lock:
        conn = _connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS system_config (
                scope TEXT NOT NULL,
                mode TEXT NOT NULL,
                content TEXT NOT NULL,
                PRIMARY KEY (scope, mode)
            );
        """)
        defaults = [
            ("greeting", DEFAULT_GREETINGS),
            ("title", DEFAULT_TITLES),
            ("subtitle", DEFAULT_SUBTITLES),
            ("placeholder", DEFAULT_PLACEHOLDERS),
        ]
        for scope, mapping in defaults:
            for mode, text in mapping.items():
                conn.execute(
                    "INSERT OR IGNORE INTO system_config (scope, mode, content) VALUES (?, ?, ?)",
                    (scope, mode, text),
                )
        conn.commit()
        conn.close()
    _config_loaded = True


def _load_config_scope(scope: str) -> dict[str, str]:
    _init_config()
    conn = _connect()
    rows = conn.execute("SELECT mode, content FROM system_config WHERE scope = ?", (scope,)).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def get_all_config() -> dict[str, dict[str, str]]:
    _init_config()
    conn = _connect()
    rows = conn.execute("SELECT scope, mode, content FROM system_config").fetchall()
    conn.close()
    result = {}
    for row in rows:
        result.setdefault(row[0], {})[row[1]] = row[2]
    return result


def set_config(scope: str, mode: str, content: str):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO system_config (scope, mode, content) VALUES (?, ?, ?)",
            (scope, mode, content),
        )
        conn.commit()
        conn.close()


# ── 自定义 Mode ──

def _init_modes():
    with _lock:
        conn = _connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS custom_modes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                greeting TEXT DEFAULT '',
                subtitle TEXT DEFAULT '',
                placeholder TEXT DEFAULT '',
                prompt_path TEXT DEFAULT '',
                data_dir TEXT DEFAULT '',
                created_at REAL NOT NULL
            );
        """)
        conn.commit()
        conn.close()


def get_all_modes() -> list[dict]:
    _init_modes()
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, greeting, subtitle, placeholder, prompt_path, data_dir FROM custom_modes ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "greeting": r[2], "subtitle": r[3],
         "placeholder": r[4], "prompt_path": r[5], "data_dir": r[6]}
        for r in rows
    ]


def get_mode(mode_id: str) -> dict | None:
    _init_modes()
    conn = _connect()
    row = conn.execute(
        "SELECT id, title, greeting, subtitle, placeholder, prompt_path, data_dir FROM custom_modes WHERE id = ?",
        (mode_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "greeting": row[2], "subtitle": row[3],
            "placeholder": row[4], "prompt_path": row[5], "data_dir": row[6]}


def create_mode(mode_id: str, title: str, greeting: str, subtitle: str, placeholder: str, prompt_path: str, data_dir: str):
    _init_modes()
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO custom_modes (id, title, greeting, subtitle, placeholder, prompt_path, data_dir, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (mode_id, title, greeting, subtitle, placeholder, prompt_path, data_dir, time.time()),
        )
        conn.commit()
        conn.close()


def delete_mode(mode_id: str) -> bool:
    _init_modes()
    # 不能删除内置模式
    if mode_id in ("chat", "chat_only", "search"):
        return False
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM custom_modes WHERE id = ?", (mode_id,))
        deleted = conn.total_changes > 0
        conn.commit()
        conn.close()
        return deleted


# ── LLM 画像提取 ──

EXTRACT_PROFILE_PROMPT = """从以下客服对话中提取用户信息，严格输出JSON，不要加任何解释文字：
---
{dialogue}
---
JSON格式：{{"gender":"男/女/未知","age":数字或0,"preferences":{{"house_type":"大户型/小户型","has_pets":true/false,"robot_type":"扫拖一体/扫地机器人","care_noise":true/false,"has_children":true/false,"has_elderly":true/false,"need_auto_dust":true/false,"need_self_clean":true/false}}}}
只输出JSON："""


def extract_profile_with_llm(dialogue: str) -> dict | None:
    """用 LLM 从对话中提取用户画像，失败返回 None。"""
    try:
        from model.factor import get_chat_model
        model = get_chat_model()
        result = model.invoke(EXTRACT_PROFILE_PROMPT.format(dialogue=dialogue[:2000])).content
        # 清理 LLM 输出：去掉 markdown 代码块包裹
        text = result.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        profile = json.loads(text)
        return profile
    except Exception:
        return None


# 模块导入时自动初始化
_init()
_init_feedback()

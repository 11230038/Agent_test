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
                created_at REAL NOT NULL
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
        conn.commit()
        conn.close()


def save_message(session_id: str, role: str, content: str):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time()),
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


def list_sessions(limit: int = 20) -> list[dict]:
    conn = _connect()
    rows = conn.execute("""
        SELECT session_id, COUNT(*) as msg_count, MAX(created_at) as last_active
        FROM messages GROUP BY session_id ORDER BY last_active DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"session_id": r[0], "msg_count": r[1], "last_active": r[2]} for r in rows]


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

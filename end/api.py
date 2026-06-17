import os
import time
import uuid

import jwt
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from agent.react_agent import ReactAgent, AgentInitializationError, AgentExecutionError
from agent.tools.agent_tools import get_last_rag_sources
from rag.rag_service import get_rag_service
from utils import session_store
from utils.logger_handler import loggers

app = FastAPI(title="Robot Agent API")
_agent: ReactAgent | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None
    session_id: str | None = None
    user_context: dict | None = None
    mode: str = "chat"


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: dict | None = None


def success_response(message: str, data: dict | None = None) -> ApiResponse:
    return ApiResponse(success=True, message=message, data=data)


def error_response(message: str, data: dict | None = None) -> ApiResponse:
    return ApiResponse(success=False, message=message, data=data)


def get_agent() -> ReactAgent:
    global _agent
    if _agent is None:
        _agent = ReactAgent()
    return _agent


def _make_trace_id() -> str:
    return uuid.uuid4().hex[:12]


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "请求失败，请稍后重试。"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(detail).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_response("请求参数校验失败", {"errors": exc.errors()}).model_dump(),
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    loggers.error(f"未处理异常:{exc}")
    return JSONResponse(
        status_code=500,
        content=error_response("服务器内部错误，请稍后重试。").model_dump(),
    )


@app.get("/health", response_model=ApiResponse)
def health_check():
    return success_response("ok", {"status": "ok"})


@app.get("/ready", response_model=ApiResponse)
def ready_check():
    checks = {}

    # 检查 LLM
    try:
        from model.factor import get_chat_model
        get_chat_model()
        checks["llm"] = {"ok": True}
    except Exception as e:
        checks["llm"] = {"ok": False, "error": str(e)}

    # 检查 Embedding
    try:
        from model.factor import get_embed_model
        get_embed_model()
        checks["embedding"] = {"ok": True}
    except Exception as e:
        checks["embedding"] = {"ok": False, "error": str(e)}

    # 检查 Chroma
    try:
        from rag.rag_service import get_rag_service
        status = get_rag_service().get_status()
        checks["chroma"] = {
            "ok": status["knowledge_base"]["chunk_count"] >= 0,
            "chunk_count": status["knowledge_base"]["chunk_count"],
        }
    except Exception as e:
        checks["chroma"] = {"ok": False, "error": str(e)}

    failed = [name for name, v in checks.items() if not v.get("ok", False)]
    all_ok = len(failed) == 0
    msg = "ok" if all_ok else f"degraded: {', '.join(failed)} 不可用"
    return success_response(msg, {"checks": checks})


@app.post("/api/chat", response_model=ApiResponse)
def chat(payload: ChatRequest):
    trace_id = _make_trace_id()
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    loggers.info(f"[{trace_id}] 收到聊天请求 session={payload.session_id} history_len={len(payload.history or [])}")

    try:
        answer = get_agent().execute(message, history=payload.history, trace_id=trace_id, user_context=payload.user_context, mode=payload.mode)
    except AgentInitializationError as e:
        loggers.error(f"[{trace_id}] 模型初始化失败: {e}")
        raise HTTPException(status_code=503, detail="服务配置异常，请联系管理员") from e
    except AgentExecutionError as e:
        loggers.error(f"[{trace_id}] 模型执行失败: {e}")
        raise HTTPException(status_code=502, detail="模型服务暂不可用，请稍后重试") from e
    except ValueError as e:
        loggers.error(f"[{trace_id}] 配置错误: {e}")
        raise HTTPException(status_code=503, detail="服务配置异常，请联系管理员") from e
    except Exception as e:
        loggers.error(f"[{trace_id}] 未知错误: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试") from e

    sources = get_last_rag_sources()
    loggers.info(f"[{trace_id}] 聊天请求完成 answer_len={len(answer)} sources={len(sources)}")

    # 持久化对话 + 自动更新用户画像
    try:
        sid = payload.session_id or "default"
        session_store.save_message(sid, "user", message)
        session_store.save_message(sid, "assistant", answer)

        # 自动画像：LLM 提取 + 关键词规则兜底
        uctx = payload.user_context or {}
        uid = uctx.get("user_id", "")
        if uid and uid != "未知用户":
            city = uctx.get("city", "")
            dialogue = message + " " + answer
            # 优先 LLM 提取
            profile = session_store.extract_profile_with_llm(dialogue)
            if profile:
                prefs = profile.get("preferences", {}) or {}
                session_store.merge_profile(
                    uid, city,
                    profile.get("gender", ""),
                    profile.get("age", 0),
                    prefs,
                )
            else:
                # LLM 失败时回退到关键词规则
                demos = session_store.extract_demographics(dialogue)
                prefs = session_store.extract_preferences(dialogue)
                session_store.merge_profile(uid, city, demos.get("gender", ""), demos.get("age", 0), prefs)
    except Exception:
        pass  # 持久化失败不影响主流程

    return success_response("请求成功", {"answer": answer, "trace_id": trace_id, "sources": sources})


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    trace_id = _make_trace_id()
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    loggers.info(f"[{trace_id}] 收到流式聊天请求 session={req.session_id} history_len={len(req.history or [])}")

    def generate():
        import queue
        import threading

        q: queue.Queue = queue.Queue()

        def run():
            try:
                for chunk in get_agent().execute_stream(message, history=req.history, trace_id=trace_id, user_context=req.user_context, mode=req.mode):
                    q.put(("data", chunk))
                q.put(("done", None))
            except AgentInitializationError as e:
                loggers.error(f"[{trace_id}] 模型初始化失败: {e}")
                q.put(("error", "服务配置异常，请联系管理员"))
            except AgentExecutionError as e:
                loggers.error(f"[{trace_id}] 模型执行失败: {e}")
                q.put(("error", "模型服务暂不可用，请稍后重试"))
            except Exception as e:
                loggers.error(f"[{trace_id}] 流式聊天执行失败: {e}")
                q.put(("error", "服务器内部错误，请稍后重试"))

        t = threading.Thread(target=run, daemon=True)
        t.start()

        while True:
            try:
                msg_type, data = q.get(timeout=4)
                if msg_type == "done":
                    break
                if msg_type == "error":
                    yield f"data: [ERROR] {data}\n\n"
                    break
                for line in data.split("\n"):
                    yield f"data: {line}\n"
                yield "\n"
                loggers.info(f"[{trace_id}] SSE → {repr(data[:80])}")
            except queue.Empty:
                yield "data: \n\n"

        loggers.info(f"[{trace_id}] 流式聊天请求完成")

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/rag/status", response_model=ApiResponse)
def rag_status():
    try:
        rag = get_rag_service()
        status = rag.get_status()
    except Exception as e:
        return success_response("ok", {
            "available": False,
            "error": str(e),
        })
    return success_response("ok", status)


class SearchRequest(BaseModel):
    query: str
    style: str = "full"


@app.post("/api/rag/search", response_model=ApiResponse)
def rag_search(payload: SearchRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    try:
        rag = get_rag_service()
        results = rag.search(query)
    except Exception as e:
        loggers.error(f"知识库检索失败: {e}")
        raise HTTPException(status_code=503, detail="知识库服务暂不可用，请稍后重试") from e

    return success_response("ok", {
        "query": query,
        "total": len(results),
        "results": results,
    })


# ── 管理端接口 ──

ADMIN_PASSWORD = "796581"
JWT_SECRET = "robot-agent-admin-secret-key-2026"
JWT_EXPIRE_SECONDS = 86400  # 24 小时

_data_path: str | None = None


def _get_data_dir() -> str:
    """获取知识库 data 目录的绝对路径。"""
    global _data_path
    if _data_path is None:
        from utils.config_handler import chroma_conf
        from utils.path_tool import get_abs_path
        _data_path = get_abs_path(chroma_conf.get("data_path", "data"))
    return _data_path


def _check_token(token: str):
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="令牌已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="令牌无效，请重新登录")


def _allowed_ext(filename: str) -> bool:
    from utils.config_handler import chroma_conf
    ext = os.path.splitext(filename)[1].lower()
    return ext in chroma_conf.get("allow_knowledge_file_type", [".pdf", ".txt"])


# ── 登录 ──

class AdminLoginRequest(BaseModel):
    password: str


@app.post("/api/admin/login", response_model=ApiResponse)
def admin_login(payload: AdminLoginRequest):
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")
    token = jwt.encode(
        {"exp": time.time() + JWT_EXPIRE_SECONDS},
        JWT_SECRET,
        algorithm="HS256",
    )
    loggers.info("管理端登录成功")
    return success_response("登录成功", {"token": token})


# ── 知识库管理 ──

class AdminTokenRequest(BaseModel):
    token: str


@app.post("/api/admin/knowledge", response_model=ApiResponse)
def admin_knowledge(payload: AdminTokenRequest):
    _check_token(payload.token)
    try:
        rag = get_rag_service()
        structure = rag.vector_store.get_detailed_structure()
    except Exception as e:
        loggers.error(f"获取知识库结构失败: {e}")
        raise HTTPException(status_code=503, detail="知识库服务暂不可用") from e
    return success_response("ok", structure)


@app.post("/api/admin/upload")
async def admin_upload(
    token: str = Form(...),
    category: str = Form(default="扫地机器人客服"),
    file: UploadFile = File(...),
):
    _check_token(token)

    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")
    if not _allowed_ext(file.filename):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅支持 PDF、TXT")

    data_dir = _get_data_dir()
    # 按分类存储到子目录
    cat_dir = os.path.join(data_dir, category) if category != "扫地机器人客服" else data_dir
    os.makedirs(cat_dir, exist_ok=True)

    save_path = os.path.join(cat_dir, file.filename)
    # 避免覆盖：同名文件加序号
    base, ext = os.path.splitext(file.filename)
    counter = 1
    while os.path.exists(save_path):
        save_path = os.path.join(cat_dir, f"{base}_{counter}{ext}")
        counter += 1

    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
    except Exception as e:
        loggers.error(f"保存文件失败: {e}")
        raise HTTPException(status_code=500, detail="文件保存失败") from e

    # 索引到向量库
    try:
        rag = get_rag_service()
        abs_path = os.path.abspath(save_path)
        rag.vector_store._load_single_file(abs_path, category)
    except Exception as e:
        loggers.error(f"索引文件失败: {e}")
        raise HTTPException(status_code=500, detail="文件已保存但索引失败") from e

    loggers.info(f"管理端上传文件成功: {save_path} 分类: {category}")
    return success_response("上传成功", {
        "filename": os.path.basename(save_path),
        "category": category,
        "path": os.path.abspath(save_path),
    })


class AdminDeleteRequest(BaseModel):
    token: str
    source: str  # 文件完整路径


@app.post("/api/admin/delete", response_model=ApiResponse)
def admin_delete(payload: AdminDeleteRequest):
    _check_token(payload.token)

    source = payload.source.strip()
    if not source or not os.path.exists(source):
        raise HTTPException(status_code=400, detail="文件不存在")

    filename = os.path.basename(source)

    # 从向量库删除
    try:
        rag = get_rag_service()
        rag.vector_store.delete_by_source(source)
    except Exception as e:
        loggers.error(f"删除向量失败: {e}")
        raise HTTPException(status_code=500, detail="向量删除失败") from e

    # 从磁盘删除
    try:
        os.remove(source)
    except Exception as e:
        loggers.error(f"删除文件失败: {e}")
        # 向量已删，文件删不掉的情况也要报
        raise HTTPException(status_code=500, detail="向量已删除，但文件删除失败") from e

    loggers.info(f"管理端删除文档成功: {source}")
    return success_response("删除成功", {"filename": filename, "source": source})


class AdminCategoryRequest(BaseModel):
    token: str
    source: str
    category: str


@app.post("/api/admin/category", response_model=ApiResponse)
def admin_change_category(payload: AdminCategoryRequest):
    _check_token(payload.token)

    source = payload.source.strip()
    new_category = payload.category.strip()
    if not source or not os.path.exists(source):
        raise HTTPException(status_code=400, detail="源文件不存在")
    if not new_category:
        raise HTTPException(status_code=400, detail="分类不能为空")

    try:
        rag = get_rag_service()
        abs_path = os.path.abspath(source)
        rag.vector_store.delete_by_source(abs_path)
        rag.vector_store._load_single_file(abs_path, new_category)
    except Exception as e:
        loggers.error(f"更改分类失败: {e}")
        raise HTTPException(status_code=500, detail="分类更改失败") from e

    loggers.info(f"管理端更改分类成功: {source} → {new_category}")
    return success_response("分类已更新", {
        "filename": os.path.basename(source),
        "category": new_category,
    })


class AdminChunkUpdateRequest(BaseModel):
    token: str
    chunk_id: str
    content: str


@app.post("/api/admin/chunk/update", response_model=ApiResponse)
def admin_chunk_update(payload: AdminChunkUpdateRequest):
    _check_token(payload.token)

    chunk_id = payload.chunk_id.strip()
    content = payload.content.strip()
    if not chunk_id:
        raise HTTPException(status_code=400, detail="chunk_id 不能为空")
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")

    try:
        rag = get_rag_service()
        ok = rag.vector_store.update_chunk(chunk_id, content)
    except Exception as e:
        loggers.error(f"更新 chunk 失败: {e}")
        raise HTTPException(status_code=500, detail="更新失败") from e

    if not ok:
        raise HTTPException(status_code=404, detail="chunk 不存在")

    loggers.info(f"管理端更新 chunk 成功: {chunk_id}")
    return success_response("chunk 已更新", {"chunk_id": chunk_id, "char_count": len(content)})


# ── 提示词管理接口 ──

def _get_prompt_config() -> dict[str, str]:
    """返回 {显示名: 文件路径}。"""
    from utils.config_handler import prompts_conf
    from utils.path_tool import get_abs_path
    mapping = {
        "主 Agent 提示词": "main_prompt_path",
        "RAG 总结提示词": "rag_summarize_prompt_path",
        "报告生成提示词": "report_prompt_path",
        "纯聊天提示词": "chat_prompt_path",
    }
    result = {}
    for label, key in mapping.items():
        rel = prompts_conf.get(key, "")
        if rel:
            result[label] = get_abs_path(rel)
    return result


@app.post("/api/admin/prompts", response_model=ApiResponse)
def admin_prompts_list(payload: AdminTokenRequest):
    """列出所有提示词文件。"""
    _check_token(payload.token)
    prompts = []
    for label, path in _get_prompt_config().items():
        exists = os.path.isfile(path)
        size = os.path.getsize(path) if exists else 0
        prompts.append({
            "name": label,
            "path": path,
            "filename": os.path.basename(path),
            "exists": exists,
            "size": size,
        })
    return success_response("ok", {"prompts": prompts})


class AdminPromptReadRequest(BaseModel):
    token: str
    path: str


@app.post("/api/admin/prompt/read", response_model=ApiResponse)
def admin_prompt_read(payload: AdminPromptReadRequest):
    """读取指定提示词文件内容。"""
    _check_token(payload.token)
    path = payload.path.strip()
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=400, detail="文件不存在")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        loggers.error(f"读取提示词失败: {e}")
        raise HTTPException(status_code=500, detail="读取失败") from e
    return success_response("ok", {
        "path": path,
        "filename": os.path.basename(path),
        "content": content,
        "char_count": len(content),
    })


class AdminPromptWriteRequest(BaseModel):
    token: str
    path: str
    content: str


@app.post("/api/admin/prompt/write", response_model=ApiResponse)
def admin_prompt_write(payload: AdminPromptWriteRequest):
    """覆写提示词文件。"""
    _check_token(payload.token)
    path = payload.path.strip()
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=400, detail="文件不存在")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload.content)
    except Exception as e:
        loggers.error(f"写入提示词失败: {e}")
        raise HTTPException(status_code=500, detail="写入失败") from e
    loggers.info(f"管理端更新提示词成功: {os.path.basename(path)}")
    return success_response("提示词已保存", {"filename": os.path.basename(path), "char_count": len(payload.content)})


# ── 会话 & 画像接口 ──

@app.get("/api/sessions", response_model=ApiResponse)
def list_sessions():
    sessions = session_store.list_sessions()
    return success_response("ok", {"sessions": sessions})


@app.get("/api/session/{session_id}", response_model=ApiResponse)
def get_session(session_id: str):
    history = session_store.get_session_history(session_id)
    return success_response("ok", {"session_id": session_id, "history": history})


@app.delete("/api/session/{session_id}", response_model=ApiResponse)
def delete_session(session_id: str):
    session_store.delete_session(session_id)
    return success_response("已删除", {"session_id": session_id})


class ProfileRequest(BaseModel):
    user_id: str
    city: str = ""
    gender: str = ""
    age: int = 0
    preferences: dict | None = None


@app.post("/api/profile", response_model=ApiResponse)
def save_profile(payload: ProfileRequest):
    if payload.user_id == "未知用户":
        raise HTTPException(status_code=400, detail="未知用户无法保存画像，请先设置用户ID")
    session_store.save_profile(payload.user_id, payload.city, payload.gender, payload.age, payload.preferences)
    return success_response("已保存", {"user_id": payload.user_id})


@app.get("/api/profile/{user_id}", response_model=ApiResponse)
def get_profile(user_id: str):
    profile = session_store.get_profile(user_id)
    if not profile:
        return success_response("ok", {"profile": None})
    return success_response("ok", {"profile": profile})


# ── 反馈接口 ──

class FeedbackRequest(BaseModel):
    session_id: str
    rating: str  # "like" | "dislike"
    comment: str = ""


@app.post("/api/feedback", response_model=ApiResponse)
def submit_feedback(payload: FeedbackRequest):
    if payload.rating not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="rating 必须为 like 或 dislike")
    session_store.save_feedback(payload.session_id, payload.rating, payload.comment)
    return success_response("反馈已提交")


@app.get("/api/feedback/stats", response_model=ApiResponse)
def feedback_stats():
    stats = session_store.get_feedback_stats()
    return success_response("ok", stats)

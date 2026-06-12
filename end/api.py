import uuid
from fastapi import FastAPI, HTTPException, Request
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

        # 自动画像：从 user_context 拿基础信息，从对话提取偏好和人口统计
        uctx = payload.user_context or {}
        uid = uctx.get("user_id", "")
        if uid and uid != "未知用户":
            city = uctx.get("city", "")
            demos = session_store.extract_demographics(message + " " + answer)
            prefs = session_store.extract_preferences(message + " " + answer)
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
                sse = f"data: {data}\n\n"
                loggers.info(f"[{trace_id}] SSE → {repr(data[:80])}")
                yield sse
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

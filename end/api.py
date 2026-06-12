import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from agent.react_agent import ReactAgent, AgentInitializationError, AgentExecutionError
from agent.tools.agent_tools import get_last_rag_sources
from rag.rag_service import get_rag_service
from utils.logger_handler import loggers

app = FastAPI(title="Robot Agent API")
_agent: ReactAgent | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None
    session_id: str | None = None
    user_context: dict | None = None


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


@app.post("/api/chat", response_model=ApiResponse)
def chat(payload: ChatRequest):
    trace_id = _make_trace_id()
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    loggers.info(f"[{trace_id}] 收到聊天请求 session={payload.session_id} history_len={len(payload.history or [])}")

    try:
        answer = get_agent().execute(message, history=payload.history, trace_id=trace_id, user_context=payload.user_context)
    except AgentInitializationError as e:
        loggers.error(f"[{trace_id}] {e}")
        raise HTTPException(status_code=503, detail=str(e)) from e
    except AgentExecutionError as e:
        loggers.error(f"[{trace_id}] {e}")
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        loggers.error(f"[{trace_id}] 聊天服务配置错误:{e}")
        raise HTTPException(status_code=503, detail=f"聊天服务配置错误:{e}") from e
    except Exception as e:
        loggers.error(f"[{trace_id}] 聊天服务执行失败:{e}")
        raise HTTPException(status_code=500, detail=f"聊天服务执行失败:{e}") from e

    sources = get_last_rag_sources()
    loggers.info(f"[{trace_id}] 聊天请求完成 answer_len={len(answer)} sources={len(sources)}")
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
                for chunk in get_agent().execute_stream(message, history=req.history, trace_id=trace_id, user_context=req.user_context):
                    q.put(("data", chunk))
                q.put(("done", None))
            except AgentInitializationError as e:
                loggers.error(f"[{trace_id}] {e}")
                q.put(("error", str(e)))
            except AgentExecutionError as e:
                loggers.error(f"[{trace_id}] {e}")
                q.put(("error", str(e)))
            except Exception as e:
                loggers.error(f"[{trace_id}] 流式聊天执行失败:{e}")
                q.put(("error", str(e)))

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
        raise HTTPException(status_code=503, detail=f"检索失败:{e}") from e

    return success_response("ok", {
        "query": query,
        "total": len(results),
        "results": results,
    })

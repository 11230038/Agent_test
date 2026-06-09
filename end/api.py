from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.react_agent import ReactAgent

app = FastAPI(title="Robot Agent API")
agent = ReactAgent()


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    answer = agent.execute(message)
    return {"answer": answer}

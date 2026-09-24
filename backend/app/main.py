from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agent.graph import run_agent

app = FastAPI(title="ShopAgent-OS API")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        reply = run_agent(request.message)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Something went wrong processing your message.",
        )
    return ChatResponse(reply=reply)

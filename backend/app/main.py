from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent.graph import run_agent
from app.auth import verify_api_key

app = FastAPI(title="ShopAgent-OS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
def chat(request: ChatRequest) -> ChatResponse:
    try:
        reply = run_agent(request.message, session_id=request.session_id)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Something went wrong processing your message.",
        )
    return ChatResponse(reply=reply)

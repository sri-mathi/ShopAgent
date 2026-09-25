from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent.graph import run_agent
from app.auth import verify_api_key
from app.guardrails import is_prompt_injection
from app.rate_limit import check_rate_limit

SAFE_REFUSAL_MESSAGE = (
    "I'm not able to help with that. Is there something else I can help with "
    "regarding your order, our products, or store policies?"
)

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
    customer_email: str | None = None


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, api_key: str = Depends(verify_api_key)) -> ChatResponse:
    if not check_rate_limit(api_key):
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

    if is_prompt_injection(request.message):
        return ChatResponse(reply=SAFE_REFUSAL_MESSAGE)

    try:
        reply = run_agent(
            request.message,
            session_id=request.session_id,
            customer_email=request.customer_email,
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Something went wrong processing your message.",
        )
    return ChatResponse(reply=reply)

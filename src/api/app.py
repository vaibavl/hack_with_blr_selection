import json
import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import auth, db
from ..agent.comparison import MemoryBenchmarkComparator
from ..agent.orchestrator import support_agent
from ..banking.core_banking_service import core_banking
from ..hindsight.client_wrapper import hindsight_service

app = FastAPI(
    title="BharatApex AI - FinTech Support Agent API",
    description="Login-protected conversational banking agent with Hindsight memory",
    version="2.0.0",
)

db.init_db()


# ----------------------------------------------------------------- models
class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(max_length=4000)


class BenchmarkRequest(BaseModel):
    message: str = Field(max_length=4000)


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)


Session = Depends(auth.current_session)


def _title_from(message: str) -> str:
    t = " ".join(message.split())
    return (t[:42] + "…") if len(t) > 43 else (t or "New chat")


def _format_message(m: dict) -> dict:
    meta = json.loads(m["meta"]) if m.get("meta") else {}
    return {"id": m["id"], "role": m["role"], "content": m["content"],
            "created_at": m["created_at"], **meta}


# ------------------------------------------------------------------- auth
@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    customer_id = auth.authenticate(req.username, req.password)
    if not customer_id:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = auth.create_session(customer_id, req.username)
    response.set_cookie(
        auth.COOKIE_NAME, token,
        max_age=auth.session_ttl_hours() * 3600,
        httponly=True, samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "0") == "1",
    )
    summary = core_banking.get_account_summary(customer_id)
    return {"customer_id": customer_id, "name": summary["name"], "tier": summary["tier"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.end_session(request.cookies.get(auth.COOKIE_NAME))
    response.delete_cookie(auth.COOKIE_NAME)
    return {"status": "signed_out"}


@app.get("/api/auth/me")
def me(session: dict = Session):
    summary = core_banking.get_account_summary(session["customer_id"])
    return {"customer_id": session["customer_id"], "username": session["username"],
            "name": summary["name"], "tier": summary["tier"]}


# -------------------------------------------------------------- overview
@app.get("/api/overview")
def overview(session: dict = Session):
    cid = session["customer_id"]
    return {
        "profile": core_banking.get_account_summary(cid),
        "transactions": core_banking.get_transactions(cid, limit=10),
    }


# ---------------------------------------------------------- conversations
@app.get("/api/conversations")
def list_conversations(session: dict = Session):
    return db.list_conversations(session["customer_id"])


@app.post("/api/conversations")
def new_conversation(session: dict = Session):
    return db.create_conversation(session["customer_id"])


@app.patch("/api/conversations/{conv_id}")
def rename_conversation(conv_id: str, req: RenameRequest, session: dict = Session):
    if not db.rename_conversation(session["customer_id"], conv_id, req.title.strip()):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "renamed"}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str, session: dict = Session):
    if not db.delete_conversation(session["customer_id"], conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@app.get("/api/conversations/{conv_id}/messages")
def conversation_messages(conv_id: str, session: dict = Session):
    if not db.get_conversation(session["customer_id"], conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [_format_message(m) for m in db.get_messages(conv_id)]


# ------------------------------------------------------------------- chat
@app.post("/api/chat")
def chat(req: ChatRequest, session: dict = Session):
    cid = session["customer_id"]
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    conv = db.get_conversation(cid, req.conversation_id) if req.conversation_id else None
    if req.conversation_id and not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not conv:
        conv = db.create_conversation(cid, _title_from(message))

    prior = db.get_messages(conv["id"], limit=20)
    history = [{"role": m["role"], "content": m["content"]} for m in prior]

    if not prior and conv["title"] == "New chat":
        db.rename_conversation(cid, conv["id"], _title_from(message))

    result = support_agent.process_message(
        customer_id=cid, message=message, use_memory=True, history=history)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    meta = {
        "actions": result.get("actions", []),
        "latency_ms": result.get("latency_ms"),
        "escalation": result.get("escalation"),
    }
    db.add_message(conv["id"], "user", message)
    db.add_message(conv["id"], "assistant", result["reply"], json.dumps(meta, default=str))

    return {
        "conversation": db.get_conversation(cid, conv["id"]),
        "reply": result["reply"],
        **meta,
    }


@app.post("/api/benchmark")
def benchmark(req: BenchmarkRequest, session: dict = Session):
    return MemoryBenchmarkComparator.compare(customer_id=session["customer_id"], message=req.message)


# ----------------------------------------------------------------- public
@app.get("/api/health")
def health():
    return {"status": "online", "service": "BharatApex AI", "hindsight_mode": hindsight_service.mode,
            "llm": "groq" if support_agent.llm_router.agentic_available else "local"}


STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                            headers={"Cache-Control": "no-store"})

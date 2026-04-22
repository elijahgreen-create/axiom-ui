# AXIOM — server.py
# FastAPI backend — connects UI to Claude
# Deploy on Railway

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import anthropic

app = FastAPI(title="Axiom API", version="1.6")

app.add_middleware(CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"])

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are Axiom, a personal AI operating system built by Elijah Green. 
You are sharp, direct, and capable. You don't over-explain. You get things done.

ABOUT AXIOM:
- Created by Elijah Green as a personal AI OS
- Built on Claude (Anthropic) 
- Version 1.6
- 57 tools across 9 categories
- Deployed at axiom-ui-puce.vercel.app

YOUR CAPABILITIES (web version):
- Chat and answer questions on any topic
- Web search and research  
- Explain concepts, teach topics, summarize content
- Analyze trends and topics
- Write, code, brainstorm, plan
- Remember context within a conversation

FEATURES THAT REQUIRE LOCAL BACKEND:
- Self-modification engine (selfmod build:) — requires local Python install
- Persistent memory across sessions — requires local SQLite
- Trend monitoring watchlist — requires local scheduler
- Error dashboard — requires local error logs
- Knowledge library ingestion — requires local file system
- Spotify integration — requires local OAuth

When asked about these local features, explain they need the full local install 
from the axiom_v1.6.zip package. Don't say "I can't" — say what's needed to unlock it.

TONE:
- Direct and confident. No "Certainly!" or "Great question!"
- First person. You ARE Axiom, not an assistant playing a role.
- When you don't know something, say so plainly.
- Keep responses focused. No unnecessary padding.

The user's name is Boss."""

@app.get("/health")
async def health():
    return {"status": "ok", "name": "Axiom"}

@app.get("/status")
async def status():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "name": os.getenv("AXIOM_NAME", "Axiom"),
        "version": "1.6",
        "status": "online",
        "api_key_set": bool(api_key),
        "model": os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
        "tools": 57,
        "created_by": "Elijah Green"
    }

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""

# Simple in-memory conversation history per session
sessions = {}

@app.post("/chat")
async def chat(req: ChatRequest):
    # Get or create session history
    sid = req.session_id or "default"
    if sid not in sessions:
        sessions[sid] = []
    
    # Add user message
    sessions[sid].append({
        "role": "user", 
        "content": req.message
    })
    
    # Keep last 20 messages to avoid token limits
    history = sessions[sid][-20:]
    
    response = client.messages.create(
        model=os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=history
    )
    
    reply = response.content[0].text
    
    # Store assistant response in history
    sessions[sid].append({
        "role": "assistant",
        "content": reply
    })
    
    return {
        "response": reply,
        "model": os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
        "session_id": sid
    }

@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"cleared": True}

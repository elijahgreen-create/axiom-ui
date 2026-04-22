# AXIOM — server.py v1.8
# Streaming responses — no more timeouts

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import anthropic
import json

app = FastAPI(title="Axiom API", version="1.8")

app.add_middleware(CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"])

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are Axiom, a personal AI operating system built by Elijah Green.
You are sharp, direct, and capable. You don't over-explain. You get things done.

ABOUT YOU:
- You are Axiom. Created by Elijah Green.
- Built on Claude by Anthropic.
- Version 1.8. Live at axiom-ui-puce.vercel.app.

WHAT YOU CAN DO RIGHT NOW (web version):
- Answer any question
- Search the web in real time for current news, prices, facts, scores
- Research and summarize any topic
- Write, code, analyze, plan, brainstorm
- Remember the full conversation context

WHAT NEEDS THE LOCAL INSTALL (axiom_v1.6.zip):
- Self-modification engine
- Persistent memory across sessions
- Trend monitoring watchlist
- Error dashboard
- Knowledge library / URL ingestion
- Spotify control

For local features: tell the user to download axiom_v1.6.zip, 
add their API key to .env, and run python axiom.py locally.

TONE: Direct. No filler. First person — you ARE Axiom.
The user's name is Boss."""

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search"
}

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""

sessions = {}

@app.get("/health")
async def health():
    return {"status": "ok", "name": "Axiom", "version": "1.8"}

@app.get("/status")
async def status():
    return {
        "name": os.getenv("AXIOM_NAME", "Axiom"),
        "version": "1.8",
        "status": "online",
        "api_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "model": os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
        "web_search": True,
        "streaming": True,
        "created_by": "Elijah Green"
    }

@app.post("/chat")
async def chat(req: ChatRequest):
    sid = req.session_id or "default"
    if sid not in sessions:
        sessions[sid] = []

    sessions[sid].append({
        "role": "user",
        "content": req.message
    })

    history = sessions[sid][-20:]

    def stream_response():
        full_reply = ""
        try:
            with client.messages.stream(
                model=os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[WEB_SEARCH_TOOL],
                messages=history
            ) as stream:
                for text in stream.text_stream:
                    full_reply += text
                    # Send each chunk as SSE
                    chunk = json.dumps({"text": text, "done": False})
                    yield f"data: {chunk}\n\n"

        except Exception as e:
            # Fallback without web search tool
            try:
                with client.messages.stream(
                    model=os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=history
                ) as stream:
                    for text in stream.text_stream:
                        full_reply += text
                        chunk = json.dumps({"text": text, "done": False})
                        yield f"data: {chunk}\n\n"
            except Exception as e2:
                error_msg = f"Connection error: {str(e2)}"
                full_reply = error_msg
                yield f"data: {json.dumps({'text': error_msg, 'done': False})}\n\n"

        # Save to session history
        sessions[sid].append({
            "role": "assistant",
            "content": full_reply
        })

        # Send done signal
        yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"cleared": True}

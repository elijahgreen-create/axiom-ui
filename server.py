# AXIOM — server.py v1.7
# FastAPI backend with real web search via Claude

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import anthropic

app = FastAPI(title="Axiom API", version="1.7")

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
- Version 1.7
- Deployed at axiom-ui-puce.vercel.app

YOUR CAPABILITIES (web version):
- Chat and answer questions on any topic
- Real-time web search — you can search the internet right now
- Research any topic, find current news, look up prices, check facts
- Explain concepts, teach topics, summarize content
- Write, code, brainstorm, plan
- Remember context within a conversation

FEATURES THAT REQUIRE LOCAL BACKEND:
- Self-modification engine (selfmod build:) — requires local Python install
- Persistent memory across sessions — requires local SQLite
- Trend monitoring watchlist — requires local scheduler
- Error dashboard — requires local error logs
- Knowledge library ingestion — requires local file system
- Spotify integration — requires local OAuth

When asked about local features, explain what's needed to unlock them.
Don't say "I can't" — say what's needed.

TONE:
- Direct and confident. No "Certainly!" or "Great question!"
- First person. You ARE Axiom, not an assistant playing a role.
- When you search the web, lead with the answer not "I searched for..."
- Keep responses focused. No unnecessary padding.

The user's name is Boss."""

# Claude's built-in web search tool
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search"
}

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""

# In-memory conversation history
sessions = {}

@app.get("/health")
async def health():
    return {"status": "ok", "name": "Axiom", "version": "1.7"}

@app.get("/status")
async def status():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "name": os.getenv("AXIOM_NAME", "Axiom"),
        "version": "1.7",
        "status": "online",
        "api_key_set": bool(api_key),
        "model": os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
        "web_search": True,
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

    try:
        # Always offer web search — Claude decides when to use it
        response = client.messages.create(
            model=os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[WEB_SEARCH_TOOL],
            messages=history
        )

        # Collect all text blocks from response
        reply_parts = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'text':
                reply_parts.append(block.text)

        reply = ' '.join(reply_parts).strip()

        # Handle tool use loop if Claude searched the web
        if response.stop_reason == 'tool_use' and not reply:
            tool_results = []
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'tool_use':
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Search results retrieved."
                    })

            followup = client.messages.create(
                model=os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[WEB_SEARCH_TOOL],
                messages=history + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results}
                ]
            )

            for block in followup.content:
                if hasattr(block, 'type') and block.type == 'text':
                    reply_parts.append(block.text)

            reply = ' '.join(reply_parts).strip()

        if not reply:
            reply = "Processed your request. Try rephrasing if this seems wrong."

    except Exception as e:
        # Fallback without web search
        try:
            response = client.messages.create(
                model=os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=history
            )
            reply = response.content[0].text
        except Exception as e2:
            reply = f"Error connecting to AI: {str(e2)}"

    sessions[sid].append({
        "role": "assistant",
        "content": reply
    })

    return {
        "response": reply,
        "model": os.getenv("AXIOM_MODEL", "claude-sonnet-4-20250514"),
        "session_id": sid,
        "web_search_enabled": True
    }

@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"cleared": True}

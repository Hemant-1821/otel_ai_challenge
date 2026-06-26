"""otel AI Revenue Manager — FastAPI application."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import AsyncGenerator

# Project root on path so imports work regardless of CWD
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from fastapi import Cookie, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel

from agent.agent import agent
from server.auth import create_session, verify_session

app = FastAPI(title="otel AI Revenue Manager")

# Use Jinja2 Environment directly — avoids Starlette adding url_for to env.globals
# which makes the LRU cache key unhashable (tuple containing dict) in Jinja2 3.1.x
_tmpl_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=True,
)


def render(name: str, **ctx: object) -> HTMLResponse:
    return HTMLResponse(_tmpl_env.get_template(name).render(**ctx))


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    thread_id: str


# ── SSE callback bridge ───────────────────────────────────────────────────────

class _SSECallback(BaseCallbackHandler):
    """Bridges sync LangChain callbacks → async SSE queue."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        self._q = queue
        self._loop = loop

    def _emit(self, event: dict) -> None:
        asyncio.run_coroutine_threadsafe(self._q.put(event), self._loop)

    def on_tool_start(self, serialized, input_str, **kwargs):
        self._emit({
            "type": "tool_start",
            "name": serialized.get("name", "tool"),
            "input": str(input_str)[:400],
        })

    def on_tool_end(self, output, **kwargs):
        self._emit({"type": "tool_done", "output": str(output)[:600]})

    def on_llm_start(self, serialized, prompts, **kwargs):
        self._emit({"type": "llm_start"})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse("/chat")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "otel-rm-agent"}


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return render("login.html")


@app.post("/login")
async def do_login(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", "")).strip()

    if username == os.environ.get("CHAT_USERNAME", "admin") and \
       password == os.environ.get("CHAT_PASSWORD", "admin"):
        resp = RedirectResponse("/chat", status_code=303)
        resp.set_cookie("session", create_session(username), httponly=True,
                        max_age=86400, samesite="lax")
        return resp

    return render("login.html", error="Invalid username or password")


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(session: str = Cookie(None)):
    username = verify_session(session)
    if not username:
        return RedirectResponse("/login", status_code=303)
    return render("chat.html", username=username, thread_id=f"rm-{username}")


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, session: str = Cookie(None)):
    username = verify_session(session)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async def generate() -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()
        cb = _SSECallback(q, loop)

        def run_agent() -> None:
            try:
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": body.message}]},
                    config={
                        "recursion_limit": 15,
                        "configurable": {"thread_id": body.thread_id},
                        "callbacks": [cb],
                    },
                )
                last = result["messages"][-1]
                content = last.content if hasattr(last, "content") else str(last)
                asyncio.run_coroutine_threadsafe(
                    q.put({"type": "answer", "content": content}), loop
                )
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(
                    q.put({"type": "error", "content": str(exc)}), loop
                )
            finally:
                asyncio.run_coroutine_threadsafe(q.put(None), loop)

        threading.Thread(target=run_agent, daemon=True).start()

        while True:
            event = await q.get()
            if event is None:
                yield "event: done\ndata: {}\n\n"
                break
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

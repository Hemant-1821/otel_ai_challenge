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
from langgraph.types import Command
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


def _extract_text(content: object) -> str:
    """Normalise LangChain message content to a plain string.

    Claude returns a list of typed blocks when it also emits tool calls.
    We pull out only the text blocks so markdown rendering doesn't choke.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        ]
        return "\n".join(parts) if parts else ""
    return str(content)


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    thread_id: str


class ResumeRequest(BaseModel):
    thread_id: str
    approved: bool


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


# ── Shared agent runner ───────────────────────────────────────────────────────

def _run_and_stream(
    invoke_input: object,
    thread_id: str,
    q: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Invoke the agent, detect HITL interrupts, push SSE events to queue."""
    cb = _SSECallback(q, loop)
    config = {
        "recursion_limit": 40,
        "configurable": {"thread_id": thread_id},
        "callbacks": [cb],
    }

    def emit(event: dict) -> None:
        asyncio.run_coroutine_threadsafe(q.put(event), loop)

    try:
        agent.invoke(invoke_input, config=config)

        # Check whether the graph paused on a HITL interrupt
        snapshot = agent.get_state({"configurable": {"thread_id": thread_id}})

        if snapshot.next:
            # Extract HITLRequest from the interrupt value stored in snapshot tasks
            tool_name = "get_as_of_otb"
            tool_params: dict = {}
            for task in snapshot.tasks or []:
                for intr in getattr(task, "interrupts", None) or []:
                    val = getattr(intr, "value", None)
                    if isinstance(val, dict) and "action_requests" in val:
                        reqs = val["action_requests"]
                        if reqs:
                            tool_name = reqs[0].get("name", tool_name)
                            tool_params = reqs[0].get("args", {})

            emit({
                "type": "hitl",
                "tool": tool_name,
                "params": tool_params,
            })
        else:
            # Normal completion — send the final answer
            msgs = snapshot.values.get("messages", [])
            last = msgs[-1] if msgs else None
            content = _extract_text(last.content) if last and hasattr(last, "content") else ""
            emit({"type": "answer", "content": content})

    except Exception as exc:
        emit({"type": "error", "content": str(exc)})
    finally:
        asyncio.run_coroutine_threadsafe(q.put(None), loop)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse("/chat")


@app.get("/health")
async def health():
    proof_path = Path(__file__).parent.parent / "etl" / "LOAD_PROOF.json"
    with proof_path.open() as f:
        proof = json.load(f)
    return {
        "db_fingerprint": proof["reservation_stay_status_sha256"],
        "dataset_revision": proof["dataset_revision"],
        "row_hash": proof["row_hash"],
        "financial_status_posted_only_rows": proof["financial_status_posted_only_rows"],
    }


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

        threading.Thread(
            target=_run_and_stream,
            args=(
                {"messages": [{"role": "user", "content": body.message}]},
                body.thread_id,
                q,
                loop,
            ),
            daemon=True,
        ).start()

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


@app.post("/api/chat/resume")
async def chat_resume(body: ResumeRequest, session: str = Cookie(None)):
    username = verify_session(session)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async def generate() -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()

        decision = "approve" if body.approved else "reject"
        resume_payload = {"decisions": [{"type": decision}]}

        threading.Thread(
            target=_run_and_stream,
            args=(
                Command(resume=resume_payload),
                body.thread_id,
                q,
                loop,
            ),
            daemon=True,
        ).start()

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

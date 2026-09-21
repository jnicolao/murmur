"""Murmur Phase 1: the voice loop.

    apps/api/.venv/bin/uvicorn murmur.app:app --port 8000

The client is a single static page. Next.js arrives in Phase 2, when there are
real screens to build (entry list, mood timeline) rather than one button.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from murmur.ws.session import Session

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Murmur")
session: Session | None = None


@app.on_event("startup")
async def load_models() -> None:
    global session
    session = await asyncio.to_thread(Session)
    await asyncio.to_thread(session.warm)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"ok": session is not None}


@app.websocket("/ws")
async def voice(websocket: WebSocket) -> None:
    await websocket.accept()
    assert session is not None

    buffer = bytearray()
    turn: asyncio.Task | None = None
    cancelled = asyncio.Event()

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"] is not None:
                buffer.extend(message["bytes"])
                continue

            text = message.get("text")
            if text is None:
                break

            if '"end"' in text:
                if turn and not turn.done():
                    cancelled.set()
                    await turn
                cancelled = asyncio.Event()
                pcm, buffer = bytes(buffer), bytearray()
                turn = asyncio.create_task(session.run_turn(websocket, pcm, cancelled))
            elif '"stop"' in text:
                cancelled.set()
                buffer.clear()
    except WebSocketDisconnect:
        pass
    finally:
        cancelled.set()
        if turn:
            with contextlib.suppress(Exception):
                await turn

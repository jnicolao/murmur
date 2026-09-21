"""Murmur Phase 2: the voice loop, the crisis path, and somewhere to keep it.

    docker compose up -d
    apps/api/.venv/bin/uvicorn murmur.app:app --port 8000

The client is still a single static page. Next.js is deferred to Phase 3,
where the mood timeline gives a framework something real to do.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from murmur.ws.session import Session

STATIC = Path(__file__).resolve().parent / "static"
session: Session | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session
    session = await asyncio.to_thread(Session)
    await asyncio.to_thread(session.warm)
    yield
    if session:
        session.store.close()


app = FastAPI(title="Murmur", lifespan=lifespan)


def store():
    if session is None:
        raise HTTPException(503, "still waking up")
    return session.store


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"ok": session is not None}


@app.get("/entries")
async def entries() -> list[dict]:
    return await asyncio.to_thread(store().entries)


@app.get("/entries/{entry_id}")
async def entry(entry_id: int) -> list[dict]:
    return await asyncio.to_thread(store().transcript_of, entry_id)


@app.post("/entries/{entry_id}/mood")
async def mood(entry_id: int, value: int = Body(..., embed=True)) -> dict:
    if not 1 <= value <= 5:
        raise HTTPException(400, "mood is 1 to 5")
    await asyncio.to_thread(store().set_mood, entry_id, value)
    return {"ok": True}


@app.delete("/entries/{entry_id}")
async def delete_entry(entry_id: int) -> dict:
    await asyncio.to_thread(store().delete_entry, entry_id)
    return {"ok": True}


@app.post("/forget")
async def forget(confirm: str = Body(..., embed=True)) -> dict:
    """Wipe every entry and every recording. Deliberately awkward to call."""
    if confirm != "forget everything":
        raise HTTPException(400, "confirmation phrase did not match")
    await asyncio.to_thread(store().forget_everything)
    return {"ok": True}


@app.websocket("/ws")
async def voice(websocket: WebSocket) -> None:
    await websocket.accept()
    assert session is not None

    buffer = bytearray()
    turn: asyncio.Task | None = None
    cancelled = asyncio.Event()
    entry_id: int | None = None

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
                if entry_id is None:
                    entry_id = await asyncio.to_thread(session.store.start_entry)
                    await websocket.send_json({"type": "entry", "id": entry_id})
                pcm, buffer = bytes(buffer), bytearray()
                turn = asyncio.create_task(session.run_turn(websocket, entry_id, pcm, cancelled))
            elif '"stop"' in text:
                cancelled.set()
                buffer.clear()
            elif '"mood"' in text and entry_id is not None:
                import json

                value = json.loads(text).get("value")
                if isinstance(value, int) and 1 <= value <= 5:
                    await asyncio.to_thread(session.store.set_mood, entry_id, value)
    except WebSocketDisconnect:
        pass
    finally:
        cancelled.set()
        if turn:
            with contextlib.suppress(Exception):
                await turn
        if entry_id is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(session.store.end_entry, entry_id)

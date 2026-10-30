"""The Murmur API, and the client it serves.

    docker compose up -d
    make web        # builds apps/web into a static export
    apps/api/.venv/bin/uvicorn murmur.app:app --port 8000

In production this process serves everything from one origin, so there is one
thing to run. For working on the client, `make dev` runs the Next.js dev
server on port 3000 against this API instead.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from murmur.affect.trend import Window, describe
from murmur.ws.session import Session

WEB = Path(__file__).resolve().parents[2] / "web" / "out"
DEV_ORIGIN = "http://localhost:3000"
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

# Only ever the local dev server. Nothing about this application is meant to
# be reachable from anywhere else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[DEV_ORIGIN, "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if (WEB / "_next").is_dir():
    app.mount("/_next", StaticFiles(directory=WEB / "_next"), name="next")


def store():
    if session is None:
        raise HTTPException(503, "still waking up")
    return session.store


@app.get("/")
async def index():
    page = WEB / "index.html"
    if not page.exists():
        return HTMLResponse(
            "<p style='font:16px system-ui;padding:40px'>The client has not been built. "
            "Run <code>make web</code>, then reload.</p>",
            status_code=503,
        )
    return FileResponse(page)


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


@app.get("/timeline")
async def timeline(days: int = 90) -> dict:
    """Points to plot, and a sentence only when it has been earned."""
    keep = max(1, min(days, 365))
    points = await asyncio.to_thread(store().daily_mood, keep)
    recent = await asyncio.to_thread(store().mood_window, 7, 0)
    earlier = await asyncio.to_thread(store().mood_window, 14, 7)

    trend = describe(
        Window(
            recent["self_mood"], recent["est_valence"], recent["check_ins"], recent["utterances"]
        ),
        Window(
            earlier["self_mood"],
            earlier["est_valence"],
            earlier["check_ins"],
            earlier["utterances"],
        ),
    )
    return {
        "points": [
            {
                "day": str(point["day"]),
                "self_mood": point["self_mood"],
                "est_valence": point["est_valence"],
                "entries": point["entries"],
                "utterances": point["utterances"],
            }
            for point in points
        ],
        "trend": {"text": trend.text, "reason": trend.reason},
    }


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

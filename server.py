"""
Ouroboros Agent Server — Self-editable entry point.

This file lives in REPO_DIR and can be modified by the agent.
It runs as a subprocess of the launcher, serving the web UI and
coordinating the supervisor/worker system.

Starlette + uvicorn on localhost:{PORT}.
"""

import asyncio
import json
import logging
import os
import pathlib
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

import uvicorn

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_DIR = pathlib.Path(os.environ.get("OUROBOROS_REPO_DIR", pathlib.Path(__file__).parent))
DATA_DIR = pathlib.Path(os.environ.get("OUROBOROS_DATA_DIR",
    pathlib.Path.home() / "Ouroboros" / "data"))
PORT = int(os.environ.get("OUROBOROS_SERVER_PORT", "8765"))
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(REPO_DIR))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_log_dir = DATA_DIR / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
from logging.handlers import RotatingFileHandler
_file_handler = RotatingFileHandler(
    _log_dir / "server.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8",
)
logging.basicConfig(format=_LOG_FORMAT, level=logging.INFO, handlers=[_file_handler])
logger = logging.getLogger("server")

# ---------------------------------------------------------------------------
# Supervisor Message Bus
# ---------------------------------------------------------------------------
supervisor: Optional[Any] = None  # Set by launcher

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

async def index(request: Request) -> HTMLResponse:
    """Serve main page."""
    html_file = REPO_DIR / "web" / "index.html"
    with open(html_file, encoding="utf-8") as f:
        return HTMLResponse(f.read())

async def health(request: Request) -> JSONResponse:
    """Health check."""
    return JSONResponse({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

def _send_progress(message: str, level: str = "INFO") -> bool:
    """Send progress message via supervisor message bus."""
    global supervisor
    if supervisor is None:
        return False
    try:
        supervisor.send_progress(message, level=level)
    except Exception as e:
        logger.error(f"Failed to send progress: {e}")
        return False
    return True

async def upload_file(request: Request) -> JSONResponse:
    """Upload file from UI to DATA_DIR/uploads."""
    try:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "filename"):
            return JSONResponse({"error": "No file provided"}, status_code=400)

        if not file.filename:
            return JSONResponse({"error": "Empty filename"}, status_code=400)

        safe_filename = pathlib.Path(file.filename).name
        for c in safe_filename:
            if ord(c) < 32 or c in ':"/\\|?*\x7f':
                safe_filename = safe_filename.replace(c, "_")

        destination = UPLOAD_DIR / safe_filename
        offset = 0
        while destination.exists():
            offset += 1
            stem = pathlib.Path(file.filename).stem
            suffix = pathlib.Path(file.filename).suffix
            safe_filename = f"{stem}_{offset}{suffix}"
            destination = UPLOAD_DIR / safe_filename

        content = await file.read()
        with open(destination, "wb") as f:
            f.write(content)

        _send_progress(f"📁 File uploaded: {safe_filename} ({len(content)} bytes)", level="INFO")

        return JSONResponse({
            "status": "success",
            "filename": safe_filename,
            "size": len(content),
            "path": str(destination.relative_to(DATA_DIR))
        })

    except Exception as e:
        logger.exception("File upload failed")
        return JSONResponse({"error": str(e)}, status_code=500)

routes = [
    Route("/", index),
    Route("/health", health),
    Route("/api/file/upload", upload_file, methods=["POST"]),
    WebSocketRoute("/ws/", websocket_endpoint),
]

# ---------------------------------------------------------------------------
# WebSocket Handler
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, ws_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[ws_id] = websocket
        logger.info(f"WebSocket connected: {ws_id}")

    def disconnect(self, ws_id: str):
        if ws_id in self.active:
            del self.active[ws_id]
            logger.info(f"WebSocket disconnected: {ws_id}")

    async def send_message(self, ws_id: str, message: Any):
        if ws_id in self.active:
            try:
                await self.active[ws_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to {ws_id}: {e}")

    async def broadcast(self, message: Any, exclude_ws_id: Optional[str] = None):
        for ws_id, ws in list(self.active.items()):
            if ws_id != exclude_ws_id:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {ws_id}: {e}")

manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time messages."""
    ws_id = str(uuid.uuid4())
    await manager.connect(ws_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from {ws_id}: {data}")

    except WebSocketDisconnect:
        manager.disconnect(ws_id)

# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app() -> Starlette:
    """Create Starlette application."""
    routes_full = routes + [
        Mount("/static", app=StaticFiles(directory=str(REPO_DIR / "web"/"static")), name="static")
    ]

    app = Starlette(
        debug=True,
        routes=routes_full,
        on_startup=[startup],
        on_shutdown=[shutdown],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        logger.info(f"{request.method} {request.url.path} {response.status_code} {duration*1000:.1f}ms")
        return response

    return app

app = create_app()

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def startup():
    """On startup."""
    _send_progress("🌐 Server started", level="INFO")

async def shutdown():
    """On shutdown."""
    _send_progress("🛑 Server shutting down", level="INFO")

def run_server():
    """Run uvicorn server in a thread."""
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.serve())

def start_in_thread():
    """Start server in background thread."""
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    start_in_thread()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Server stopped")
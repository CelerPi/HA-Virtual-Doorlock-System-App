from __future__ import annotations

import asyncio
import base64
import contextlib
import threading
import time
from typing import Any

import aiohttp
from aiohttp import web

from .config import IntercomConfig


class VDSApi:
    def __init__(self, core: Any, config: IntercomConfig) -> None:
        self.core = core
        self.config = config

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/health", self.health)
        app.router.add_get("/api/status", self.status)
        app.router.add_get("/api/frame", self.frame)
        app.router.add_get("/api/audio", self.get_audio)
        app.router.add_post("/api/audio", self.post_audio)
        app.router.add_post("/api/unlock", self.control)
        app.router.add_post("/api/answer", self.control)
        app.router.add_post("/api/hangup", self.control)
        app.router.add_post("/api/monitor/start", self.monitor)
        app.router.add_post("/api/monitor/stop", self.monitor)
        app.router.add_get("/api/ws", self.websocket)
        return app

    async def health(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._json(403, {"ok": False, "error": "forbidden"})
        return self._json(200, {"ok": True})

    async def status(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._json(403, {"ok": False, "error": "forbidden"})
        return self._json(
            200,
            {
                "runtime": self.core.frame_hub.snapshot(),
                "config": self.config.as_dict(),
            },
        )

    async def frame(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._json(403, {"ok": False, "error": "forbidden"})

        frame = self.core.frame_hub.get_frame()
        if frame is None:
            return self._json(404, {"ok": False, "error": "no_frame"})
        return web.Response(body=frame, content_type="image/jpeg")

    async def get_audio(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._json(403, {"ok": False, "error": "forbidden"})

        try:
            since = int(request.query.get("since", 0))
        except (TypeError, ValueError):
            since = 0

        chunks = self.core.frame_hub.get_audio_chunks(since)
        return self._json(
            200,
            {
                "ok": True,
                "audio_id": self.core.frame_hub.snapshot().get("audio_id", 0),
                "chunks": [
                    {"id": aid, "pcm": base64.b64encode(pcm).decode("ascii")}
                    for aid, pcm in chunks
                ],
            },
        )

    async def post_audio(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._json(403, {"ok": False, "error": "forbidden"})

        body = await self._read_json(request)
        target_ip = str(body.get("target_ip", "")).strip()
        pcm_b64 = str(body.get("pcm", ""))
        if not target_ip or not pcm_b64:
            return self._json(400, {"ok": False, "error": "missing_target_ip_or_pcm"})

        try:
            pcm = base64.b64decode(pcm_b64)
        except Exception:
            return self._json(400, {"ok": False, "error": "invalid_pcm_base64"})

        if len(pcm) % 2 != 0:
            return self._json(400, {"ok": False, "error": "pcm_length_must_be_even"})

        accepted = self.core.request_outgoing_audio(target_ip, pcm)
        if not accepted:
            return self._json(409, {"ok": False, "error": "audio_request_rejected"})
        return self._json(200, {"ok": True, "target_ip": target_ip, "samples": len(pcm) // 2})

    async def control(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._json(403, {"ok": False, "error": "forbidden"})

        body = await self._read_json(request)
        target_ip = body.get("target_ip") or self.core.frame_hub.snapshot().get("target_ip")
        if not target_ip:
            return self._json(409, {"ok": False, "error": "no_active_call"})

        path = request.path
        if path == "/api/unlock":
            accepted = self.core.request_unlock(str(target_ip))
            action = "unlock"
        elif path == "/api/answer":
            accepted = self.core.request_answer(str(target_ip))
            action = "answer"
        else:
            accepted = self.core.request_hangup(str(target_ip))
            action = "hangup"

        if not accepted:
            return self._json(409, {"ok": False, "error": "request_rejected", "action": action})
        return self._json(200, {"ok": True, "action": action, "target_ip": target_ip})

    async def monitor(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._json(403, {"ok": False, "error": "forbidden"})

        body = await self._read_json(request)
        target_ip = str(body.get("target_ip", "")).strip()
        if not target_ip:
            return self._json(400, {"ok": False, "error": "missing_target_ip"})

        action = "start" if request.path == "/api/monitor/start" else "stop"
        if action == "start":
            accepted = self.core.request_monitor_start(target_ip)
        else:
            accepted = self.core.request_monitor_stop(target_ip)

        if not accepted:
            return self._json(409, {"ok": False, "error": "monitor_request_rejected"})
        return self._json(200, {"ok": True, "action": action, "target_ip": target_ip})

    async def websocket(self, request: web.Request) -> web.WebSocketResponse:
        if not self._authorized(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({"type": "error", "error": "forbidden"})
            await ws.close()
            return ws

        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)

        receive_task = asyncio.create_task(self._receive_ws(ws))
        try:
            last_frame_id = -1
            last_audio_id = -1
            last_snapshot: dict[str, Any] | None = None
            next_status_at = 0.0
            while not ws.closed:
                snapshot = self.core.frame_hub.snapshot()
                now = time.monotonic()
                status_snapshot = {
                    key: value
                    for key, value in snapshot.items()
                    if key not in {"frame_id", "audio_id", "has_frame", "has_audio"}
                }
                if status_snapshot != last_snapshot or now >= next_status_at:
                    if not await self._safe_send_json(
                        ws,
                        {
                            "type": "status",
                            "runtime": snapshot,
                            "config": self.config.as_dict(),
                        },
                    ):
                        break
                    last_snapshot = status_snapshot
                    next_status_at = now + 1.0

                frame_id = int(snapshot.get("frame_id", 0))
                if frame_id != last_frame_id:
                    frame = self.core.frame_hub.get_frame()
                    if frame is not None:
                        if not await self._safe_send_bytes(ws, b"VDSF" + frame_id.to_bytes(4, "big") + frame):
                            break
                    last_frame_id = frame_id

                chunks = self.core.frame_hub.get_audio_chunks(last_audio_id)
                if chunks:
                    for audio_id, pcm in chunks:
                        if not await self._safe_send_bytes(ws, b"VDSA" + audio_id.to_bytes(4, "big") + pcm):
                            return ws
                        last_audio_id = max(last_audio_id, audio_id)

                await asyncio.sleep(0.02)
        finally:
            receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, ConnectionResetError, aiohttp.ClientConnectionError, RuntimeError):
                await receive_task
        return ws

    async def _receive_ws(self, ws: web.WebSocketResponse) -> None:
        try:
            async for msg in ws:
                if msg.type != web.WSMsgType.TEXT:
                    continue
                try:
                    data = msg.json()
                except ValueError:
                    continue
                if data.get("type") != "audio":
                    continue

                target_ip = str(data.get("target_ip", "")).strip()
                pcm_b64 = str(data.get("pcm", ""))
                if not target_ip or not pcm_b64:
                    continue
                with contextlib.suppress(Exception):
                    pcm = base64.b64decode(pcm_b64)
                    self.core.request_outgoing_audio(target_ip, pcm)
        except (ConnectionResetError, aiohttp.ClientConnectionError, RuntimeError) as exc:
            print(f"[api] WebSocket receive stopped: {exc}", flush=True)

    async def _safe_send_json(self, ws: web.WebSocketResponse, data: dict[str, Any]) -> bool:
        if ws.closed:
            return False
        try:
            await ws.send_json(data)
            return True
        except (ConnectionResetError, aiohttp.ClientConnectionError, RuntimeError) as exc:
            print(f"[api] WebSocket send_json stopped: {exc}", flush=True)
            return False

    async def _safe_send_bytes(self, ws: web.WebSocketResponse, data: bytes) -> bool:
        if ws.closed:
            return False
        try:
            await ws.send_bytes(data)
            return True
        except (ConnectionResetError, aiohttp.ClientConnectionError, RuntimeError) as exc:
            print(f"[api] WebSocket send_bytes stopped: {exc}", flush=True)
            return False

    def _authorized(self, request: web.Request) -> bool:
        if not self.config.api_token:
            return False
        auth_header = request.headers.get("Authorization", "")
        token = request.query.get("token", "")
        return auth_header == f"Bearer {self.config.api_token}" or token == self.config.api_token

    async def _read_json(self, request: web.Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _json(self, status: int, body: dict[str, Any]) -> web.Response:
        return web.json_response(body, status=status)


class ApiServer:
    def __init__(self, core: Any, config: IntercomConfig) -> None:
        self.core = core
        self.config = config
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runner: web.AppRunner | None = None
        self._started = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._started.clear()
        self._thread = threading.Thread(target=self._run, name="VDS-API", daemon=True)
        self._thread.start()
        self._started.wait(timeout=5)

    def stop(self) -> None:
        if self._loop is None:
            return

        future = asyncio.run_coroutine_threadsafe(self._cleanup(), self._loop)
        with contextlib.suppress(Exception):
            future.result(timeout=3)
        self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._loop = None
        self._runner = None

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start_async())
            self._started.set()
            loop.run_forever()
        finally:
            loop.run_until_complete(self._cleanup())
            loop.close()

    async def _start_async(self) -> None:
        self._runner = web.AppRunner(VDSApi(self.core, self.config).app())
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.config.api_host, self.config.api_port)
        await site.start()

    async def _cleanup(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

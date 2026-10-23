import asyncio
from typing import List, Optional
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

    def _schedule_broadcast(self, message: dict):
        asyncio.create_task(self.broadcast(message))

    def broadcast_sync(self, message: dict):
        if not self.active_connections:
            return

        loop = self._loop
        if not loop or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
                self._loop = loop
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            try:
                loop.call_soon_threadsafe(self._schedule_broadcast, message)
            except Exception:
                pass
        else:
            try:
                asyncio.run(self.broadcast(message))
            except Exception:
                pass

manager = ConnectionManager()

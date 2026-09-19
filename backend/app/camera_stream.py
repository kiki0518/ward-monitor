"""Single-camera JPEG relay. Run with one Uvicorn worker (in-memory state)."""
import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
MAX_FRAME_BYTES = 2 * 1024 * 1024
STALE_SECONDS = 3


class CameraStream:
    def __init__(self):
        self.publisher = None
        self.frame = None
        self.sequence = 0
        self.received_at = 0
        self.changed = asyncio.Condition()

    async def next_frame(self, previous):
        async with self.changed:
            try:
                await asyncio.wait_for(self.changed.wait_for(
                    lambda: self.sequence != previous or self.publisher is None
                ), timeout=1)
            except asyncio.TimeoutError:
                pass
            fresh = self.frame is not None and time.monotonic() - self.received_at < STALE_SECONDS
            return self.sequence, self.frame if fresh else None


@router.websocket('/ws/camera/publish')
async def publish(ws: WebSocket):
    stream = ws.app.state.camera
    await ws.accept()
    if stream.publisher is not None:
        await ws.close(code=1008, reason='A camera is already publishing')
        return
    stream.publisher = ws
    try:
        await ws.send_text('ready')
        while True:
            message = await asyncio.wait_for(ws.receive(), timeout=10)
            if message['type'] == 'websocket.disconnect':
                break
            frame = message.get('bytes')
            # Envelope check only; browser does JPEG decoding. Never decode/re-encode here.
            if frame is None or not (4 <= len(frame) <= MAX_FRAME_BYTES):
                await ws.close(code=1009, reason='Expected JPEG bytes, maximum 2 MiB')
                break
            if not (frame.startswith(b'\xff\xd8') and frame.endswith(b'\xff\xd9')):
                await ws.close(code=1003, reason='Invalid JPEG envelope')
                break
            async with stream.changed:
                stream.frame = frame
                stream.sequence += 1
                stream.received_at = time.monotonic()
                stream.changed.notify_all()
            # Publisher waits for ACK before taking the latest camera sample.
            await asyncio.wait_for(ws.send_text('ok'), timeout=5)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        async with stream.changed:
            stream.publisher = None
            stream.frame = None
            stream.sequence += 1
            stream.changed.notify_all()
        try:
            await ws.close()
        except RuntimeError:
            pass


@router.websocket('/ws/camera/view')
async def view(ws: WebSocket):
    stream = ws.app.state.camera
    await ws.accept()
    previous = -1
    try:
        while True:
            if await asyncio.wait_for(ws.receive_text(), timeout=30) != 'next':
                await ws.close(code=1008, reason='Expected next')
                return
            sequence, frame = await stream.next_frame(previous)
            if frame is not None and sequence != previous:
                await asyncio.wait_for(ws.send_bytes(frame), timeout=5)
            else:
                await ws.send_json({'status': 'waiting' if frame is None else 'unchanged'})
                # No publisher means the condition returns immediately. Limit polling.
                if stream.publisher is None:
                    await asyncio.sleep(0.2)
            previous = sequence
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass

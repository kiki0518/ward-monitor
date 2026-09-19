# FastAPI server + WebSocket，是前端唯一要對接的入口
# 對應 API_CONTRACT.md：
#   GET  /api/beds                      -> 床位靜態名冊
#   WS   /ws/overview                   -> 總覽頁，持續推送 OverviewUpdate[]
#   WS   /ws/room/{bed_id}              -> RoomDetail 頁：state(vitals+active_events) + WebRTC signaling
#   GET  /api/beds/{bed_id}/events      -> 該床目前 active 事件（不含已 resolved），priority 高到低排序
#   POST /api/events/{event_id}/resolve -> 護理站標記事件已處理（idempotent）

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .camera_stream import CameraStream, router as camera_router

from app import simulator, store
from app.schemas import BedInfo, RoomDetailUpdate, WardAgentOutput


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.camera = CameraStream()
    store.seed_demo_data()
    background_tasks = [
        asyncio.create_task(simulator.run_vitals_jitter()),
        asyncio.create_task(simulator.run_event_script()),
    ]
    yield
    for task in background_tasks:
        task.cancel()


app = FastAPI(lifespan=lifespan)
app.include_router(camera_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://10.28.50.69:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/api/beds", response_model=list[BedInfo])
def list_beds():
    return store.get_all_beds()


@app.get("/api/beds/{bed_id}/events", response_model=list[WardAgentOutput])
def list_bed_events(bed_id: str):
    if not store.bed_exists(bed_id):
        raise HTTPException(status_code=404, detail="Bed not found")
    return store.get_event_history(bed_id)


@app.post("/api/events/{event_id}/resolve", response_model=WardAgentOutput)
def resolve_event(event_id: str):
    event = store.resolve_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.websocket("/ws/overview")
async def ws_overview(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            updates = [update.model_dump(mode="json") for update in store.get_all_overviews()]
            await websocket.send_json(updates)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/room/{bed_id}")
async def ws_room(websocket: WebSocket, bed_id: str):
    if not store.bed_exists(bed_id):
        await websocket.close(code=4004)
        return

    await websocket.accept()

    async def push_state():
        while True:
            vitals = store.get_vitals(bed_id)
            update = RoomDetailUpdate(
                bed_id=bed_id,
                ts=vitals.ts,
                vitals=vitals,
                active_events=store.get_active_events(bed_id),
            )
            await websocket.send_json(update.model_dump(mode="json"))
            await asyncio.sleep(1.5)

    push_task = asyncio.create_task(push_state())
    try:
        while True:
            # TODO: WebRTC signaling relay — 收到的 webrtc_offer/webrtc_answer/webrtc_ice
            # 要轉發給同一個 bed_id 上的另一方（board 或瀏覽器）。Board 端的 WebRTC 還沒接上，
            # 先只是收下不處理，避免連線被塞爆。
            await websocket.receive_json()
    except WebSocketDisconnect:
        pass
    finally:
        push_task.cancel()

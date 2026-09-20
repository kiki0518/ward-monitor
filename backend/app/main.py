# FastAPI server + WebSocket，是前端唯一要對接的入口
# 對應 API_CONTRACT.md：
#   GET  /api/beds                      -> 床位靜態名冊
#   WS   /ws/overview                   -> 總覽頁，持續推送 OverviewUpdate[]
#   WS   /ws/room/{bed_id}              -> RoomDetail 頁，預設 role=viewer（推送 state）；
#                                           board 端連 /ws/room/{bed_id}?role=board 上傳姿勢
#   GET  /api/beds/{bed_id}/events      -> 該床目前 active 事件（不含已 resolved），priority 高到低排序
#   GET  /api/beds/{bed_id}/events/history -> 該床已處理事件紀錄，resolved_at 新到舊（寫進 event_history.json，重啟即清空）
#   POST /api/beds/{bed_id}/possible-fall -> Board 端回報疑似跌倒，backend 不重新驗證，直接建立/更新事件
#   POST /api/events/{event_id}/resolve -> 護理站標記事件已處理，body 附病例紀錄（idempotent，寫進 case_reports.json）
#   /api/beds/{bed_id}/handover-*       -> AI 草稿、人工確認送出與交班紀錄（handover.py）
#
# 影像走另一條獨立的全域 pipe（不分 bed_id，demo 只有一床有真的攝影機）：
#   WS   /ws/camera/publish  -> board 端上傳 JPEG
#   WS   /ws/camera/view     -> 前端拉取最新 JPEG
# 這條在 camera_stream.py，見該檔案（GET /camera 監看頁已移除）。demo 用 bed_id "101"
# 當作有真實攝影機的那一床，這只是前端/文件上的慣例，不是後端 schema 裡的欄位。

import asyncio
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app import simulator, store
from app.handover import router as handover_router
from app.camera_stream import CameraStream
from app.camera_stream import router as camera_router
from app.schemas import (
    BedInfo,
    BoardPostureUpdate,
    PossibleFallReport,
    ResolveReportRequest,
    RoomDetailUpdate,
    WardAgentOutput,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Camera state and ward data must belong to the same exported FastAPI app.
    app.state.camera = CameraStream()
    store.seed_demo_data()
    background_tasks = [
        asyncio.create_task(simulator.run_vitals_jitter()),
        asyncio.create_task(simulator.run_vitals_alerting()),
        asyncio.create_task(simulator.run_posture_jitter()),
        asyncio.create_task(simulator.run_bathroom_jitter()),
        asyncio.create_task(simulator.run_location_alerting()),
        asyncio.create_task(simulator.run_event_script()),
    ]
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)
app.include_router(camera_router)
app.include_router(handover_router)

app.add_middleware(
    CORSMiddleware,
    # 用 regex 涵蓋常見區網 IP 段（192.168.x.x / 10.x.x.x / 172.16-31.x.x）+ localhost，
    # 這樣現場筆電換一次 IP 也不用回來改 CORS 設定，只要前端跟後端還在同一個區網就會通。
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}):\d+$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/api/beds", response_model=list[BedInfo])
def list_beds():
    return store.get_all_beds()


@app.get("/api/nurses", response_model=list[str])
def list_nurses():
    return store.get_all_nurses()


@app.get("/api/beds/{bed_id}/events", response_model=list[WardAgentOutput])
def list_bed_events(bed_id: str):
    if not store.bed_exists(bed_id):
        raise HTTPException(status_code=404, detail="Bed not found")
    return store.get_event_history(bed_id)


@app.get("/api/beds/{bed_id}/events/history", response_model=list[WardAgentOutput])
def list_bed_event_history(bed_id: str):
    if not store.bed_exists(bed_id):
        raise HTTPException(status_code=404, detail="Bed not found")
    return store.get_resolved_events(bed_id)


@app.post("/api/beds/{bed_id}/possible-fall", response_model=WardAgentOutput)
def report_possible_fall(bed_id: str, report: PossibleFallReport):
    if not store.bed_exists(bed_id):
        raise HTTPException(status_code=404, detail="Bed not found")
    return store.report_event(
        bed_id,
        ts=report.ts,
        state="possible_fall",
        priority="red",
        reason="疑似跌倒",
        location="out_of_bed",
        action="請護理師查看",
    )


@app.post("/api/events/{event_id}/resolve", response_model=WardAgentOutput)
def resolve_event(event_id: str, report: ResolveReportRequest):
    event = store.resolve_event(
        event_id,
        completed_actions=report.completed_actions,
        follow_up=report.follow_up,
        notes=report.notes,
    )
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
async def ws_room(websocket: WebSocket, bed_id: str, role: Literal["board", "viewer"] = "viewer"):
    if not store.bed_exists(bed_id):
        await websocket.close(code=4004)
        return

    await websocket.accept()

    if role == "board":
        await _handle_board_connection(websocket, bed_id)
    else:
        await _handle_viewer_connection(websocket, bed_id)


async def _handle_viewer_connection(websocket: WebSocket, bed_id: str) -> None:
    try:
        while True:
            vitals = store.get_vitals(bed_id)
            update = RoomDetailUpdate(
                bed_id=bed_id,
                ts=vitals.ts,
                vitals=vitals,
                active_events=store.get_active_events(bed_id),
                current_posture=store.get_posture(bed_id),
                in_camera=store.get_in_camera(bed_id),
                location=store.get_location(bed_id) if store.get_in_camera(bed_id) is not None else None,
            )
            await websocket.send_json(update.model_dump(mode="json"))
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass


async def _handle_board_connection(websocket: WebSocket, bed_id: str) -> None:
    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except ValueError:
                await websocket.close(code=1008, reason="Invalid JSON")
                return
            try:
                if not isinstance(raw, dict):
                    raise ValueError("Expected JSON object")
                update = BoardPostureUpdate(**{**raw, "bed_id": bed_id})
            except (ValidationError, ValueError):
                await websocket.close(code=1008, reason="Invalid board posture")
                return
            store.set_posture(bed_id, update.current_posture)
            store.set_in_camera(bed_id, update.in_camera)
    except WebSocketDisconnect:
        pass

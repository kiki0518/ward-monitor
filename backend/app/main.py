# FastAPI server + WebSocket，是前端唯一要對接的入口
# 對應 API_CONTRACT.md：
#   GET  /api/beds                      -> 床位靜態名冊
#   WS   /ws/overview                   -> 總覽頁，持續推送 OverviewUpdate[]
#   WS   /ws/room/{bed_id}              -> RoomDetail 頁：state(vitals+active_events) + WebRTC signaling
#   GET  /api/beds/{bed_id}/events      -> 該床目前 active 事件（不含已 resolved），priority 高到低排序
#   GET  /api/beds/{bed_id}/events/history -> 該床已處理事件紀錄，resolved_at 新到舊（寫進 event_history.json，重啟即清空）
#   POST /api/events/{event_id}/resolve -> 護理站標記事件已處理，body 附病例紀錄（idempotent，寫進 case_reports.json）
#   GET  /api/reports/export            -> 把 case_reports.json 整理成 PDF 下載，成功後清空 case_reports.json（摘要目前是假資料，待接 LLM）

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import report_generator, simulator, store
from app.camera_stream import CameraStream, router as camera_router
from app.schemas import BedInfo, ResolveReportRequest, RoomDetailUpdate, WardAgentOutput


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Camera state and ward data must belong to the same exported FastAPI app.
    app.state.camera = CameraStream()
    store.seed_demo_data()
    background_tasks = [
        asyncio.create_task(simulator.run_vitals_jitter()),
        asyncio.create_task(simulator.run_vitals_alerting()),
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

app.add_middleware(
    CORSMiddleware,
    # 用 regex 而不是寫死 port：Vite dev server 常因為 port 被佔用換 port（5173/5174/...），
    # 寫死單一 port 每次都要手動改，改用 regex 涵蓋 localhost/127.0.0.1/10.28.50.x 的任何 port。
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10\.28\.50\.\d{1,3}):\d+",
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


@app.get("/api/beds/{bed_id}/events/history", response_model=list[WardAgentOutput])
def list_bed_event_history(bed_id: str):
    if not store.bed_exists(bed_id):
        raise HTTPException(status_code=404, detail="Bed not found")
    return store.get_resolved_events(bed_id)


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


@app.get("/api/reports/export")
def export_reports():
    reports = store.get_case_reports()
    pdf_bytes = report_generator.generate_report_pdf(reports)
    store.clear_case_reports()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=ward-monitor-report.pdf"},
    )


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
        await asyncio.gather(push_task, return_exceptions=True)

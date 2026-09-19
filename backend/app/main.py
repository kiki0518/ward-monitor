# B3 負責：FastAPI server + WebSocket，是前端唯一要對接的入口
# 之後要接：
#   - 訂閱 B1 的 pose 資料 (直接呼叫 / MQTT，先簡單做直接呼叫)
#   - 訂閱 B2 的行為判斷/決策結果
#   - vitals_simulator 產生的假生理數據
#   - 統一格式後透過 /ws 推送給前端

from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app import store
from app.schemas import (
    EventsResponse,
    RoomDetailResponse,
    RoomSummary,
    RoomsResponse,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store.seed_demo_data()


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/api/rooms", response_model=RoomsResponse)
def list_rooms():
    rooms = [
        RoomSummary(
            bed_id=room.bed_id,
            patient_name=room.patient_name,
            is_live=room.is_live,
            risk_level=store.get_risk_level(room.bed_id),
            last_updated=room.last_updated,
        )
        for room in store.get_all_rooms()
    ]
    return RoomsResponse(rooms=rooms)


@app.get("/api/rooms/{bed_id}", response_model=RoomDetailResponse)
def get_room_detail(bed_id: str):
    room = store.get_room(bed_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return RoomDetailResponse(
        bed_id=room.bed_id,
        patient_name=room.patient_name,
        is_live=room.is_live,
        current_posture=room.current_posture,
        risk_level=store.get_risk_level(bed_id),
        latest_keypoints=room.latest_keypoints,
        latest_vitals=room.latest_vitals,
        habit_baseline=room.habit_baseline,
        medical_orders=room.medical_orders,
    )


@app.get("/api/rooms/{bed_id}/events", response_model=EventsResponse)
def get_room_events(bed_id: str, limit: int = Query(default=50, ge=1)):
    if not store.room_exists(bed_id):
        raise HTTPException(status_code=404, detail="Room not found")
    return EventsResponse(events=store.get_events(bed_id, limit))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # TODO: 迴圈推送病房狀態 / 關鍵點 / 體徵資料給前端
    await websocket.close()

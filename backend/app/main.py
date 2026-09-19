# B3 負責：FastAPI server + WebSocket，是前端唯一要對接的入口
# 之後要接：
#   - 訂閱 B1 的 pose 資料 (直接呼叫 / MQTT，先簡單做直接呼叫)
#   - 訂閱 B2 的行為判斷/決策結果
#   - vitals_simulator 產生的假生理數據
#   - 統一格式後透過 /ws 推送給前端

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from .camera_stream import CameraStream, router as camera_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.camera = CameraStream()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(camera_router)


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # TODO: 迴圈推送病房狀態 / 關鍵點 / 體徵資料給前端
    await websocket.close()

# Ward Monitor — 梅竹黑客松病房監測系統

詳細規格請見上層目錄的 `病房監測系統_Spec.md`。這裡只是專案骨架，內容邏輯還沒實作，先讓 5 人可以各自認領模組平行開工。

## 目錄結構

```
ward-monitor/
├── backend/            (Python + FastAPI + WebSocket)
│   └── app/
│       ├── main.py               ← B3：FastAPI server + WebSocket 入口
│       ├── schemas.py            ← 共用資料格式，大家先對好這裡
│       ├── pose_inference/       ← B1：板子端姿勢推論
│       ├── behavior_engine/      ← B2：行為狀態判斷 (含跌倒/夜遊/醫囑違規)
│       ├── patient_context/      ← B2：個人化基準 + 醫囑限制
│       ├── ward_agent/           ← B2：決策層 (risk/reason/priority/action)
│       └── vitals_simulator/     ← B3：假生理數據產生器
└── frontend/           (React + Vite)
    └── src/
        ├── pages/
        │   ├── Overview.jsx      ← F1：病房總覽 (卡片列表 + 狀態顏色)
        │   └── RoomDetail.jsx    ← F2：單病房詳細頁 (攝影機+骨架+體徵)
        ├── components/
        │   ├── RoomCard.jsx      ← F1
        │   ├── PoseOverlay.jsx   ← F2
        │   └── VitalsPanel.jsx   ← F2
        └── services/
            └── ws.js             ← WebSocket 連線邏輯，跟 B3 對格式
```

## 分工對照

| 負責人 | 模組 |
|---|---|
| B1 | `backend/app/pose_inference/` |
| B2 | `backend/app/behavior_engine/`、`patient_context/`、`ward_agent/` |
| B3 | `backend/app/main.py`、`vitals_simulator/`，統一 WebSocket 資料格式 |
| F1 | `frontend/src/pages/Overview.jsx`、`components/RoomCard.jsx` |
| F2 | `frontend/src/pages/RoomDetail.jsx`、`components/PoseOverlay.jsx`、`VitalsPanel.jsx` |

## 開工前必做

所有人先對齊 `backend/app/schemas.py` 裡的資料格式（Keypoints / BehaviorEvent / WardAgentOutput / Vitals），格式定好之後，每個人都可以用假資料開始寫，不用互相等。

## 啟動方式

### Camera 即時監看實驗

單獨測試「開發板 camera → server → 瀏覽器」請看 [streaming/README.md](streaming/README.md)。
直接轉送 camera 輸出的 MJPEG，透過 WebSocket 傳至 FastAPI；觀看入口為 `http://SERVER_IP:8000/camera`。
不需 H.264 編碼器、MediaMTX 或 React。請依 streaming 文件用單一 worker 啟動 backend。
若要同時跑 MoveNet，使用 `python3 streaming/movenet_test.py --server SERVER_IP`；
預設 `/dev/video2`，同一鏡頭分成原始 JPEG 串流和板子姿勢推論兩路。

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

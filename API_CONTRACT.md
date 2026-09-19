# 前後端 API 契約 (B3 ↔ F1/F2)

補充 README 提到、但目前找不到的 `病房監測系統_Spec.md` 的前後端契約部分。B1↔B2 之間的姿勢推論/行為判斷內部格式不在這份文件範圍內，仍以 `schemas.py` 裡的 `Keypoints` / `BehaviorEvent` 為準（維持 TODO，由 B1/B2 自行對齊）。

## 資料流

```
                         ┌───────────────────────────┐
Board(B1) 攝影機/姿勢推論 │                           │
   └─ Keypoints ────────▶│  B2: behavior_engine       │
                         │      + patient_context     │
                         │      + ward_agent          │
                         │        └─ WardAgentOutput ─┼──┐
   vitals_simulator ─────▶  (B3 內部)                 │  │
                         └───────────────────────────┘  │
                                                          ▼
                                                   B3 (FastAPI)
                         ┌──────────────────────────────────────┐
                         │ GET  /api/beds                        │──▶ F1 Overview（載入一次）
                         │ WS   /ws/overview                     │──▶ F1 Overview（持續推送）
                         │ WS   /ws/room/{bed_id}                │──▶ F2 RoomDetail（vitals+events+signaling）
                         │ POST /api/events/{event_id}/resolve   │◀── F2 RoomDetail（護理站標記已處理）
                         └──────────────────────────────────────┘

WebRTC 影像：Board(B1) ⇄ 瀏覽器 直接 P2P（同區網，不架 STUN/TURN），
B3 只在 /ws/room/{bed_id} 上轉發 SDP/ICE signaling，不經手影像本身。
```

## 端點

| 方法 | 路徑 | 用途 |
|---|---|---|
| GET | `/api/beds` | 一次性拉全部床位/病患靜態名冊 |
| WS | `/ws/overview` | 全床摘要，持續推送（總覽頁用） |
| WS | `/ws/room/{bed_id}` | 單床 vitals + active_events + WebRTC signaling（詳細頁用，進頁才連線） |
| POST | `/api/events/{event_id}/resolve` | 護理站標記事件已處理 |

## Schema

### `BedInfo`（`GET /api/beds` 回傳陣列的元素）
```json
{ "bed_id": "101", "patient_name": "王小明" }
```

### `OverviewUpdate`（`/ws/overview` 推送）
```json
[
  {
    "bed_id": "101",
    "priority": "green",
    "reason": "生理數據正常",
    "updated_at": "2026-09-19T14:32:10Z"
  },
  {
    "bed_id": "103",
    "priority": "red",
    "reason": "疑似跌倒",
    "updated_at": "2026-09-19T14:32:05Z"
  }
]
```
- `priority`: `"green" | "yellow" | "red"`，對應前端 `RoomCard` 的 `normal/warning/high`
- `reason`: 該床目前最高 priority 事件的 reason；沒有 active event 時填「生理數據正常」

### `WardAgentOutput`（事件，`RoomDetailUpdate.active_events` 的元素，也是 `resolve` 的回傳值）
```json
{
  "event_id": "evt_8f2a",
  "bed_id": "103",
  "state": "possible_fall",
  "priority": "red",
  "reason": "疑似跌倒",
  "location": "out_of_bed",
  "action": "請護理師查看",
  "started_at": "2026-09-19T14:31:50Z",
  "resolved_at": null
}
```
- `state` enum：`bed_exit`(離床) / `possible_fall`(疑似跌倒) / `abnormal_transition`(異常姿勢轉換) / `prolonged_sitting`(長期坐著) / `night_wandering`(夜間遊蕩) / `medical_order_violation`(違反醫囑限制) / `abnormal_vitals`(生理數據異常)
- `location` enum：`in_bed` / `out_of_bed` / `chair` / `near_door` / `bathroom`
- 一張床可以同時有多個 active event（`resolved_at` 為 `null` 的都算 active）

### `Vitals`
```json
{
  "bed_id": "103",
  "bp_systolic": 128,
  "bp_diastolic": 82,
  "temperature": 36.7,
  "heart_rate": 92,
  "spo2": 97,
  "ts": "2026-09-19T14:32:10Z"
}
```

### `RoomDetailUpdate`（`/ws/room/{bed_id}` 上 `type: "state"` 訊息，約 1-2 秒推一次）
```json
{
  "type": "state",
  "bed_id": "103",
  "ts": "2026-09-19T14:32:10Z",
  "vitals": { "...": "見上方 Vitals" },
  "active_events": [ "...WardAgentOutput 陣列..." ]
}
```

### WebRTC signaling（`/ws/room/{bed_id}` 上，用 `type` 跟 state 訊息共用同一條連線）
```json
{ "type": "webrtc_offer", "bed_id": "103", "sdp": "..." }
{ "type": "webrtc_answer", "bed_id": "103", "sdp": "..." }
{ "type": "webrtc_ice", "bed_id": "103", "candidate": { "...": "..." } }
```
- 影像本身不經過這個 JSON 通道，只有 SDP/ICE 交換走這裡；交換完成後 media 是 board 與瀏覽器 P2P 直連
- 影像是原始攝影機畫面，骨架線條目前**不**烤進畫面（前端不需要、也不會拿到 keypoints）

## 前端消費方式

- **Overview 頁**：載入時 `GET /api/beds` 拿名冊，之後靠 `/ws/overview` 的 `bed_id` 對應更新 priority/reason；`RoomCard` 的 `roomId`/`riskLevel` 之後改用 `bed_id`/`priority` 命名。
- **RoomDetail 頁**：進頁才建立 `/ws/room/{bed_id}` 連線，同時用收到的 offer/ice 建立 WebRTC PeerConnection 顯示影像；`active_events` 列表旁可以放「標記已處理」按鈕 → 呼叫 `POST /api/events/{event_id}/resolve`。

## 目前狀態

`backend/app/schemas.py`、`main.py`、`frontend/src/services/ws.js` 已依此契約補上函式/型別骨架（皆為 TODO body，尚未接上真實邏輯）。`Overview.jsx` / `RoomCard.jsx` 仍先用 `frontend/src/mock/rooms.js` 的假資料，等對應負責人把 TODO 補完再串接。

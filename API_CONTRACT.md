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
{
  "bed_id": "101",
  "patient_name": "王建國",
  "gender": "male",
  "age": 78,
  "diagnosis": "腦中風後遺症"
}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `bed_id` | string | 床號，例如 `"101"`；全系統的床位識別碼，其他所有 schema 都用同一組值對應 |
| `patient_name` | string | 病患姓名 |
| `gender` | enum | `"male"` / `"female"` |
| `age` | int | 病患年齡 |
| `diagnosis` | string | 病因/診斷，人類可讀，例如「腦中風後遺症」「髖關節骨折術後」，demo 用固定假資料，見 `backend/app/data/beds.csv` |

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

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `priority` | enum | `"green"`（正常）/ `"yellow"`（注意）/ `"red"`（高風險）。對應前端 `RoomCard` 的 `normal`/`warning`/`high`；取該床目前 active events 中優先度最高者，沒有 active event 時固定 `"green"` |
| `reason` | string | 人類可讀描述。有 active event 時填最高 priority 那個事件的 `reason`；沒有 active event 時固定「生理數據正常」 |
| `updated_at` | datetime (ISO 8601, UTC) | 例如 `"2026-09-19T14:32:10Z"`，這筆摘要的產生時間 |

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

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `event_id` | string | 事件唯一識別碼，由 B2 產生（例如 `"evt_8f2a"`） |
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `state` | enum | `bed_exit`（離床）/ `possible_fall`（疑似跌倒）/ `abnormal_transition`（異常姿勢轉換）/ `prolonged_sitting`（長期坐著）/ `night_wandering`（夜間遊蕩）/ `medical_order_violation`（違反醫囑限制）/ `abnormal_vitals`（生理數據異常） |
| `priority` | enum | `"green"` / `"yellow"` / `"red"`，同 `OverviewUpdate.priority` |
| `reason` | string | 人類可讀描述，例如「夜間離床超過 5 分鐘」「疑似跌倒」 |
| `location` | enum | `in_bed`（床上）/ `out_of_bed`（離床）/ `chair`（椅子上）/ `near_door`（門邊）/ `bathroom`（浴廁） |
| `action` | string \| null | 建議動作文字，例如「請護理師查看」；沒有建議動作時為 `null` |
| `started_at` | datetime (ISO 8601, UTC) | 事件觸發時間 |
| `resolved_at` | datetime \| null | 護理站按「標記已處理」的時間；`null` 代表事件仍 active。一張床可以同時有多個 `resolved_at` 為 `null` 的 active event |

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

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `bp_systolic` | int | 收縮壓，單位 mmHg。參考範圍約 `90–140`（`abnormal_vitals` 事件觸發的門檻由 B2 決定，這裡只是 `vitals_simulator` 產生假資料時的合理區間，非強制驗證） |
| `bp_diastolic` | int | 舒張壓，單位 mmHg。參考範圍約 `60–90` |
| `temperature` | float | 體溫，單位 °C。參考範圍約 `35.5–38.5`，變化較慢 |
| `heart_rate` | int | 心跳，單位 bpm。參考範圍約 `50–120`，模擬時做隨時間小幅波動 |
| `spo2` | int | 血氧飽和度，單位 %。參考範圍約 `90–100`，模擬時做隨時間小幅波動 |
| `ts` | datetime (ISO 8601, UTC) | 這筆生理數據的量測時間 |

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

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `type` | const | 固定為 `"state"`，前端用來跟 webrtc signaling 訊息區分 |
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `ts` | datetime (ISO 8601, UTC) | 這筆狀態訊息的產生時間 |
| `vitals` | `Vitals` | 見上方 `Vitals` schema |
| `active_events` | `WardAgentOutput[]` | 目前所有 `resolved_at` 為 `null` 的事件；可以是空陣列（代表無事件） |

### WebRTC signaling（`/ws/room/{bed_id}` 上，用 `type` 跟 state 訊息共用同一條連線）
```json
{ "type": "webrtc_offer", "bed_id": "103", "sdp": "..." }
{ "type": "webrtc_answer", "bed_id": "103", "sdp": "..." }
{ "type": "webrtc_ice", "bed_id": "103", "candidate": { "...": "..." } }
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `type` | enum | `webrtc_offer` / `webrtc_answer` / `webrtc_ice`（跟 `"state"` 共用同一個 `type` 欄位空間，前端靠這個字串分派） |
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `sdp` | string \| null | SDP payload，只有 `webrtc_offer`/`webrtc_answer` 會有值，`webrtc_ice` 時為 `null` |
| `candidate` | object \| null | ICE candidate 物件（瀏覽器 `RTCIceCandidate` 原生結構），只有 `webrtc_ice` 會有值，其餘為 `null` |

- 影像本身不經過這個 JSON 通道，只有 SDP/ICE 交換走這裡；交換完成後 media 是 board 與瀏覽器 P2P 直連
- 影像是原始攝影機畫面，骨架線條目前**不**烤進畫面（前端不需要、也不會拿到 keypoints）

## 前端消費方式

- **Overview 頁**：載入時 `GET /api/beds` 拿名冊，之後靠 `/ws/overview` 的 `bed_id` 對應更新 priority/reason；`RoomCard` 的 `roomId`/`riskLevel` 之後改用 `bed_id`/`priority` 命名。
- **RoomDetail 頁**：進頁才建立 `/ws/room/{bed_id}` 連線，同時用收到的 offer/ice 建立 WebRTC PeerConnection 顯示影像；`active_events` 列表旁可以放「標記已處理」按鈕 → 呼叫 `POST /api/events/{event_id}/resolve`。

## 目前狀態

`backend/app/schemas.py`、`main.py`、`frontend/src/services/ws.js` 已依此契約補上函式/型別骨架（皆為 TODO body，尚未接上真實邏輯）。`Overview.jsx` / `RoomCard.jsx` 仍先用 `frontend/src/mock/rooms.js` 的假資料，等對應負責人把 TODO 補完再串接。

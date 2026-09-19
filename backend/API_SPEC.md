# Backend API Spec — 病房監測系統

> 依討論結果定案：板子 用 **MQTT** 送資料進 backend；Demo 準備 **4-6 間病房**（1間真實鏡頭+其他純模擬）；Event log 用**記憶體內的 list/dict**，不接資料庫。

---

## 1. 架構總覽

```
┌─────────────┐     MQTT      ┌──────────────────────────────────┐
│ B1 (板子)    │  publish      │  Backend (FastAPI)                │
│ 真實鏡頭房間  │ ───────────> │                                    │
└─────────────┘  ward/{bed_id}│  ┌──────────┐   ┌───────────────┐  │
                 /pose        │  │MQTT Client│──>│ Behavior Engine│ │
                               │  └──────────┘   │ + Ward Agent   │  │
┌─────────────┐               │                  └──────┬────────┘  │
│ Room Simulator│  直接函式呼叫 │                         │           │
│ (模擬房間，無  │ ───────────> │                         ▼           │
│  實體裝置)    │               │                  ┌──────────────┐  │
└─────────────┘               │                  │ Event Store   │  │
                               │                  │ (記憶體)       │  │
                               │                  └──────┬────────┘  │
                               │                         │           │
                               │  ┌──────────────┐        │           │
                               │  │ Vitals        │───────┤           │
                               │  │ Simulator     │       │           │
                               │  └──────────────┘        │           │
                               │                         ▼           │
                               │              REST API + WebSocket   │
                               └──────────────────┬──────────────────┘
                                                   │
                                                   ▼
                                              前端 Dashboard
```

**設計原則**：只有「真實鏡頭房間」的資料走 MQTT（因為它是實體板子，跟 backend 是分開的裝置，需要網路傳輸）。「模擬房間」沒有實體裝置，Room Simulator 直接在 backend 程式內部呼叫跟真實房間一樣的 Behavior Engine / Ward Agent 函式，不需要多繞一趟 MQTT，減少不必要的複雜度。兩條路徑最後都匯入同一個 Event Store，前端完全不用區分資料是真的還是模擬的。

---

## 2. MQTT

### Broker
本機跑 Mosquitto（`brew install mosquitto` 或用 Docker），預設 port `1883`，demo 期間跟前後端一樣開在 localhost 網路內。

### Topic 設計
```
ward/{bed_id}/pose
```
例如：`ward/B203-1/pose`

### Payload（B1 發布的訊息）
```json
{
  "timestamp": "2026-09-19T02:14:03Z",
  "bed_id": "B203-1",
  "keypoints": {
    "nose":            [0.51, 0.23, 0.92],
    "left_eye":        [0.49, 0.21, 0.88],
    "right_eye":       [0.53, 0.21, 0.88],
    "left_ear":        [0.46, 0.22, 0.70],
    "right_ear":       [0.56, 0.22, 0.70],
    "left_shoulder":   [0.43, 0.36, 0.95],
    "right_shoulder":  [0.57, 0.35, 0.95],
    "left_elbow":      [0.40, 0.48, 0.85],
    "right_elbow":     [0.60, 0.47, 0.85],
    "left_wrist":      [0.38, 0.58, 0.80],
    "right_wrist":     [0.62, 0.57, 0.80],
    "left_hip":        [0.46, 0.61, 0.90],
    "right_hip":       [0.55, 0.60, 0.90],
    "left_knee":       [0.47, 0.78, 0.88],
    "right_knee":      [0.54, 0.78, 0.88],
    "left_ankle":      [0.47, 0.94, 0.75],
    "right_ankle":     [0.54, 0.94, 0.75]
  }
}
```
每個關鍵點是 `[x, y, confidence]`，x/y 為 0~1 normalized 座標。

**負責人**：B1（板子端發布）+ B3（backend 訂閱端，訂閱 `ward/+/pose` 這個 wildcard topic 一次涵蓋所有真實房間）

---

## 3. REST API

三個 endpoint 都只回傳「目前狀態」的快照，前端在頁面載入的當下打一次，之後的即時更新一律交給 [WebSocket](#4-websocket-ws)。

### `GET /api/rooms`
回傳所有病房（真實+模擬）目前的狀態總覽，給 Dashboard 總覽頁用。

**Response** — `RoomsResponse`
```json
{
  "rooms": [
    {
      "bed_id": "B203-1",
      "patient_name": "王OO",
      "is_live": true,
      "risk_level": "normal",
      "last_updated": "2026-09-19T02:14:03Z"
    },
    {
      "bed_id": "B203-2",
      "patient_name": "陳OO",
      "is_live": false,
      "risk_level": "high",
      "last_updated": "2026-09-19T02:20:11Z"
    }
  ]
}
```

**`RoomSummary` 欄位**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `bed_id` | string | 床位識別碼，格式 `{房號}-{床號}`，例如 `B203-1` |
| `patient_name` | string | 病患姓名（demo 用假名） |
| `is_live` | boolean | 是否為真實鏡頭房間（前端可選擇顯示標記，不強制） |
| `risk_level` | `"normal" \| "warning" \| "high"` | 見下方「`risk_level` 怎麼算」 |
| `last_updated` | string (ISO 8601) | 這筆狀態最後一次更新的時間 |

---

### `GET /api/rooms/{bed_id}`
單一病房詳細資訊，給 RoomDetail 頁用。前端進頁面時先打這支拿一次完整快照，畫面先渲染出來，之後才建立 WebSocket 疊上增量更新（見第 5 節）。

**Response** — `RoomDetail`
```json
{
  "bed_id": "B203-1",
  "patient_name": "王OO",
  "is_live": true,
  "current_posture": "lying",
  "risk_level": "normal",
  "latest_keypoints": { /* 同 MQTT payload 的 keypoints 格式，模擬房間沒有真的骨架時為 null */ },
  "latest_vitals": {
    "bp_systolic": 132,
    "bp_diastolic": 85,
    "temperature": 36.7,
    "heart_rate": 78,
    "spo2": 97
  },
  "habit_baseline": {
    "usual_wake_time": "06:30",
    "usual_bathroom_duration_min": 3
  },
  "medical_orders": {
    "no_leg_raise": true
  }
}
```

**`RoomDetail` 欄位**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `bed_id`, `patient_name`, `is_live`, `risk_level` | 同 `RoomSummary` | |
| `current_posture` | `"standing" \| "sitting" \| "lying" \| "walking" \| null` | Behavior Engine 判斷出的目前姿勢，尚無資料時為 `null` |
| `latest_keypoints` | Keypoints \| null | 最新一幀關鍵點，模擬房間沒有真的骨架時為 `null` |
| `latest_vitals` | Vitals | 最新一筆生理數據 |
| `habit_baseline` | `{usual_wake_time: string, usual_bathroom_duration_min: number}` | 個人化習慣基準，demo 用固定假資料 |
| `medical_orders` | `{no_leg_raise: boolean}` | 醫囑限制旗標，demo 先只有這一個 |

**找不到 `bed_id` 時**：回傳 `404`，body 為 FastAPI 預設的 `{"detail": "Room not found"}`。

---

### `GET /api/rooms/{bed_id}/events`
事件歷史記錄（跌倒、離床、醫囑違規等），給 Dashboard 的事件列表用。

**Query params**：`limit`（預設 50，回傳最新的 N 筆，依 `timestamp` 由新到舊）

**Response** — `EventsResponse`
```json
{
  "events": [
    {
      "event_id": "evt_20260919_0220",
      "bed_id": "B203-1",
      "timestamp": "2026-09-19T02:20:11Z",
      "event": "POSSIBLE_FALL",
      "risk": "high",
      "reason": "偵測到跌倒姿勢，且該病患有跌倒病史，事發於凌晨時段",
      "priority": 1,
      "action": "立即通知當班護理師，同步記錄事件"
    }
  ]
}
```

**`EventEntry` 欄位**（同時也是第 4 節 WebSocket `risk_update` 的 `data` 格式）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `event_id` | string | 事件唯一識別碼，前端合併 REST/WebSocket 資料時的去重 key |
| `bed_id` | string | |
| `timestamp` | string (ISO 8601) | |
| `event` | string | `POSSIBLE_FALL` / `BED_EXIT` / `ABNORMAL_TRANSITION` 等，見 Behavior Engine |
| `risk` | `"normal" \| "warning" \| "high"` | 這一筆事件本身的風險等級 |
| `reason` | string | Ward Agent 產生的判斷理由（人類可讀） |
| `priority` | number | 數字越小越優先 |
| `action` | string | 建議動作（人類可讀） |

**找不到 `bed_id` 時**：回傳 `404`（同上）。`bed_id` 存在但還沒有任何事件時，回傳 `{"events": []}`。

---

### `risk_level` 怎麼算

`risk_level` **不是**獨立儲存、需要另外維護的欄位——risk 只屬於 event，不屬於 room。`risk_level` 是每次查詢時（REST 回應 / WS `room_status` 推播前）動態從 Event Store 算出來的：

- 取這個 `bed_id` 目前最新一筆事件的 `risk`
- 這個 `bed_id` 完全沒有任何事件時，`risk_level` 就是 `"normal"`

沒有另外的「目前風險狀態」需要覆寫或同步，也不會跟 Event Store 的內容不一致——單一事實來源永遠是 Event Store。

**負責人**：以上三個 REST endpoint 都是 B3

---

## 4. WebSocket `/ws`

單一連線，前端連上後持續收到推送訊息。所有訊息共用一個 envelope 格式，用 `type` 欄位區分種類：

```json
{
  "type": "pose_update" | "vitals_update" | "risk_update" | "room_status",
  "bed_id": "B203-1",
  "timestamp": "2026-09-19T02:14:03Z",
  "data": { /* 依 type 不同，內容不同，見下 */ }
}
```

| type | data 內容 | 推送頻率 | 誰觸發 |
|---|---|---|---|
| `pose_update` | 同 MQTT payload 的 `keypoints` | 每幀（約 10-15 fps，看板子效能） | B1 資料進來時 |
| `vitals_update` | `{bp_systolic, bp_diastolic, temperature, heart_rate, spo2}` | 心跳/血氧每 1-2 秒；血壓/體溫每 30 秒 | vitals_simulator 定時觸發 |
| `risk_update` | 同 `EventEntry` 格式（見第 3 節） | 事件發生時才推（不是定時） | Ward Agent 判斷出新事件時 |
| `room_status` | `{risk_level, current_posture}` | 狀態改變時 | Behavior Engine 狀態轉換時 |

前端收到訊息後，依 `bed_id` 分派到對應的房間 state 更新，不用每個房間開一條連線。

**負責人**：B3（WebSocket broadcast 邏輯），B2 的 Behavior Engine / Ward Agent 產生的結果由 B3 包成上面的格式送出

---

## 5. 前後端資料流慣例

這節是給 REST + WebSocket 兩邊都要遵守的整合規則，避免各自實作出不一致的行為。

### CORS / 連線方式
前端 Vite dev server（預設 `5173`）跟 backend（`8000`）是不同 origin。Backend 用 FastAPI `CORSMiddleware` 開放本機 origin，前端不用設 dev proxy。前端統一直接打絕對網址，風格對應 `services/ws.js` 現有的 `WS_URL` 常數：

```js
// services/api.js
const API_BASE_URL = "http://localhost:8000";
```

### 每頁的資料流：REST 拿快照、WebSocket 疊增量

- **Overview 頁**：掛載時打一次 `GET /api/rooms` 取得房間清單並渲染卡片；之後完全靠 WebSocket 的 `room_status`（更新單張卡片的 `risk_level`/`current_posture`）更新畫面，不額外輪詢 REST。
- **RoomDetail 頁**：掛載時打一次 `GET /api/rooms/{bed_id}` 拿完整快照（含 `latest_vitals`、`latest_keypoints`、`habit_baseline`、`medical_orders`）先渲染畫面，接著才建立 WebSocket 連線，用 `pose_update`/`vitals_update`/`risk_update`/`room_status` 疊上增量更新。`habit_baseline`/`medical_orders` 只有 REST 會給，WebSocket 不會推送這兩個欄位。

### 事件合併去重
`GET /api/rooms/{bed_id}/events` 拿到的歷史事件，跟之後 WebSocket `risk_update` 推播的新事件，前端要用同一份以 `event_id` 為 key 的資料結構管理（例如 Map）：REST 回來的批次先塞進去，`risk_update` 推入時若 `event_id` 已存在就略過，不存在才加入並依 `timestamp` 排序顯示。

### Loading / Error
Overview、RoomDetail 兩頁都要有基本的 loading 與 error 畫面（含 REST 404 的「查無此病房」），不做自動重試/backoff。

### 前端 HTTP 呼叫方式
不加 axios / react-query 等套件，統一用原生 `fetch()` 包一層薄薄的 service 函式（`getRooms()` / `getRoom(bedId)` / `getRoomEvents(bedId, limit)`），放在 `frontend/src/services/api.js`，風格對應現有 `services/ws.js` 的極簡寫法。

---

## 6. 模擬房間（Room Simulator）

**目的**：demo 用的另外 3-5 間房間沒有實體板子，需要有東西讓 Dashboard 看起來像「真的在監控多間病房」。

**做法**：一個背景排程任務，對每個模擬房間：
1. 定時（例如每 2-3 秒）產生一組假的 `keypoints`（可以是固定幾個預錄的姿勢座標輪流播放，不用即時運算生成）
2. 直接呼叫 `behavior_engine.classify_posture()` / `detect_events()`，跟真實房間走一樣的邏輯處理
3. 結果一樣送進 Event Store + WebSocket 廣播

**建議**：可以寫 1-2 個「劇本」（例如某間房間在 demo 過程中會固定在某個時間點觸發一次跌倒事件），讓 demo 現場有故事性，不是每間房永遠都正常。

**負責人**：B3（跟 vitals_simulator 一起，可以算是同一人負責的「模擬資料」大類）

---

## 7. 資料結構總覽（對應 `backend/app/schemas.py`）

`schemas.py` 需要兩類 schema，層次不同、不要混在一起：

**內部資料流 schema**（B1/B2/B3 之間互相溝通用，不是 REST response 的形狀）

| Schema | 用途 | 誰產生 |
|---|---|---|
| `Keypoints` | 17個關鍵點座標 | B1（真實）/ Room Simulator（模擬） |
| `BehaviorEvent` | 站/坐/躺/走/跌倒等狀態與事件 | B2 (behavior_engine) |
| `WardAgentOutput` | risk/reason/priority/action | B2 (ward_agent) |
| `Vitals` | 血壓/體溫/心跳/血氧 | B3 (vitals_simulator) |

**REST response schema**（給前端消費的 HTTP response 形狀，定義在第 3 節）

| Schema | 對應 endpoint |
|---|---|
| `RoomSummary` / `RoomsResponse` | `GET /api/rooms` |
| `RoomDetail` | `GET /api/rooms/{bed_id}` |
| `EventEntry` / `EventsResponse` | `GET /api/rooms/{bed_id}/events`（`EventEntry` 同時也是 WS `risk_update` 的 `data` 格式） |

**目前狀態**：兩類都還是 TODO 空殼，下一步是把這兩類 schema 的欄位實際填進 `schemas.py`，並且先用假資料建一個 in-memory 的「房間目前狀態」store（跟 Event Store 分開）撐起這三個 REST endpoint，不用等 B1/B2/vitals_simulator 的邏輯全部做完。

---


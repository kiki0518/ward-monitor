# 前後端 API 契約

補充 README 提到、但目前找不到的 `病房監測系統_Spec.md` 的前後端契約部分。Board 端姿勢推論/行為判斷內部格式不在這份文件範圍內，仍以 `schemas.py` 裡的 `Keypoints` / `BehaviorEvent` 為準（維持 TODO）。

## 現行 backend 整合狀態

病房 API 與 MJPEG 串流共用 `app.main:app`、同一個 lifespan 及 TCP 8000。
啟動時同時建立 camera 狀態、床位／事件資料與兩個背景模擬任務，關閉時取消並等待模擬任務結束。
所有狀態在記憶體內，部署只能使用單一 worker。

| 方法 | 現行串流端點 | 用途 |
| --- | --- | --- |
| WS | `/ws/camera/publish` | 單一板子發布 JPEG，使用 ready / ok ACK |
| WS | `/ws/camera/view` | 觀看者以 next 取得最新 JPEG 或 waiting / unchanged 狀態 |

詳細 wire format、大小限制、逾時及錯誤碼見 [streaming API spec](streaming/README.md#streaming-api-spec)。
這兩個端點與下方的病房端點同時有效，既有病房 JSON schema 不變。
目前是全系統單一 camera，沒有 `bed_id` 對應；不要把它當作每個床位各自的影像。

**WebRTC 已經不是這個專案在用的方案**，`schemas.py` 裡也沒有 `WebRTCSignal` 這個 class 了；`/ws/room/{bed_id}` 現在只做兩件事：`role=viewer`（預設）持續推送 state，`role=board` 接收 board 傳來的姿勢，兩者都跟影像無關。影像走下面的 JPEG relay，backend 不提供監看 HTML 頁（`GET /camera` 已移除），`VideoFeed.jsx` 已改接 `/ws/camera/view`。

## 資料流

```
                         ┌───────────────────────────┐
Board 姿勢推論           │                           │
   └─ current_posture ──▶│  Backend (FastAPI)         │
                         │  /ws/room/{bed_id}?role=board│
   vitals_simulator ─────▶  (backend 內部)             │
                         └─────────────┬─────────────┘
                                        │ posture 存進 state，跟著下一次 state 一起送
                                        ▼
                         ┌──────────────────────────────────────┐
                         │ GET  /api/beds                        │──▶ Overview 頁（載入一次）
                         │ WS   /ws/overview                     │──▶ Overview 頁（持續推送）
                         │ WS   /ws/room/{bed_id}（預設 role=viewer）│──▶ RoomDetail 頁（state）
                         │ POST /api/events/{event_id}/resolve   │◀── RoomDetail 頁（護理站標記已處理）
                         └──────────────────────────────────────┘

Board 攝影機/JPEG ─────▶ /ws/camera/publish ──▶ Backend（camera_stream.py，全域單一 camera，
                                                  不分 bed_id）──▶ /ws/camera/view ──▶ 瀏覽器
```

**影像傳輸走另一條獨立的全域 pipe**，不是 `/ws/room/{bed_id}`：board 用 binary WebSocket 把 JPEG 傳給 `/ws/camera/publish`，前端從 `/ws/camera/view` 拉取最新一張，protocol/backpressure 細節見 `streaming/README.md` 跟 `backend/app/camera_stream.py`。這條不分 `bed_id`——demo 只有一床（`bed_id = "101"`）有真的攝影機，這是前端/文件上的慣例，不是後端 schema 欄位，也沒有做 `bed_id` 範圍化（多鏡頭要支援時才需要）。

姿勢分類（站/坐/躺/舉手）由 board 算好，透過 `/ws/room/{bed_id}?role=board`（跟影像分開的另一條連線）傳給 backend，backend 只是存放/轉發，不自己做分類。

**跌倒判斷也是 board 自己做，不是 backend 從姿勢轉換速度去推斷**：board 判斷「這是疑似跌倒」之後，呼叫 `POST /api/beds/{bed_id}/possible-fall` 回報，backend 收到就直接建立/更新 `possible_fall` 事件，不重新驗證。這是離散事件（board 判斷出一次跌倒才呼叫一次），不是持續串流，所以走 REST 而不是 WebSocket，跟姿勢那條連線是分開的兩支。

## 端點

| 方法 | 路徑 | 用途 |
|---|---|---|
| GET | `/api/beds` | 一次性拉全部床位/病患靜態名冊 |
| GET | `/api/nurses` | 護理師名單（`assigned_nurse` 去重排序），給護理師身分選單用 |
| WS | `/ws/overview` | 全床摘要，持續推送（總覽頁用） |
| WS | `/ws/room/{bed_id}`（`?role=viewer`，預設值） | 單床 state（vitals+active_events+current_posture），詳細頁用，進頁才連線 |
| WS | `/ws/room/{bed_id}?role=board` | Board 端連線，上傳 `current_posture`（見下方 `BoardPostureUpdate`） |
| POST | `/api/beds/{bed_id}/possible-fall` | Board 端回報「疑似跌倒」（見下方 `PossibleFallReport`），board 自己判斷完才呼叫 |
| WS | `/ws/camera/publish` | Board（攝影機端）上傳 JPEG（binary），全域單一 camera |
| WS | `/ws/camera/view` | RoomDetail 頁拉取最新 JPEG（binary），全域單一 camera |
| GET | `/api/beds/{bed_id}/events` | 查該床目前 active 事件（不含已 resolved），見下方「事件生命週期」 |
| GET | `/api/beds/{bed_id}/events/history` | 查該床已處理事件紀錄（`resolved_at` 不為 `null`），見下方「事件歷史」 |
| POST | `/api/events/{event_id}/resolve` | 護理站標記事件已處理，body 附一份病例紀錄，見下方「病例紀錄與匯出報告」 |
| GET | `/api/reports/export` | 把目前累積的病例紀錄整理成 PDF 報告，直接回傳檔案下載，見下方「病例紀錄與匯出報告」 |

## Schema

### `BedInfo`（`GET /api/beds` 回傳陣列的元素）
```json
{
  "bed_id": "101",
  "patient_name": "王建國",
  "gender": "male",
  "age": 78,
  "diagnosis": "腦中風後遺症",
  "assigned_nurse": "王美玲"
}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `bed_id` | string | 床號，例如 `"101"`；全系統的床位識別碼，其他所有 schema 都用同一組值對應 |
| `patient_name` | string | 病患姓名 |
| `gender` | enum | `"male"` / `"female"` |
| `age` | int | 病患年齡 |
| `diagnosis` | string | 病因/診斷，人類可讀，例如「腦中風後遺症」「髖關節骨折術後」，demo 用固定假資料，見 `backend/app/data/beds.csv` |
| `assigned_nurse` | string \| null | 負責這張床的護理師姓名，demo 用固定假資料（一層樓一位護理師），見 `backend/app/data/beds.csv`；沒有指派時為 `null` |

### `OverviewUpdate`（`/ws/overview` 推送）
```json
[
  {
    "bed_id": "101",
    "priority": "green",
    "reason": "生理數據正常",
    "active_event_count": 0,
    "updated_at": "2026-09-19T14:32:10Z"
  },
  {
    "bed_id": "103",
    "priority": "red",
    "reason": "疑似跌倒",
    "active_event_count": 2,
    "updated_at": "2026-09-19T14:32:05Z"
  }
]
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `priority` | enum | `"green"`（正常）/ `"yellow"`（注意）/ `"red"`（高風險）。對應前端 `RoomCard` 的 `normal`/`warning`/`high`；取該床目前 active events 中優先度最高者，沒有 active event 時固定 `"green"` |
| `reason` | string | 人類可讀描述。有 active event 時填最高 priority 那個事件的 `reason`；沒有 active event 時固定「生理數據正常」 |
| `active_event_count` | int | 該床目前 active 事件總數（`resolved_at` 為 `null` 的筆數）。Overview 卡片只顯示最高 priority 那一筆的 `reason`，這個欄位讓卡片能額外提示「還有其他 N 個事件」，不用把整個 `active_events` 陣列塞進 Overview payload |
| `updated_at` | datetime (ISO 8601, UTC) | 例如 `"2026-09-19T14:32:10Z"`。有 active event 時是那筆事件的 `started_at`（異常從什麼時候開始），不是這次推送/計算摘要的時間；沒有 active event 時固定是查詢當下時間 |

### `WardAgentOutput`（事件，`RoomDetailUpdate.active_events` 的元素，也是 `resolve`/查詢的回傳值）
```json
{
  "event_id": "evt_20260919143150_a1b2",
  "bed_id": "103",
  "state": "possible_fall",
  "priority": "red",
  "reason": "疑似跌倒",
  "location": "out_of_bed",
  "action": "請護理師查看",
  "started_at": "2026-09-19T14:31:50Z",
  "last_seen_at": "2026-09-19T14:32:05Z",
  "resolved_at": null
}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `event_id` | string | 事件唯一識別碼，由 ward_agent 產生，格式 `evt_<started_at 的緊湊時間戳記>_<4碼隨機 hex>`（例如 `"evt_20260919143150_a1b2"`），方便從 ID 本身看出大概發生時間 |
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `state` | enum | `bed_exit`（離床）/ `possible_fall`（疑似跌倒）/ `abnormal_transition`（異常姿勢轉換）/ `prolonged_sitting`（長期坐著）/ `night_wandering`（離床過久）/ `medical_order_violation`（違反醫囑限制）/ `abnormal_vitals`（生理數據異常）/ `prolonged_bathroom`（如廁過久） |
| `priority` | enum | `"green"` / `"yellow"` / `"red"`，同 `OverviewUpdate.priority` |
| `reason` | string | 人類可讀描述，例如「夜間離床超過 5 分鐘」「疑似跌倒」 |
| `location` | enum | `in_bed`（床上）/ `out_of_bed`（離床）/ `chair`（椅子上）/ `near_door`（門邊）/ `bathroom`（浴廁） |
| `action` | string \| null | 建議動作文字，例如「請護理師查看」；沒有建議動作時為 `null` |
| `started_at` | datetime (ISO 8601, UTC) | 這個事件第一次被偵測到的時間，重複偵測到同一事件時不會變（見下方「事件生命週期」） |
| `last_seen_at` | datetime (ISO 8601, UTC) | 這個事件最近一次被重新偵測到的時間，跟 `started_at` 一起可以判斷「已經持續多久」跟「是不是還在發生」 |
| `resolved_at` | datetime \| null | 護理站按「標記已處理」的時間；`null` 代表事件仍 active。一張床可以同時有多個 `resolved_at` 為 `null` 的 active event |

### `ResolveReportRequest`（`POST /api/events/{event_id}/resolve` 的 request body）
```json
{
  "completed_actions": "協助病患回床並安撫情緒",
  "follow_up": "持續觀察生命徵象",
  "notes": "家屬在場陪同"
}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `completed_actions` | string | 護理站已完成的處理內容，必填 |
| `follow_up` | string | 需要交接給下一位人員的後續處理，必填（沒有的話傳空字串） |
| `notes` | string | 備註，選填，預設空字串 |

前端彈出的「標記已處理」表單對應這三個欄位；這支請求沒有這個 body 會被 FastAPI 擋下（422）。

### `CaseReport`（寫進 `case_reports.json` 的一筆紀錄，`GET /api/reports/export` 用來產生 PDF）
```json
{
  "event_id": "evt_20260919143150_a1b2",
  "bed_id": "103",
  "completed_actions": "協助病患回床並安撫情緒",
  "follow_up": "持續觀察生命徵象",
  "notes": "家屬在場陪同",
  "resolved_at": "2026-09-19T14:32:18Z"
}
```

`ResolveReportRequest` 補上 `event_id`/`bed_id`/`resolved_at` 就是這個 schema，這支不是任何端點的直接回傳值，只在 `case_reports.json` 裡以陣列形式存在。

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
| `bp_systolic` | int | 收縮壓，單位 mmHg。參考範圍約 `90–140`（`abnormal_vitals` 事件觸發的門檻由 ward_agent 決定，這裡只是 `vitals_simulator` 產生假資料時的合理區間，非強制驗證） |
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
  "active_events": [ "...WardAgentOutput 陣列..." ],
  "current_posture": "lying",
  "in_camera": true
}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `type` | const | 固定為 `"state"` |
| `bed_id` | string | 對應 `BedInfo.bed_id` |
| `ts` | datetime (ISO 8601, UTC) | 這筆狀態訊息的產生時間 |
| `vitals` | `Vitals` | 見上方 `Vitals` schema |
| `active_events` | `WardAgentOutput[]` | 目前所有 `resolved_at` 為 `null` 的事件；可以是空陣列（代表無事件） |
| `current_posture` | enum \| null | `standing`（站）/ `sitting`（坐）/ `lying`（躺）。由 board 直接算好傳過來（`streaming/movenet_pose.py` 的 `stable_pose`），backend 只是存放轉發；模擬房間、board 還沒送過資料、或 board 判斷為 `unknown`／`raising_hand` 時為 `null` |
| `in_camera` | boolean \| null | 畫面裡有沒有偵測到人，由 board 傳過來。`false` 代表沒偵測到人（`current_posture` 這時一定也是 `null`）；`true` + `current_posture: null` 代表有偵測到人但姿勢判斷不出來（`unknown`）。模擬房間、board 還沒送過資料時為 `null` |

### `BoardPostureUpdate`（board 連到 `/ws/room/{bed_id}?role=board` 上傳的訊息）
```json
{
  "ts": "2026-09-19T14:32:10Z",
  "in_camera": true,
  "current_posture": "lying"
}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `ts` | datetime (ISO 8601, UTC) | board 這筆姿勢判斷的時間 |
| `in_camera` | boolean（必填） | 同 `RoomDetailUpdate.in_camera`，但這裡是必填——沒送這個欄位 backend 會拒絕整筆訊息 |
| `current_posture` | enum \| null | 同 `RoomDetailUpdate.current_posture` 的列舉值 |

`bed_id` 不用放在訊息內容裡，已經在連線網址 `/ws/room/{bed_id}` 裡了。這條連線不傳影像——影像走 `/ws/camera/publish`，是完全獨立的另一條 pipe（見上方「資料流」）。

### `PossibleFallReport`（`POST /api/beds/{bed_id}/possible-fall` 的 request body）
```json
{ "ts": "2026-09-19T14:32:10Z" }
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `ts` | datetime (ISO 8601, UTC) | board 判斷出疑似跌倒的時間 |

`bed_id` 一樣不用放在 body 裡，已經在網址裡了。Response 是建立/更新後的 `WardAgentOutput`（`state: "possible_fall"`），跟 `GET /api/beds/{bed_id}/events` 回傳的元素格式相同。重複回報同一場跌倒（例如板子每隔幾秒重新確認一次還是跌倒）不會開出多筆事件——後端用既有的去重規則（同 `bed_id` + `state` 已有 active 事件就更新 `last_seen_at`，不開新的），board 端不用自己記得「這場跌倒有沒有回報過」。

### 攝影機串流（`/camera` 監看頁已移除、`/ws/camera/publish`、`/ws/camera/view`）

單一鏡頭的 JPEG frame relay，影像有經過 backend（`backend/app/camera_stream.py`），只支援單一 uvicorn worker（狀態存在記憶體裡，不能多 worker 部署）。跟上面的 JSON envelope 系列（`state`/`BoardPostureUpdate`）不同，這兩支是純 binary WebSocket，不是 `{type, bed_id, ...}` 格式，也不分 `bed_id`。

**`WS /ws/camera/publish`**（Board / 攝影機端連線）
- 連上後 server 先送文字 `"ready"`
- 之後每張畫面送一個 binary frame：必須是合法 JPEG（開頭 `\xFF\xD8`、結尾 `\xFF\xD9`），大小上限 2 MiB
- server 收到每張都回文字 `"ok"` 當 ack；publisher 應該等到 `"ok"` 才送下一張（避免積壓）
- 同時間只能有一個 publisher，第二個連線進來會直接被拒絕（close code `1008`）
- publisher 斷線時，backend 會清空目前存的 frame（避免 viewer 端看到過期畫面卻不知道來源已經斷了）

**`WS /ws/camera/view`**（RoomDetail 頁連線）
- 是 pull 模式：viewer 每次想要下一張畫面，就送文字 `"next"`
- server 收到 `"next"` 後回應二選一：
  - 有新畫面：直接回傳 binary frame（JPEG bytes）
  - 沒有新畫面：回傳 JSON `{"status": "waiting"}`（目前沒有 publisher，或超過 3 秒沒更新 → 視為 stale）或 `{"status": "unchanged"}`（有 publisher 但畫面跟上次拿到的一樣）
- 送的不是 `"next"` 的其他文字會被視為協定錯誤，直接關閉連線（`1008`）
- 前端要自己維護一個迴圈：收到一張（或 waiting/unchanged）後，馬上送下一個 `"next"`

完整協定細節、GStreamer pipeline、板子端指令見 `streaming/README.md`；backend 端實作在 `backend/app/camera_stream.py`。

## 事件生命週期

- **去重**：同一個 `(bed_id, state)` 如果已經有一筆 active（`resolved_at is None`）事件，不會再開一筆新的 `event_id`，而是更新既有那筆的 `reason`/`priority`/`location`/`last_seen_at`；`started_at` 保持不變。只有等既有那筆被 `resolve` 之後，同樣的 `(bed_id, state)` 再發生才會開新的一筆。`location` 不算在去重 key 裡，因為同一件事發展過程中 `location` 本來就可能改變（例如跌倒後從床邊移到房間中央），算進去會被誤判成新事件。
- **查詢**：`GET /api/beds/{bed_id}/events` 只回傳該床目前 active 的事件（`resolved_at is None`），**不含**已 resolved 的，bare array（`WardAgentOutput[]`），依 `priority` 高到低排序（`red` → `yellow` → `green`），同 priority 內新到舊，不分頁。找不到 `bed_id` 時回 `404`。這支本質上是 `active_events` 的 REST 版本（不用開 WebSocket 也能拿到目前 active 事件），不是完整事件歷史。
- **resolve 的 idempotency**：對一筆已經 resolved 的事件再打一次 `POST .../resolve`，直接回傳目前狀態、不報錯、也不會覆寫既有的 `resolved_at`（不是把它蓋成新的時間戳記）。前端不用先查詢目前狀態才敢呼叫。沒有「撤銷」功能——resolve 是單向操作，標記錯了目前無法復原。
- **不做的事**：resolved 事件永遠留著，不清除、不做 retention（單一 process、記憶體內、demo 用途，重啟就清空；真的要長期運行再處理）。
- **誤觸（前端行為，不是 API）**：`RoomDetail` 頁的「誤觸」按鈕純粹是前端把該 `event_id` 從畫面上濾掉，**不呼叫任何後端 API**、不改 `resolved_at`、也不進事件歷史。因為沒有寫回後端，這筆事件在 `store.py` 裡仍然是 active，下次 `ward_agent` 再判斷到同樣的 `(bed_id, state)` 時仍會沿用同一個 `event_id`（見上面「去重」規則）。

## 事件歷史

`GET /api/beds/{bed_id}/events/history` — 查該床所有透過 `resolve` 處理過的事件，給 RoomDetail 頁影像下方的「處理紀錄」用。

- **回傳格式**：跟 `GET /api/beds/{bed_id}/events` 一樣，bare array（`WardAgentOutput[]`）。依 `resolved_at` 新到舊排序，不分頁。找不到 `bed_id` 時回 `404`。
- **儲存方式**：後端把事件寫進一個 JSON 檔案（`backend/app/data/event_history.json`，已加進 `.gitignore`），**每次後端重新啟動時初始化（清空）這個檔案**——只記錄「這次執行期間」處理過的事件，不是跨重啟的永久紀錄，重啟後歷史會歸零。跟現有 `store.py` 的 in-memory 資料一樣是 demo 用途，不是真正的資料庫。
- **寫入時機**：`POST /api/events/{event_id}/resolve` 成功時 append 進 JSON 檔案。「誤觸」是純前端行為，不會寫進來。

## 病例紀錄與匯出報告

`POST /api/events/{event_id}/resolve` 現在**必須**帶 `ResolveReportRequest` body（見上方 schema）。前端在使用者按下「標記已處理」時彈出一個表單（已完成的處理／需要下一位處理／備註），填完按「確認」才會真的打這支 API；「取消」則什麼都不送。

- **儲存**：resolve 成功（第一次，非 idempotent 重複呼叫）時，除了原本寫進 `event_history.json`，同時把 `ResolveReportRequest` 補上 `event_id`/`bed_id`/`resolved_at` 組成 `CaseReport`，append 進 `backend/app/data/case_reports.json`（已加進 `.gitignore`）。跟 `event_history.json` 一樣**每次後端重新啟動就清空**，不是永久紀錄。
- **idempotency**：對已經 resolved 的事件再打一次 `resolve`（不論這次 body 內容是什麼），不會覆寫 `resolved_at`，也不會重複寫入 `case_reports.json`。

`GET /api/reports/export` — 把目前 `case_reports.json` 裡的所有紀錄整理成一份 PDF，直接以 `Content-Disposition: attachment` 回傳，前端收到後觸發瀏覽器下載，不分床位、不分頁面，回傳的是**全部**病例紀錄的彙整報告。

- **內容**：報告開頭有一段摘要文字，後面列出每筆病例的床號/事件 id/處理時間/三個欄位內容。
- **摘要目前是假資料**（`backend/app/report_generator.py` 的 `_summarize()`），先用固定模板文字撐住前後端流程；之後要接 LLM，只要把這個函式換成真正呼叫 LLM API（把 `case_reports` 序列化丟進去，回傳摘要文字）即可，其他部分不用動。
- **PDF 產生**：用 `fpdf2`（純 Python，不需要系統層級相依套件），中文字型內嵌 `backend/app/data/fonts/NotoSansTC-Regular.ttf`（Google Noto Sans TC，OFL 授權，已存進 repo）。
- 沒有任何病例紀錄時，PDF 仍會正常產生，摘要文字會說明「本次匯出範圍內沒有已處理的病例紀錄」。
- **匯出後會清空**：PDF 產生成功後，`case_reports.json` 會被清空（等於這批病例紀錄「已經匯出過」）。所以同一筆病例只會出現在**下一次**匯出的報告裡一次，不會被重複匯出；下次再打這支 API，範圍只會是「上次匯出之後新累積的病例」。`event_history.json`（RoomDetail 的「處理紀錄」）不受影響，不會被這支端點清空。

## 前端消費方式

- **Overview 頁**：載入時 `GET /api/beds` 拿名冊，之後靠 `/ws/overview` 的 `bed_id` 對應更新 priority/reason；`RoomCard` 的 `roomId`/`riskLevel` 之後改用 `bed_id`/`priority` 命名；頁面上的「匯出」按鈕呼叫 `GET /api/reports/export` 下載 PDF。
- **RoomDetail 頁**：進頁建立 `/ws/room/{bed_id}` 連線（不用帶 `role`，預設就是 viewer）拿 vitals/events/`current_posture`；**只有 `bed_id === "101"`** 時額外開一條 `/ws/camera/view` 連線，用「送 `next` → 收一張畫面或 waiting/unchanged」的迴圈把最新 JPEG frame 畫到畫面上（見上方「攝影機串流」），其他床沒有真實攝影機，不用連；`active_events` 列表每筆放「標記已處理」跟「誤觸」兩個按鈕——前者彈出表單，填完呼叫 `POST /api/events/{event_id}/resolve`（單向操作，沒有撤銷，會進處理紀錄），後者純前端濾掉、不打 API（見上面「誤觸」）；影像下方的「處理紀錄」呼叫 `GET /api/beds/{bed_id}/events/history` 顯示；頁面上也有「匯出」按鈕，跟 Overview 頁一樣呼叫 `GET /api/reports/export`。

## 目前狀態

- Backend（`schemas.py`/`store.py`/`simulator.py`/`main.py`）：`/api/beds`、`/ws/overview`、`/ws/room/{bed_id}`（`role=board` 上傳姿勢、`role=viewer` 推送 state+events+`current_posture`）、`/api/beds/{bed_id}/events`、`/api/beds/{bed_id}/events/history`、`/api/beds/{bed_id}/possible-fall`、`/api/events/{event_id}/resolve`（含病例紀錄）、`/api/reports/export` 都已實作，不是骨架。`current_posture`/`vitals`/事件目前由 `simulator.py` 的背景任務產生假資料（demo 用），board 接上之後直接把假資料來源換掉即可，介面不用動。
- `backend/app/camera_stream.py`：`/ws/camera/publish`、`/ws/camera/view` 已實作並整併進同一個 FastAPI app；`GET /camera` 監看頁跟 `camera.html` 已移除，backend 只提供串流 API。板子端 GStreamer/MoveNet 程式在 `streaming/`。
- `backend/app/report_generator.py`：PDF 產生已實作，**摘要文字是假資料**，待接 LLM（見「病例紀錄與匯出報告」）
- MoveNet 姿勢分類結果目前仍只輸出在板子終端，尚未透過 `/ws/room/{bed_id}?role=board` 或 `/api/beds/{bed_id}/possible-fall` 上傳給 backend（見 [`BOARD_API_SPEC.md`](./BOARD_API_SPEC.md)）。
- `frontend/src/components/VideoFeed.jsx`：已改接 `/ws/camera/view` 顯示 JPEG。
- `Overview.jsx` / `RoomCard.jsx` 仍先用 `frontend/src/mock/rooms.js` 的假資料，等對應負責人把 TODO 補完再串接。

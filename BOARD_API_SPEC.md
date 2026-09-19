# 板子 → Backend API Spec（姿勢 / 跌倒）

這份文件是給板子端（`streaming/`）看的：板子有什麼東西，就照這份規格傳給 backend。跟前端對接的完整契約在 [`API_CONTRACT.md`](./API_CONTRACT.md)。

影像（JPEG 串流）**不在這份文件範圍內**——那條已經是你們自己在 `streaming/README.md` 定案的協定（`/ws/camera/publish`），backend 這邊照那份實作好了，不用再對。這份只講姿勢推論的部分：`streaming/movenet_pose.py` 算出來的東西要怎麼送到 backend。

Demo 目前只有 **`bed_id = "101"`** 這一床接真的板子，其他床都是模擬。

---

## 兩支 API

| | 姿勢（持續性） | 疑似跌倒（離散事件） |
|---|---|---|
| 端點 | `ws://<server_ip>:8000/ws/room/101?role=board` | `POST http://<server_ip>:8000/api/beds/101/possible-fall` |
| 協定 | WebSocket，JSON 文字訊息 | HTTP REST，JSON body |
| 什麼時候呼叫 | 每次算出新的姿勢就送（持續性狀態更新） | **只有你們自己判斷出「這是跌倒」的時候**才呼叫（離散事件） |
| backend 收到後做什麼 | 存起來、轉發給前端顯示 | 建立/更新一筆跌倒事件，backend 不重新驗證 |

**跌倒判斷是板子端自己做**，backend 不會從姿勢轉換速度去反推「這像不像跌倒」——這件事完全交給板子那邊的邏輯決定，backend 只負責記錄板子已經下好的判斷。

---

## 1. 姿勢：`/ws/room/101?role=board`

連線建立後 backend 不會回覆任何東西（單向：你們送、backend 收）。連線斷了重新連上繼續送就好，backend 不會因為斷線做任何特殊處理。

### 訊息格式

```json
{
  "ts": "2026-09-19T14:32:10Z",
  "in_camera": true,
  "current_posture": "lying"
}
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `ts` | string，ISO 8601 UTC | 這筆姿勢判斷的時間 |
| `in_camera` | boolean（必填） | 畫面裡有沒有偵測到人，見下方說明 |
| `current_posture` | string 或 `null` | 見下方「值怎麼對應」 |

不用附 `bed_id`——已經在連線網址裡了。`in_camera` 是必填欄位，沒送這個欄位 backend 會拒絕整筆訊息（跟 `current_posture` 值不合法時一樣的行為）。

### `in_camera` 是什麼、跟 `current_posture: null` 有什麼不同

這兩種情況現在都可能讓 `current_posture` 是 `null`，但語意不一樣，前端會分開顯示（例如「無法判斷姿勢」vs「病患不在鏡頭前」），所以要分開講：

- **`in_camera: false`**：畫面裡完全沒偵測到人（房間空的、病患不在鏡頭範圍內）。這種情況下 `current_posture` 一定也是 `null`（沒有人就沒有姿勢可判斷）。
- **`in_camera: true` + `current_posture: null`**：有偵測到人，但姿勢判斷不出來（對應 `stable_pose == "unknown"`，例如角度不好、部分被遮擋）。

`classify_pose()` 現在沒有直接輸出「有沒有人」這個欄位，你們要自己決定怎麼從現有資料推：一個簡單做法是看 `keypoints` 裡所有關鍵點的 `score` 是不是都低於 `KEYPOINT_THRESHOLD`（完全沒有關鍵點超過信心閾值，大概率就是沒人），不用做到很精確，這個欄位主要是給「病患是不是離開房間太久」這類判斷用，抓大方向就好。

### 值怎麼對應

**用 `stable_pose`（多數決平滑過的值），不要用單幀的 `pose_class`**——`current_posture` 只是給前端顯示用的持續性狀態，不需要對單幀雜訊敏感；平滑過的值畫面比較不會閃爍。

| `stable_pose` 的值 | 送到 `current_posture` |
|---|---|
| `"standing"` | `"standing"` |
| `"sitting"` | `"sitting"` |
| `"lying"` | `"lying"` |
| `"unknown"` | `null`（**不要**送字串 `"unknown"`） |

`current_posture` 只接受這 4 個字串或 `null`，其他字串 backend 會拒絕整筆訊息。

### 多久送一次

沒有嚴格頻率要求——`stable_pose` 有更新就送，不用刻意降頻或增頻，也不用為了配合什麼即時性去改變你們原本的推論節奏。

---

## 2. 疑似跌倒：`POST /api/beds/101/possible-fall`

### Request

```json
{ "ts": "2026-09-19T14:32:10Z" }
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `ts` | string，ISO 8601 UTC |  BOARD 端判斷出疑似跌倒的時間 |

不用附 `bed_id`（在網址路徑裡）。`Content-Type: application/json`。

### Response

成功是 HTTP `200`，body 是建立好的事件：

```json
{
  "event_id": "evt_20260919143210_a1b2",
  "bed_id": "101",
  "state": "possible_fall",
  "priority": "red",
  "reason": "疑似跌倒",
  "location": "out_of_bed",
  "action": "請護理師查看",
  "started_at": "2026-09-19T14:32:10Z",
  "last_seen_at": "2026-09-19T14:32:10Z",
  "resolved_at": null
}
```

不用理會 response body 的內容，呼叫成功（HTTP 200）就代表 backend 收到了。

### 重複呼叫不用擔心

如果你們的邏輯是「持續判斷、只要還像跌倒就一直回報」，**直接每次都呼叫這支就好，不用自己記錄「這場跌倒有沒有回報過」**。backend 這邊有去重機制：同一床如果已經有一筆還沒被護理站標記處理的跌倒事件，重複呼叫只會更新那筆事件的時間戳記，不會開出好幾筆重複事件。等護理站在前端標記「已處理」之後，下一次回報才會開新的一筆。

### 最小 client 範例

```python
import requests
from datetime import datetime, timezone

def report_possible_fall(server_ip: str, bed_id: str = "101"):
    url = f"http://{server_ip}:8000/api/beds/{bed_id}/possible-fall"
    response = requests.post(url, json={
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    response.raise_for_status()
```

---
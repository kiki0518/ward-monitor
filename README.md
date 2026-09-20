# Ward Monitor — 梅竹黑客松病房監測系統

## 啟動方式

### Camera 即時監看實驗

單獨測試「開發板 camera → server → 瀏覽器」請看 [streaming/README.md](streaming/README.md)。
直接轉送 camera 輸出的 MJPEG，透過 WebSocket 傳至 FastAPI；觀看 API 為 `ws://SERVER_IP:8000/ws/camera/view`。
不需 H.264 編碼器、MediaMTX 或 React。請依 streaming 文件用單一 worker 啟動 backend。
若要同時跑 MoveNet，使用 `.venv-camera/bin/python streaming/movenet_test.py --server 192.168.31.248`；
預設 `/dev/video2`，同一鏡頭分成原始 JPEG 串流和板子姿勢推論兩路。

### 開啟開發板相機

先在電腦啟動下方的 Backend，並確認開發板與電腦位於可互通的同一個網路。
`SERVER_IP` 要填電腦的區網 IP，不能在開發板上填 `127.0.0.1`；例如電腦 IP 是
`10.28.50.69`，開發板就使用 `--server 10.28.50.69`。

```bash
.venv-camera/bin/python streaming/movenet_test.py --server 192.168.31.248
```

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 \
  --ws-max-size 2097152 --ws-max-queue 1 --ws-per-message-deflate false
```

同一個 FastAPI server 同時提供病房 REST / WebSocket、camera 上傳／觀看 API，
不需另開串流 backend。床位、模擬生理數據與最新影像均為記憶體狀態，請使用單一 worker。
React 的 `VideoFeed` 透過 `/ws/camera/view` 顯示 MJPEG；目前全系統只有一支 camera，
尚未建立床位與 camera 的對應。

後端回歸測試（在專案根目錄執行，需額外安裝 `httpx`）：

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 確認 Backend 是否正常運作

Backend 啟動後（預設 http://127.0.0.1:8000 ），對應 `API_CONTRACT.md` 的端點，有幾個方式可以確認：

**1. API 文件（REST 部分最直觀）**

瀏覽器打開 http://127.0.0.1:8000/docs ，FastAPI 會自動列出 `GET /api/beds`、`POST /api/events/{event_id}/resolve` 這兩支 REST endpoint，可以直接在網頁上「Try it out」測試（WebSocket 不會出現在這裡，見下方第 3 點）。

**2. curl 兩支 REST endpoint**
```bash
curl http://127.0.0.1:8000/api/beds
curl -i -X POST http://127.0.0.1:8000/api/events/nope/resolve   # 查不存在的 event_id，應該回 404
curl http://127.0.0.1:8000/api/beds/103/events  # 先取得目前 active event_id
# 再 POST /api/events/<實際 event_id>/resolve
```
預期結果（依 demo seed 資料，見 `backend/app/store.py`）：
- `/api/beds` 回傳 `backend/app/data/beds.csv` 內的床位
- 查不存在的 `event_id` 回 `404`
- 對查到的事件 ID 第一次呼叫 resolve 會成功，回傳的物件裡 `resolved_at` 從 `null` 變成有時間戳記

**3. WebSocket 用終端機測（curl 測不了）**

`backend/.venv` 已經有 `websockets` 套件（`uvicorn[standard]` 的依賴），不用額外安裝，直接跑：
```bash
cd backend && source .venv/bin/activate
python -c "
import asyncio, websockets

async def main():
    async with websockets.connect('ws://127.0.0.1:8000/ws/overview') as ws:
        for _ in range(3):
            print(await ws.recv())

asyncio.run(main())
"
```
預期每 2 秒印一次全床位的 `OverviewUpdate` 陣列，總共印 3 次然後結束。`103` 的 `priority` 應該是 `"red"`（除非已經被上面第 2 點 resolve 掉，那就會變回 `"green"`）。

把 `ws/overview` 換成 `ws/room/103` 就可以測單一床位那條，預期印出 `{type: "state", vitals: {...}, active_events: [...]}`。接不存在的床位（例如 `ws/room/nope`）應該直接被拒絕連線（`websockets.connect` 會丟出例外）。


**4. 看 terminal 有沒有錯誤**

`--reload` 模式下，任何一支 endpoint 出錯都會在啟動 uvicorn 的 terminal 印出完整 traceback，照著 traceback 最後幾行找出是哪個檔案哪一行壞的。

## Demo 手動觸發事件

1 樓（101~124）是刻意排除在隨機模擬之外的展示樓層，只有 101/102/103 這三床會有事件，其他樓層維持完全隨機，當 Overview 頁面的背景氣氛。

只有 101 有真的板子/攝影機，102、103 沒有真的感測器。三支腳本都是「先連到 101 床的即時姿勢資料（`/ws/room/101`）等偵測到指定動作，才觸發對應事件」，不是打開就馬上發，示範時要對著鏡頭實際做動作腳本才會動：

| 腳本 | 對應床 | 要對著鏡頭做的動作 | 偵測條件 |
|---|---|---|---|
| `trigger_fall.py` | 101 疑似跌倒 | 躺下 | `in_camera=true` 且 `current_posture=="lying"` |
| `trigger_empty_bed.py` | 102 空床 | 離開鏡頭範圍 | `in_camera=false` |
| `trigger_long_sitting.py` | 103 長時間維持坐姿 | 坐著 | `in_camera=true` 且 `current_posture=="sitting"` |

先確認 backend 有在跑、板子也連上 101 了，再開一個 terminal：

```bash
cd backend && source .venv/bin/activate

python scripts/trigger_fall.py          # 等偵測到躺下 -> 觸發 101 疑似跌倒
python scripts/trigger_empty_bed.py     # 等偵測到鏡頭前沒人 -> 觸發 102 空床
python scripts/trigger_long_sitting.py  # 等偵測到坐著 -> 觸發 103 長時間坐姿
```

每支會先印「等待偵測：...」卡住不動，直到在鏡頭前做出對應動作才會印出「觸發成功：XXX 床 XXX」跟完整的事件 JSON，前端馬上就能在 Overview／RoomDetail 看到；等待中可以 Ctrl+C 取消。重複觸發不會開出重複事件（backend 有去重機制，只會更新時間戳記）。這些事件不會自動消失，要在前端 RoomDetail 頁面點「標記已處理」才會清掉。

板子還沒連上時 `in_camera` 會一直是 `null`，三支腳本都會卡在「等待偵測」，這是預期行為。可以連 `ws/room/101` 看目前的 `in_camera`/`current_posture`（見上面「確認 Backend 是否正常運作」）確認板子有沒有連上、有沒有在送資料。

如果 server 不是跑在 `localhost:8000`，三支都接受一個可選參數，例如：

```bash
python scripts/trigger_fall.py http://192.168.1.100:8000
```

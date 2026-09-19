# Ward Monitor — 梅竹黑客松病房監測系統

## 啟動方式

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

## 確認 Backend 是否正常運作

Backend 啟動後（預設 http://127.0.0.1:8000 ），對應 `API_CONTRACT.md` 的四支 endpoint，有幾個方式可以確認：

**1. API 文件（REST 部分最直觀）**

瀏覽器打開 http://127.0.0.1:8000/docs ，FastAPI 會自動列出 `GET /api/beds`、`POST /api/events/{event_id}/resolve` 這兩支 REST endpoint，可以直接在網頁上「Try it out」測試（WebSocket 不會出現在這裡，見下方第 3 點）。

**2. curl 兩支 REST endpoint**
```bash
curl http://127.0.0.1:8000/api/beds
curl -i -X POST http://127.0.0.1:8000/api/events/nope/resolve   # 查不存在的 event_id，應該回 404
curl -X POST http://127.0.0.1:8000/api/events/evt_8f2a/resolve  # demo seed 資料裡的事件，應該成功並帶回 resolved_at
```
預期結果（依 demo seed 資料，見 `backend/app/store.py`）：
- `/api/beds` 回傳目前 seed 的 5 個床位（`101`~`105`）
- 查不存在的 `event_id` 回 `404`
- `evt_8f2a`（床位 `103` 的疑似跌倒事件）第一次呼叫會成功，回傳的物件裡 `resolved_at` 從 `null` 變成有時間戳記

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
預期每 2 秒印一次 5 個床位的 `OverviewUpdate` 陣列，總共印 3 次然後結束。`103` 的 `priority` 應該是 `"red"`（除非已經被上面第 2 點 resolve 掉，那就會變回 `"green"`）。

把 `ws/overview` 換成 `ws/room/103` 就可以測單一床位那條，預期印出 `{type: "state", vitals: {...}, active_events: [...]}`。接不存在的床位（例如 `ws/room/nope`）應該直接被拒絕連線（`websockets.connect` 會丟出例外）。


**4. 看 terminal 有沒有錯誤**

`--reload` 模式下，任何一支 endpoint 出錯都會在啟動 uvicorn 的 terminal 印出完整 traceback，照著 traceback 最後幾行找出是哪個檔案哪一行壞的。

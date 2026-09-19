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

Backend 啟動後（預設 http://127.0.0.1:8000 ），有幾個方式可以確認：

**1. API 文件（最直觀）**

瀏覽器打開 http://127.0.0.1:8000/docs ，FastAPI 會自動列出所有 REST endpoint，可以直接在網頁上「Try it out」測試。

**2. curl 三支 REST endpoint**
```bash
curl http://127.0.0.1:8000/api/rooms
curl http://127.0.0.1:8000/api/rooms/B203-2
curl http://127.0.0.1:8000/api/rooms/B203-2/events
curl -i http://127.0.0.1:8000/api/rooms/NOPE   # 查不存在的床號，應該回 404
```
預期結果（依 demo seed 資料，見 `backend/app/store.py`）：
- `/api/rooms` 回傳目前 seed 的所有房間
- `B203-2` 的 `risk_level` 是 `"high"`（seed 資料裡有一筆跌倒事件），其他房間是 `"normal"`
- `/api/rooms/B203-2/events` 有一筆 `POSSIBLE_FALL`
- 查不存在的床號回 `404`

**3. 看 terminal 有沒有 500 錯誤**

`--reload` 模式下，任何一支 endpoint 出錯都會在啟動 uvicorn 的 terminal 印出完整 traceback，照著 traceback 最後幾行找出是哪個檔案哪一行壞的。

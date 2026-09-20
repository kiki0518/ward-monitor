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

要使用「AI 交班紀錄」時，請改用 `bash scripts/start-backend.sh` 啟動（會自動載入 TAIDE 環境變數，見下方 [AI 交班紀錄](#ai-交班紀錄)）；直接跑上面的 `uvicorn` 不會載入，按「AI 整理」會回 503。

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

## AI 交班紀錄

原匯出按鈕改為「產生交班紀錄」：選取同一病人的處理紀錄、日期與班別，TAIDE 整理後可編輯「已完成的處理／需要下一位處理／備註」，按送出才儲存在處理紀錄下方。原始資料不清空，交班紀錄跨重啟保存。

模型尚未部署時，摘要會提示服務未啟用。輕量 TAIDE 模型、啟動方式與限制見 [部署說明](docs/HANDOVER.md)；環境變數範本在 [backend/taide.env.example](backend/taide.env.example)。

### 啟動流程（Intel Mac，本機 CPU 推論）

AI 的串接路徑：瀏覽器「AI 整理」→ 後端 `POST /api/beds/{bed_id}/handover-drafts` → 後端呼叫本機 `llama-server`（`http://127.0.0.1:8080/v1/chat/completions`）→ TAIDE GGUF 模型推論。瀏覽器不會直接連模型。

**第一次設定（只需做一次）**

1. 下載 TAIDE 的 GGUF 模型檔（Hugging Face 需先登入並接受條款，token 不要寫進專案），記下檔案的絕對路徑。
2. 安裝編譯工具並編譯 `llama-server`（需要 Git、CMake、Ninja、Apple Command Line Tools）：
   ```bash
   brew install cmake ninja
   bash scripts/build-llama.sh    # 產物在 .runtime/llama.cpp（已被 Git 忽略）
   ```
3. 建立 `backend/taide.env.local`（已被 Git 忽略），路徑一律用絕對路徑：
   ```bash
   export LLAMA_SERVER=/專案絕對路徑/.runtime/llama.cpp/build/bin/llama-server
   export TAIDE_MODEL_PATH=/絕對路徑/taide-7b-a.2-q4_k_m.gguf
   ```

**每次啟動（兩個終端，在專案根目錄）**

```bash
bash scripts/start-taide.sh      # 終端 A：模型服務，載入約 30 秒
bash scripts/start-backend.sh    # 終端 B：後端，自動載入 TAIDE 環境變數
```

模型服務就緒可用 `curl http://127.0.0.1:8080/health` 確認（回 200）。之後照上方 Frontend 啟動前端即可。CPU 推論一次摘要約 15–30 秒，按鈕停在處理中屬正常。

**驗證模型連線**（使用虛構資料，不寫入病例或交班紀錄）：

```bash
source backend/taide.env.example && source backend/taide.env.local
backend/venv/bin/python scripts/check-taide.py
```

**常見問題**

- 按「AI 整理」回 `503 AI 摘要服務尚未啟用`：後端沒有載入 `TAIDE_*` 環境變數。停掉後端，改用 `bash scripts/start-backend.sh` 重啟。
- 回 `502 TAIDE 連線失敗`：模型服務沒開，先執行 `bash scripts/start-taide.sh`。
- 回 `422 紀錄過長`：減少勾選的處理紀錄筆數。
- `start-taide.sh` 說找不到 llama-server 或模型：檢查 `backend/taide.env.local` 的路徑是否為絕對路徑且檔案存在。
- `start-backend.sh` 沒有 `--reload`，修改後端程式碼後要手動重啟。

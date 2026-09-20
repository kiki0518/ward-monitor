# AI 交班紀錄

流程：在總覽選病人，或從病床詳情點「產生交班紀錄」→ 選日期、班別與處理紀錄 → AI 整理 → 人工編輯三個欄位 → 送出。已送出的內容顯示在病床詳情「處理紀錄」下方的「交班紀錄」。原 PDF 匯出 API 已移除。

日期與白班／小夜班／大夜班是交班標籤，不自動推算跨午夜的來源時間範圍。預設選取尚未包含在已送出交班紀錄的來源；可手動重選曾交班的紀錄。未解除警示與系統自動解除事件不作為護理處理紀錄。follow_up 是待追蹤文字，模型不得推論已完成。

## 輕量 TAIDE 部署

起點選用官方 [TAIDE-LX-7B-Chat-4bit](https://huggingface.co/taide/TAIDE-LX-7B-Chat-4bit)：7B、4-bit、4K context，官方模型卡列有自動摘要能力。這是相對 12B 模型較輕的選擇，仍須在目標硬體驗證延遲與摘要品質。下載模型前，需要使用者登入 Hugging Face 並接受該模型的存取條款。

1. 從 [llama.cpp 官方 releases](https://github.com/ggml-org/llama.cpp/releases) 安裝符合目標電腦的 llama-server。
2. 在官方模型頁完成存取流程，下載 GGUF。不要把 Hugging Face token 寫進儲存庫。
3. 啟動推論服務（替換實際模型路徑）：

```sh
llama-server -m /absolute/path/to/taide-4bit.gguf --alias taide-handover --host 127.0.0.1 --port 8080 -c 4096
```

4. 從專案根目錄啟動後端：

```sh
source backend/taide.env.example
cd backend
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`TAIDE_API_BASE` 必須包含 `/v1`；後端呼叫 `/chat/completions`，也能換成其他提供相同協定的 TAIDE 推論服務。金鑰使用 `TAIDE_API_KEY`，只留在後端環境。參考 [llama-server 文件](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)。

未設定模型時回 503；連線逾時、截斷或無效 JSON 回 502，不產生假摘要。單次連線逾時 120 秒。輸入超過 `TAIDE_MAX_INPUT_BYTES` 時回 422，提示減少選取紀錄，不靜默截斷。預設 5000 bytes 是保守大小限制，並非精確 token 計數；context 不足仍可能由模型服務拒絕，須依模型調整。輸出預設 1024 tokens。這版不自動分段摘要。

## Intel Mac 安裝腳本沒有預編譯版本時

若 `llama.app/install.sh` 顯示沒有可用的預編譯版本，可從官方原始碼建立 CPU 版本：

```sh
bash scripts/build-llama.sh
```

腳本固定使用官方 `b11057`，需要 Git、CMake、Ninja 與 Apple Command Line Tools。下載和編譯產物都在 Git 忽略的 `.runtime/llama.cpp`，不安裝到系統目錄，也不變更 macOS 安全設定。此設定關閉 Metal，保留 CPU／Accelerate 支援。

建立 `backend/taide.env.local`（已被 Git 忽略），指定 `LLAMA_SERVER` 為編譯完成的 `.runtime/llama.cpp/build/bin/llama-server` 絕對路徑，`TAIDE_MODEL_PATH` 為已下載的 GGUF 絕對路徑。分別在兩個終端啟動：

```sh
bash scripts/start-taide.sh
bash scripts/start-backend.sh
```

已有後端占用 8000 時，先在原來終端停止舊後端，再透過上述腳本啟動，使模型設定生效。服務啟動後，可用虛構資料檢查摘要，這個檢查不寫入病例或交班紀錄：

```sh
source backend/taide.env.local
.venv/bin/python scripts/check-taide.py
```

## 儲存與限制

- `case_reports.json` 保存原始護理處理紀錄，改為重新啟動不清空；寫入使用鎖與原子替換（目前單一後端 process）。
- `handover.sqlite3` 保存 AI 草稿、來源快照與人工送出的內容，提交在 SQLite 交易中完成。相同草稿重送會回傳第一次的結果，避免重複新增。
- 取消編輯不新增正式交班紀錄，未送出草稿不顯示在清單。草稿仍保留在本機資料庫，這版沒有草稿恢復或清理 UI。
- 日期與班別可以在編輯時修改。送出後為唯讀。
- 只把處理時間與三個文字欄位傳給模型，不主動附姓名／床號；自由文字若含姓名仍會包含在請求中。
- 目前名冊沒有病人／住院 ID，以床號加紀錄時的姓名隔離。換床或同床同名的不同住院尚無完整身分追蹤，正式使用前需接住院 ID。
- 舊版紀錄沒有姓名快照，保留原檔，但不自動指派給目前住床的人，也不列入可摘要來源。
- 原有即時事件的模擬狀態仍在重啟時重設；人工處理文字與交班紀錄持續保存。
- 不同草稿可重複選取來源，用於修正或重新交班；不限制同日同班只能一份。

## 驗證

```sh
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run build
npm run lint
```

測試使用隔離的臨時資料檔與模擬模型 HTTP 回應，不代表已完成真實 TAIDE 摘要品質驗證。真機驗收：建立兩筆處理紀錄 → 摘要 → 修改 → 送出 → 重整及重啟 → 確認交班內容與原始紀錄都保留。

瀏覽器操作測試：先啟動 Vite，安裝 Playwright 與其 Chromium 後執行 `node frontend/tests/handover.e2e.cjs`。此測試攔截 API，使用隔離的假模型回應及暫存紀錄，涵蓋編輯、提交失敗重試、重整、取消、舊來源重選與模型未啟用。`FRONTEND_URL` 可指定病床頁網址，`PLAYWRIGHT_CHROMIUM_EXECUTABLE` 可指定現有 Chromium。截圖輸出到系統暫存目錄。

本機編譯驗證：Intel x86_64、macOS 14.3.1、AppleClang 15，官方 b11057（59657a6）已成功建立，`llama-server --version` 可正常執行。未嵌入 llama.cpp 示範網頁；本專案使用既有前端與模型 API。尚未下載模型，因此未完成真實摘要驗證。

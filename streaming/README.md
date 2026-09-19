# MJPEG 即時監看

## 架構與規劃

C270 → GStreamer V4L2（image/jpeg）→ WebSocket 二進位 JPEG → FastAPI → 瀏覽器。
鏡頭模式直接複製原有 JPEG bytes，不解碼、不重新編碼、不需要 H.264 編碼器。
本階段只有單台 camera 即時觀看，不做推論、音訊或錄影。沿用 feat/camera-live-preview。

- 板子 appsink 只留最新一張，滿了丟舊圖；收到 server ACK 才取下一張。
- Server 只存最新一張，每個觀看者顯示完才要求下一張，慢的觀看者不阻塞發布者。
- 瀏覽器解碼後再請求，釋放每張 Blob URL；斷線會自動重連，3 秒沒新圖會隱藏舊畫面。
- 網路仍有一張在途影像，不能撤回已進入 TCP 的 bytes；網路慢時會降低有效 FPS。
- 預設 640×480、15 FPS。若每張 50 KB，約 6 Mbps（未含協定開銷）。

## Server（電腦）

在專案根目錄：

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 \
  --workers 1 --ws-max-size 2097152 --ws-max-queue 1 --ws-per-message-deflate false
```

只開 TCP 8000。此實驗使用記憶體內的單一 camera 狀態，**只能一個 worker**；
多 worker 必須先加入跨程序影像共享。此區網實驗沒有帳密，勿直接暴露到網際網路。

觀看網址：`http://SERVER_IP:8000/camera`。電腦本機可用 `http://localhost:8000/camera`。
不用啟動 React、Docker 或 MediaMTX，原本 `:8889/camera` 已停用。
若之前自行啟動 MediaMTX 容器，請先用原 Compose 設定停止它；本版已移除舊設定。

## 板子：確認 MJPEG 與依賴

需 Python 3.9+、GStreamer 1.x、Python GI（PyGObject）、Gst introspection、
`v4l2src`、`appsink`、websockets 14～15。Ubuntu / Debian 範例：

```bash
sudo apt-get install python3-gi python3-venv gir1.2-gstreamer-1.0 \
  gir1.2-gst-plugins-base-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-base v4l-utils
python3 -m venv --system-site-packages .venv-camera
.venv-camera/bin/pip install -r streaming/requirements.txt
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

Yocto / NXP BSP 請用對應映像套件或建置配方加入上述依賴，不能直接使用 apt。
`--system-site-packages` 讓 venv 能讀取 OS 提供的 `gi`。
確認選中的 camera node 提供 MJPG，且支援指定解析度及 FPS；不要選到 metadata node。

## 推流

在板子上，專案根目錄執行（也可只複製 streaming 資料夾）：

```bash
.venv-camera/bin/python streaming/publish_camera.py --server 192.168.1.100 \
  --device /dev/video0 --width 640 --height 480 --fps 15
```

把 IP 換成電腦的區網 IP。支援 `--port`，預設 8000。
板子與 server 可以透過 Wi-Fi 或 Ethernet 互通，不必用 USB 相連，但板子需獨立供電。
Ctrl+C 停止。網路中斷自動每 2 秒重試；鏡頭錯誤或 server 拒絕發布則退出並印出原因。
同時只允許一個發布者；先關掉占用 camera 的其他程式。

### 無實體鏡頭測試

在有 GStreamer / GI 的電腦或板子上：

```bash
.venv-camera/bin/python streaming/publish_camera.py --server 192.168.1.100 --source test
```

test 模式才使用 `videotestsrc ! jpegenc` 產生 JPEG 動畫；實際 camera 模式沒有 jpegenc。
`--dry-run` 只列印 pipeline，不開鏡頭，不需要 GI 或 websockets。

<<<<<<< Updated upstream
## 協定
=======
## 同時啟動 MoveNet 與串流

在板子上使用原本已能跑 MoveNet 的 Python 環境，並確保該環境也有 GI / GStreamer 和
`streaming/requirements.txt` 的 websockets。需沿用板子的 `numpy`、OpenCV (`cv2`)、
`tflite_runtime` 和 Ethos-U delegate；不要用一般桌面 TensorFlow 取代 NXP runtime。

從專案根目錄啟動：

```bash
python3 streaming/movenet_test.py --server 192.168.1.100
```

整合入口預設 `/dev/video2`（對齊你提供的原始程式）、640×480、15 FPS。
請先用 `v4l2-ctl -d /dev/video2 --list-formats-ext` 確認這個節點能輸出對應的 MJPG。
可用 `--device /dev/video0` 更換攝影機節點，`--width`、`--height`、`--fps` 調整格式。
同樣功能也能透過原串流入口開啟：

```bash
python3 streaming/publish_camera.py --server 192.168.1.100 --device /dev/video2 --pose
```

一般 `publish_camera.py` 不加 `--pose` 時仍只推流，不載入 OpenCV、NumPy 或 NPU 模型。
`movenet_test.py` 和 `publish_camera.py --pose` 是兩種入口，**擇一執行**。

```text
C270 /dev/video2 → image/jpeg → tee
                                ├─ leaky queue → appsink → JPEG WebSocket → FastAPI
                                └─ leaky queue → appsink → 解 JPEG → MoveNet / Ethos-U
```

預設模型與 delegate 沿用原程式：

- `/opt/gopoint-apps/downloads/movenet_quant_vela.tflite`
- `/usr/lib/libethosu_delegate.so`

可用 `--model /path/model.tflite --delegate /path/libethosu_delegate.so` 覆寫。
`--pose-print-interval 1` 控制終端輸出間隔（秒），不限制推論取樣速率。
啟動後應看到模型資訊、`MoveNet branch started`，以及 `Connected. Watch ...`。
即使 server 尚未啟動，也會先在板子終端看到推論輸出。

保留提供程式的 17 點座標、信心閾值 0.20、身體中心正規化、站／坐／躺／舉手判斷，
以及最近 5 次推論的多數決平滑（忽略 unknown）。也保留原本 uint8 / int8 / float32
輸入處理和輸出反量化。`movenet_pose.py` 負責這些邏輯，不再呼叫 `cv2.VideoCapture`。
推論縮放方式沿用原程式，未另外引入 letterbox 或調整分類閾值。

姿勢結果仍印在板子終端，server `/camera` 顯示未疊圖影像；本次未新增姿勢 JSON 上傳或骨架疊圖。
兩路各自丟掉舊圖，因此不保證每張傳輸影像都有同一張的推論結果。
之後若要在網頁疊骨架，需再加入 frame ID / timestamp 同步協定。

模型／delegate 載入失敗會在開鏡頭前退出。執行途中推論出錯會印出 `MoveNet stopped`，
監看繼續；重啟整合程式可恢復推論。Ctrl+C 會停止 pipeline 並通知推論執行緒退出；
若 NPU invoke 卡住，最多等待 5 秒並提示。獨立執行緒仍共用板子的 CPU / 記憶體頻寬，
需在板子實測 JPEG 解碼與 NPU 的吞吐量，無法保證推論對影像 FPS 完全沒有影響。

### 整合驗收

1. 終端持續出現 Raw / Stable / Base pose、舉手狀態與關鍵點；網頁同時顯示原始画面。
2. 停止 server：板子應持續推論並重試串流；重新啟動 server 後恢復監看。
3. 確认沒有第二個 VideoCapture 程式占用鏡頭，畫面延遲不隨時間累積。
4. Ctrl+C 停止後，再次啟動可重新取得 camera。

不需 GI / NPU 的本機回歸測試（需要 NumPy、OpenCV）：

```bash
python3 -m unittest discover -s streaming/tests -v
```

測試包含 JPEG bytes 保留、RGB / 量化處理、姿勢規則、慢推論丟舊圖、
以及模擬網路／推論互不等待。這些是單元測試，並不取代板子的 camera、GStreamer tee 與 NPU 實機測試。

## Streaming API 
>>>>>>> Stashed changes

### 資料流

```text
C270（MJPEG）→ Board 上唯一的 V4L2 capture → tee
                                                ├─ 獨立 queue / appsink
                                                │    └─ 原始 JPEG bytes
                                                │           │
                                                │           ▼
                                                │  WS /ws/camera/publish
                                                │           │
                                                │     FastAPI 最新影像槽
                                                │           │
                                                │  WS /ws/camera/view
                                                │           │
                                                │           ▼
                                                │  瀏覽器 /camera 監看頁
                                                │
                                                └─ 獨立 queue / appsink
                                                     └─ 解 JPEG → MoveNet / Ethos-U
                                                                  └─ 板子終端輸出
```

- 監看路徑不解碼、不重新編碼、不疊骨架；一則 binary WebSocket message 就是一張完整 JPEG。
- MoveNet 路徑才解 JPEG；推論結果目前只印在板子終端，不上傳到本串流 API。
- 兩路各自消費最新資料，不保證每張監看影像都有同張推論結果。
- 這裡的 MJPEG 指連續 JPEG 影像；不是 HTTP `multipart/x-mixed-replace`，也不是 MP4 / RTSP。

### 端點

以下以 `SERVER_IP:8000` 為例；`SERVER_IP` 為板子與觀看端都能連到的電腦區網 IP。

| 方法 | 路徑 | 連線方 / 用途 |
|---|---|---|
| GET | `/` | 健康檢查，回傳 `HealthResponse`；不代表 camera 已連線 |
| GET | `/camera` | 瀏覽器載入 HTML 監看頁，頁面再建立觀看 WebSocket |
| WS | `/ws/camera/publish` | Board 上傳完整 JPEG；server 回覆握手與 ACK |
| WS | `/ws/camera/view` | 瀏覽器要求下一張最新 JPEG，或取得等待狀態 |

- HTTP base URL：`http://SERVER_IP:8000`；WebSocket base URL：`ws://SERVER_IP:8000`。
- 不需要 query parameters、request body、Authorization header 或 WebSocket subprotocol。
- `/camera` 回應 `200`、`Content-Type: text/html`、`Cache-Control: no-store`。
- 不提供 `camera_id`、`bed_id`、`room_id`；整個 server process 只有一個 camera 影像槽。
- 若部署 HTTPS 反向代理，內建監看頁會跟隨頁面協定使用 `wss://`；板子腳本目前固定使用 `ws://`，沒有 TLS CLI 選項。
- 舊 `/ws` 仍是占位端點，連線後立即關閉，不用於本串流功能。

### Schema

下列 Schema 名稱是文件上的訊息名稱，**不會作為 `type` 欄位傳送**。
除了觀看狀態外，控制訊息皆為區分大小寫的純文字；不要加 JSON 引號、換行或額外空白。

#### `HealthResponse`（`GET /`）

```json
{"status": "ok"}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `status` | string | 固定 `"ok"`，只表示 HTTP handler 可回應 |

#### `PublisherReady`（server → Board，text message）

```text
ready
```

| 項目 | 型別 | 可能值 / 說明 |
|---|---|---|
| message payload | UTF-8 text | 固定 `ready`；server 接受該連線為唯一發布者後傳送一次 |

Board 必須等到 `ready` 才開始送圖。第二個發布者會被關閉，不會收到 `ready`。

#### `CameraFrame`（Board → server，以及 server → 瀏覽器，binary message）

```text
FF D8 ... JPEG encoded bytes ... FF D9
```

| 項目 | 型別 | 可能值 / 說明 |
|---|---|---|
| message payload | bytes | 一張完整 JPEG；不包 JSON、不做 Base64、不加自訂封包頭 |
| payload 長度 | byte count | 至少 4 bytes，最多 2,097,152 bytes（2 MiB），包含 JPEG 頭尾 |
| 開頭 | bytes | 必須為 `FF D8` |
| 結尾 | bytes | 必須為 `FF D9` |
| 解析度 | JPEG 內嵌資訊 | server 不限定尺寸；板子預設 640×480，瀏覽器解碼後取得寬高 |
| FPS | 無傳輸欄位 | 板子預設擷取 15 FPS；實際顯示速率由擷取、網路和觀看端速度決定 |

每張圖以一則 WebSocket **message** 為邊界，不是以 TCP read 次數切圖。
不得把 JPEG 切成多則應用訊息，也不得在一則訊息內串接多張圖片。
WebSocket 傳輸層自行分片不改變這個應用層契約。

server 只檢查大小與 JPEG 頭尾，不驗證完整編碼內容。
因此通過檢查不代表瀏覽器一定能解碼；觀看頁解碼失敗會顯示錯誤並繼續要求新圖。
`frame_id`、timestamp、尺寸、bed ID、keypoints 都沒有額外附在封包中；
server 內部的 sequence 與接收時間也不對外傳送。

#### `PublisherAck`（server → Board，text message）

```text
ok
```

| 項目 | 型別 | 可能值 / 說明 |
|---|---|---|
| message payload | UTF-8 text | 固定 `ok`；JPEG 通過檢查並寫入最新影像槽後回覆 |

ACK 僅表示 server 已接收，**不表示任何瀏覽器已顯示，也不表示影像已存檔**。
Board 一次只應有一張尚未 ACK 的影像；收到 ACK 才取下一張最新 JPEG。

#### `NextFrameRequest`（瀏覽器 → server，text message）

```text
next
```

| 項目 | 型別 | 可能值 / 說明 |
|---|---|---|
| message payload | UTF-8 text | 固定 `next`；要求比該觀看者上次回應更新的影像 |

連線後 server 不會主動送圖；觀看端必須先送 `next`。
每個觀看者最多保留一個未完成請求，收到／處理完回應才再送 `next`。
不要使用固定計時器持續灌入請求，server 不會幫忙合併排隊的 `next`。

#### `CameraViewStatus`（server → 瀏覽器，text message，內容為 JSON）

```json
{"status": "waiting"}
```

或：

```json
{"status": "unchanged"}
```

| 欄位 | 型別 | 可能值 / 說明 |
|---|---|---|
| `status` | enum | `"waiting"`：沒有可用新鮮影像；`"unchanged"`：仍有未過期的影像，但沒有比該觀看者上次回應更新的影像 |

- `waiting` 包括尚未收到第一張、發布者斷線，或最後影像已過期；沒有更細的原因欄位。
- `unchanged` 不附帶圖片；前端可暫時保留已顯示畫面。
- 收到這兩種狀態後，觀看端均可再次送 `next`。
- binary message 直接當 JPEG 處理，只有 text message 才交給 `JSON.parse`。

### 串流生命週期

#### Board 發布

```text
Board                           Server
  │──── WebSocket connect ───────→│
  │←─── text: ready ──────────────│
  │──── binary: JPEG A ──────────→│ 取代最新影像
  │←─── text: ok ─────────────────│
  │ 取最新 JPEG（跳過舊圖）        │
  │──── binary: JPEG B ──────────→│ 取代最新影像
  │←─── text: ok ─────────────────│
```

- **發布者唯一性**：同時只有一個發布者；新連線不會搶走現有 camera。
- **最新影像覆寫**：每次成功接收替換前一張，不保存歷史、不保證每張都被觀看。
- **發布者離線**：server 清除影像，喚醒等待中的觀看請求；重連後重新執行 `ready` 握手。
- **重送**：沒有 frame ID 或去重協定；ACK 遺失後重連取新圖，不補送歷史。

#### 瀏覽器觀看

```text
Browser                         Server
  │──── WebSocket connect ───────→│
  │──── text: next ──────────────→│
  │←─── binary: 最新 JPEG ────────│
  │ 解碼、顯示、釋放 Blob URL      │
  │──── text: next ──────────────→│ 等待更新（最多約 1 秒）
  │←─── 新 JPEG 或 status JSON ───│
```

- **多觀看者**：各連線獨立記錄進度，共用最新影像槽；慢的觀看者跳過舊圖，不阻塞發布者。
- **新連線**：若已有未過期 JPEG，第一次 `next` 可立即取得。
- **過期判斷**：依 server 的 monotonic 接收時間計算；影像年齡 `< 3 秒` 才有效。
  這不是攝影機拍攝時間，無法單靠此欄位衡量端到端延遲。
- **無新圖**：一次請求最多等待約 1 秒，之後依影像是否仍新鮮回覆 `unchanged` 或 `waiting`。
  發布者不存在時可以立即回 `waiting`，server 每次回應後約暫停 0.2 秒以限制空轉。

#### 超時與重新連線

| 位置 | 時間 / 行為 | 說明 |
|---|---|---|
| server 等發布者下一則訊息 | 10 秒 | 超時關閉並清空影像 |
| server 傳發布 ACK | 5 秒 | 發送超時則結束發布連線 |
| server 等觀看者 `next` | 30 秒 | 超時關閉該觀看連線 |
| server 等新影像 | 最多約 1 秒 | 超時回狀態，不因此關閉連線 |
| server 傳 JPEG 給觀看者 | 5 秒 | 發送超時則結束該觀看連線 |
| 板子開啟連線 / 等 `ready` / 等 `ok` | 各 5 秒 | 現有腳本對連線錯誤或超時等待 2 秒後重試 |
| 內建監看頁斷線 | 2 秒後重連 | 建立新連線後重新送 `next` |
| 內建監看頁無新圖 | 超過 3 秒 | 約每秒檢查一次並隱藏舊圖；收到 `waiting` 時也隱藏 |

`1003`、`1008`、`1009` 代表發布端輸入或狀態不合規，現有板子腳本會退出，
不無限重試；排除原因後重新啟動。一般網路中斷才走重連流程。
板子相機取樣連續 5 秒無資料（已連上 server 時檢查）、camera ERROR/EOS 或模型啟動失敗，
屬於本地錯誤，沒有對應的 server JSON error payload。

### 錯誤與關閉碼

錯誤使用 WebSocket close frame，不使用 HTTP JSON error schema。

| Code | 端點 | 觸發條件 | 應用層 reason |
|---|---|---|---|
| `1008` | publish | 已有發布者 | `A camera is already publishing` |
| `1009` | publish | 收到 text 而非 binary，或長度小於 4 / 大於 2 MiB | `Expected JPEG bytes, maximum 2 MiB` |
| `1003` | publish | JPEG 頭尾標記不符 | `Invalid JPEG envelope` |
| `1008` | view | 收到的 text 不等於 `next` | `Expected next` |

- 若 Uvicorn 傳輸層先擋下超大訊息，也可能收到 `1009`，reason 不一定等於上表應用層字串。
- 觀看端只接受 text `next`；目前沒有替「觀看端送 binary」定義穩定的關閉碼，請勿依賴其錯誤行為。
- 超時路徑沒有獨立業務錯誤碼；正常的應用層 close 預設 `1000`，網路異常也可能表現為非正常關閉。
  不要僅憑 close code 將超時與使用者停止區分。

### 前端消費方式

- **直接監看**：開啟 `http://SERVER_IP:8000/camera`，不必啟動 React。
- **接進 React**：建立 `/ws/camera/view` WebSocket，`onopen` 送 `next`。
  binary 以 JPEG Blob 解碼顯示；完成後釋放 Object URL，再送下一個 `next`。
  text 解析為 `CameraViewStatus`，`waiting` 隱藏舊畫面、`unchanged` 暫時保留。
- **重連與離頁**：斷線後重建 WebSocket；離開頁面時關閉連線、清除重試計時器與 Blob URL。
- **畫面資訊**：尺寸由解碼後影像取得，FPS 由前端實際收到的圖片數計算；server 沒有 stats endpoint。
- **骨架／姿勢**：本介面只給原圖，不能從回應拿到 MoveNet keypoints。
  若要疊圖需先增加帶 frame ID / timestamp 的姿勢協定。

可直接參考 [目前的完整觀看頁實作](../backend/app/camera.html)。
網頁若與 backend 不同 host / port，自訂前端必須明確使用 backend 的 WebSocket 位址，
不要把 `/ws/camera/view` 誤接到 Vite server。

### 部署限制與目前狀態

| 項目 | 目前狀態 |
|---|---|
| 影像接收／觀看／ACK／最新圖覆寫 | 已實作 |
| 多觀看者 | 支援；未做容量或負載上限保證 |
| 多 camera / 床位對應 | 未實作；不能靠多開發布者達成 |
| MoveNet | 板子端獨立執行；保留原有姿勢判斷與終端輸出 |
| 姿勢／keypoints 上傳 | 未實作 |
| 音訊／錄影／歷史影像 | 未實作 |
| 身分驗證／觀看權限 | 未實作；限受信任區網實驗 |
| 狀態持久化 | 無；重啟 server 清空最新影像與連線 |
| 多程序部署 | 不支援；只有一個 Uvicorn worker |
| OpenAPI `/docs` | WebSocket 契約不在 OpenAPI；`/camera` 也刻意排除於 schema |

建議從專案根目錄啟動 server：

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 \
  --workers 1 --ws-max-size 2097152 --ws-max-queue 1 --ws-per-message-deflate false
```

需要開放 TCP 8000。上述限制配合單一 process 的記憶體影像槽；若改用多 worker，
發布者和觀看者可能落到不同程序而看不到彼此影像。

依賴安裝、板子相機設定與 MoveNet 啟動請見本文件前面的章節；操作驗收見下方「驗收與排錯」。
後端契約回歸測試在 [backend/tests/test_camera_stream.py](../backend/tests/test_camera_stream.py)。

## 驗收與排錯

1. 先啟動 server，開頁面應看到「等待攝影機」。
2. 發布測試動畫或 camera，應看到即時影像與 FPS。
3. 開兩個觀看頁，確認互不阻塞。刻意放慢其中一個觀看者，恢復後應跳到最新影像。
4. 停止發布，頁面應隱藏舊影像；重新啟動後自動恢復。
5. 連續觀看 5 分鐘，用鏡頭前的時鐘估計延遲，記錄 Wi-Fi 頻寬與有效 FPS。

- `No module named gi`：檢查 OS PyGObject 與 venv 的 system-site-packages。
- `not-negotiated` / 沒有影像：檢查 MJPG、尺寸、FPS 和正確 /dev/videoN。
- `device busy`：關掉另一個 camera 程式；未來要推論分流應在同一 pipeline 用 tee。
- 連不上：檢查 server IP、TCP 8000、防火牆，以及 Wi-Fi 是否啟用用戶端隔離。
- 畫面卡：先降 FPS 或解析度；板子不轉碼，JPEG 品質要用鏡頭支援的控制設定調整。
- server 顯示 A camera is already publishing：先停止前一個發布程式。

後端回歸測試（另需 `pip install httpx`）：

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
```

參考：[GStreamer appsink](https://gstreamer.freedesktop.org/documentation/app/appsink.html)、
[WebSocket Python client](https://websockets.readthedocs.io/en/stable/reference/sync/client.html)。

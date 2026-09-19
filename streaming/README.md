# MJPEG 即時監看

## 架構與規劃

C270 → GStreamer V4L2（image/jpeg）→ WebSocket 二進位 JPEG → FastAPI → 瀏覽器。
鏡頭模式直接複製原有 JPEG bytes，不解碼、不重新編碼、不需要 H.264 編碼器。
本階段為單台 camera 即時觀看，可選擇同時在板子執行 MoveNet，不做音訊或錄影。
整合分支為 `feat/movenet-camera-stream`，從 MJPEG 監看分支延伸。

- 板子 appsink 只留最新一張，滿了丟舊圖；收到 server ACK 才取下一張。
- 啟用 MoveNet 時，camera 只開一次，以 tee 分成兩路 JPEG；每路有獨立的 leaky queue
  和 appsink，各最多保留一張待取影像（另有正在處理／傳輸的影像）。
- 推論執行緒只解碼自己的 JPEG，不更動送往 server 的原始 JPEG；網路重連不會等待推論。
- Server 只存最新一張，每個觀看者顯示完才要求下一張，慢的觀看者不阻塞發布者。
- 觀看 client 應解碼後再請求、釋放 Blob URL，並自行處理斷線重連與過期畫面。
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

只開 TCP 8000。此 server 同時提供既有病房 REST / WebSocket 與 camera 串流，
共用 `app.main:app`，不需額外啟動第二個 backend。此實驗使用記憶體內的單一 camera 狀態，**只能一個 worker**；
多 worker 必須先加入跨程序影像共享。此區網實驗沒有帳密，勿直接暴露到網際網路。

觀看 API：`ws://SERVER_IP:8000/ws/camera/view`。
Backend 只提供 API，不再提供 `/camera` HTML 頁；前端需自行接收 JPEG 並顯示。
不需 Docker 或 MediaMTX。
若之前自行啟動 MediaMTX 容器，請先用原 Compose 設定停止它；本版已移除舊設定。

## 板子：確認 MJPEG 與依賴

需 Python 3.9+、GStreamer 1.x、Python GI（PyGObject）、Gst introspection、
`v4l2src`、`appsink`、websockets 15。Ubuntu / Debian 範例：

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
啟動後應看到模型資訊、`MoveNet branch started`，以及 `Connected. Viewer API: ...`。
即使 server 尚未啟動，也會先在板子終端看到推論輸出。

辨識規則已更新為 `movenet_with_fall_with_unknown.py`：保留 17 點、0.20 信心閾值、
原始量化處理、七次多數決、非人形連續 2 秒後 unknown，以及髖部快速下降後
連續三幀低位確認的跌倒判斷（保留 3 秒）。不另開 VideoCapture 或 GUI，也不自動保存影像／關鍵點歷史。

每次推論結果透過獨立背景執行緒送到 `/ws/room/101?role=board`；不等待 ACK。
`standing`、`sitting`、`lying` 使用平滑結果，unknown 傳 `null`。
`in_camera` 依是否至少一個關鍵點達信心閾值判定；沒人時姿勢一律為 `null`。
跌倒與姿勢分開：不把 `fall` 寫進姿勢欄位，而由另一背景執行緒
POST `/api/beds/101/possible-fall`，body 帶 UTC `ts`。跌倒維持期間持續回報，由後端去重。

三條網路通道各自重連。姿勢僅保留最新一筆；跌倒保留一筆待送事件，失敗每 2 秒重試，
後續正常姿勢不會清掉尚未送出的跌倒。這些緩衝只存於記憶體，程式重啟後不保留。
`--pose-print-interval` 只限制終端輸出，不限制上傳頻率。
兩路各自丟棄舊圖，因此推論結果與觀看畫面不保證逐幀對齊；觀看影像仍是原始 JPEG。
詳細資料格式見 [`BOARD_API_SPEC.md`](../BOARD_API_SPEC.md)。

模型／delegate 載入失敗會在開鏡頭前退出。執行途中推論出錯會印出 `MoveNet stopped`，
監看繼續；重啟整合程式可恢復推論。Ctrl+C 會停止 pipeline 並通知推論執行緒退出；
若 NPU invoke 卡住，最多等待 5 秒並提示。獨立執行緒仍共用板子的 CPU / 記憶體頻寬，
需在板子實測 JPEG 解碼與 NPU 的吞吐量，無法保證推論對影像 FPS 完全沒有影響。

### 整合驗收

1. 終端持續出現 Raw / Stable / Base pose、跌倒與 unknown 狀態；觀看 client 同時收到原始 JPEG。
2. 停止 server：板子應持續推論並重試串流；重新啟動 server 後恢復監看。
3. 確认沒有第二個 VideoCapture 程式占用鏡頭，畫面延遲不隨時間累積。
4. Ctrl+C 停止後，再次啟動可重新取得 camera。

不需 GI / NPU 的本機回歸測試（需要 NumPy、OpenCV）：

```bash
python3 -m unittest discover -s streaming/tests -v
```

測試包含 JPEG bytes 保留、RGB / 量化處理、姿勢規則、慢推論丟舊圖、
以及模擬網路／推論互不等待。這些是單元測試，並不取代板子的 camera、GStreamer tee 與 NPU 實機測試。

## Streaming API spec

以下描述目前 `backend/app/camera_stream.py`、`backend/app/main.py` 與
`streaming/publish_camera.py` 的實作，不代表尚未實作的規劃。

### 連線設定與端點

範例 server：`192.168.1.100:8000`。所有服務共用 TCP 8000。
預設使用 HTTP / WS，沒有登入、token、WebSocket subprotocol 或房間識別參數。
若另行部署 TLS reverse proxy，觀看 client 應使用 WSS；目前板子 CLI 固定使用 WS。

| 協定 | 路徑 | 呼叫端 | 用途 |
| --- | --- | --- | --- |
| HTTP GET | `/` | 任意 HTTP client | 健康檢查 |
| WebSocket | `/ws/camera/publish` | 開發板 | 發布原始 JPEG |
| WebSocket | `/ws/camera/view` | 瀏覽器／觀看 client | 依請求取得最新 JPEG |

現有病房狀態端點為 `/ws/overview` 與 `/ws/room/{bed_id}`，與 camera 路由共用 server；
它們傳送病房 JSON，不接收 JPEG。`/ws` 已不存在，不能用來傳影像。
WebSocket 協定不列入 FastAPI OpenAPI，因此 `/docs` 不是這份串流協定的完整清單。
`GET /camera` 已移除，回傳 HTTP 404。

### HTTP GET `/`

無 request body。成功回應為 HTTP 200，Content-Type 為 `application/json`：

```json
{"status":"ok"}
```

只代表 FastAPI 可回應，不代表 camera 已連上或影像仍在更新。

### 共用影像格式

| 項目 | 格式／限制 |
| --- | --- |
| WebSocket message type | Binary |
| Payload | 一張完整 JPEG 的 bytes |
| 應用層包裝 | 無 JSON、Base64、長度前綴或自訂 header |
| 單張大小 | 4～2,097,152 bytes（2 MiB），含上下限 |
| JPEG 頭尾 | 起始 `FF D8`，結尾 `FF D9` |
| 格式檢查 | 僅檢查大小與頭尾，不驗證 JPEG 內部結構 |
| 解析度、FPS | API 未固定；板子預設 640×480、15 FPS |
| Metadata | 未傳送 frame ID、timestamp、camera ID、房間 ID 或姿勢結果 |

「一張」以完整 WebSocket message 為界，不以 TCP packet 或底層 WebSocket fragment 為界。
JPEG bytes 原樣轉送，server 不解碼、不重新編碼、不錄影。
即使收到 `ok`，也可能因 JPEG 內部損壞而無法在瀏覽器解碼。

### WebSocket `/ws/camera/publish`：板子發布

```text
ws://192.168.1.100:8000/ws/camera/publish
```

沒有 request body 或必填 query parameter。訊息順序如下：

```text
板子                                  Server
  ├──── WebSocket handshake ────────────→│
  │←─── Text: ready ────────────────────┤
  ├──── Binary: 完整 JPEG ──────────────→│
  │←─── Text: ok ───────────────────────┤
  ├──── Binary: 下一張完整 JPEG ────────→│
  │←─── Text: ok ───────────────────────┤
```

`ready` 與 `ok` 都是純文字，沒有 JSON 引號或物件包裝。

1. Server 接受 WebSocket 後，若沒有其他發布者，登記連線並送出 `ready`。
2. 板子等到 `ready` 才開始送圖，每次只送一張完整 JPEG。
3. Server 檢查格式後，覆寫最新影像、更新內部序號及接收時間，再回 `ok`。
4. 板子收到 `ok` 後才從 camera 緩衝取下一張；不要預先累積待送影像。
5. `ok` 表示 server 已接收並更新最新影像，不保證任何觀看者已收到或顯示。

同時只允許一個發布者。第二個發布者的 WebSocket 會先被接受，再以 close code `1008`
關閉，不會收到 `ready`，也不會取代原發布者。

每次等待下一則上傳訊息的期限為 10 秒，送出 ACK 的期限為 5 秒。
發布者離線、格式錯誤或逾時後，server 釋放發布者並清除最新影像；重新連線要重新等 `ready`。

### WebSocket `/ws/camera/view`：前端觀看

```text
ws://192.168.1.100:8000/ws/camera/view
```

Server 接受連線後不主動送 `ready` 或影像。觀看端必須先送純文字 `next`：

```text
觀看端                                Server
  ├──── WebSocket handshake ────────────→│
  ├──── Text: next ─────────────────────→│
  │←─── Binary: 最新 JPEG ──────────────┤
  │     解碼、顯示，釋放 Blob URL         │
  ├──── Text: next ─────────────────────→│
  │←─── Binary JPEG 或 Text JSON ───────┤
```

一個 `next` 對應一則回應；回應類型如下：

| 類型 | 內容 | 意義與前端處理 |
| --- | --- | --- |
| Binary | JPEG bytes | 解碼並顯示；完成後才送下一個 `next` |
| Text JSON | `{"status":"waiting"}` | 沒有可用的新鮮影像；隱藏舊畫面，繼續請求 |
| Text JSON | `{"status":"unchanged"}` | 最新影像仍有效，但與上次回應的序號相同；可保留畫面並繼續請求 |

`waiting` 不區分尚未開機、發布者斷線或影像過期，不能用它判斷確切原因。
狀態是 JSON 文字訊息，應先以訊息型別區分 JPEG 與 JSON，再解析 JSON。

- 每個觀看端一次只應保留一個未完成的 `next`，不要用計時器無限制送請求。
- Server 若沒有更新的序號且發布者仍在線，最多等待約 1 秒，再回傳當下影像或狀態。
- 最新 JPEG 距 server 接收時間達 3 秒即過期，回 `waiting`；此時間不是 camera 擷取時間。
- 初次連線可以取得最近一張尚未過期的影像，後續只取較新的影像。
- 多個觀看者各自記錄已回應的序號，慢的觀看者直接跳到最新影像，不補播漏看的畫面。
- 沒有發布者時，server 回狀態後暫停 0.2 秒再處理下一個請求，避免空轉。
- 每次等待觀看端的下一個 `next` 最多 30 秒；送出 JPEG 最多等待 5 秒。
- JSON 狀態送出目前沒有另外設定應用層 5 秒 timeout。

### 關閉碼與錯誤處理

錯誤透過 WebSocket close 回報，不是 HTTP JSON error body。

| Code | 端點／情境 | 目前 reason |
| --- | --- | --- |
| `1008` | publish：已有發布者 | `A camera is already publishing` |
| `1009` | publish：非 binary、少於 4 bytes 或大於 2 MiB | `Expected JPEG bytes, maximum 2 MiB` |
| `1003` | publish：JPEG 頭尾不符 | `Invalid JPEG envelope` |
| `1008` | view：收到不是 `next` 的文字 | `Expected next` |
| `1000` | 應用層逾時後，server 主動正常關閉 | 無特定 reason |

啟动命令的 `--ws-max-size 2097152` 也會在 WebSocket transport 層限制大小；
超大訊息可能在進入 handler 前就以 `1009` 關閉，此時 reason 不保證與上表相同。
網路直接斷開時可能無法收到 close frame，不要只靠 close code 判斷是否需要重連。

view 端的 binary request 不在協定內；目前 handler 使用 `receive_text()`，
未替這種誤用定義穩定的 close code。請始終送文字 `next`。
正常收到 `waiting` 或 `unchanged` 不需要重新連線，繼續送下一個 `next` 即可。

### 逾時與 client 重連行為

| 所在端 | 行為 | 期限／間隔 |
| --- | --- | --- |
| Server | 等待發布端下一則訊息 | 10 秒 |
| Server | 送出發布 ACK | 5 秒 |
| Server | 等待觀看端下一個請求 | 30 秒 |
| Server | 等待更新影像 | 最多約 1 秒 |
| Server | 送出觀看端 JPEG | 5 秒 |
| Server | 影像新鮮度 | 接收後小於 3 秒 |
| 板子 client | 建立連線、等 `ready`、等 `ok` | 各 5 秒 |
| 板子 client | 可恢復的連線錯誤／斷線後重試 | 每次失敗後等 2 秒 |

板子收到 `1003`、`1008`、`1009` 視為拒絕發布並退出，修正原因後重啟。
觀看 client 應在解碼完成後才要求下一張，釋放 Blob URL；收到 `waiting` 或斷線時隱藏舊畫面。
前端需自行實作重連與無影像逾時，backend 不提供內建監看頁。
上述板子重試是發布 client 的行為，不是 server 自動重建 client 連線。

### 最小 client 範例

Python 發布一張既有 JPEG，驗證 handshake 與 ACK（需 websockets 15）：

```python
from pathlib import Path
from websockets.sync.client import connect

with connect("ws://192.168.1.100:8000/ws/camera/publish", compression=None) as ws:
    assert ws.recv(timeout=5) == "ready"
    ws.send(Path("frame.jpg").read_bytes())
    assert ws.recv(timeout=5) == "ok"
```

此範例只測上傳；離開 `with` 會立刻斷線並清除 server 的影像。
持續監看請使用上方 `publish_camera.py` 或 `movenet_test.py` 指令。

瀏覽器最小取圖範例（由你的前端提供頁面；範例未包含自動重連及無影像逾時）：

```html
<img id="camera-preview" alt="Camera" hidden>
<script>
const image = document.querySelector('#camera-preview');
// 換成實際 backend 地址；HTTPS 前端需使用可連線的 wss:// backend。
const ws = new WebSocket('ws://192.168.1.100:8000/ws/camera/view');
ws.binaryType = 'blob';
const next = () => {
  if (ws.readyState === WebSocket.OPEN) ws.send('next');
};
ws.onopen = next;
ws.onmessage = async ({data}) => {
  if (typeof data === 'string') {
    if (JSON.parse(data).status === 'waiting') image.hidden = true;
  } else {
    const url = URL.createObjectURL(new Blob([data], {type: 'image/jpeg'}));
    try {
      image.src = url;
      await image.decode();
      image.hidden = ws.readyState !== WebSocket.OPEN;
    } catch {
      image.hidden = true;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  next();
};
ws.onclose = () => { image.hidden = true; };
</script>
```

### 狀態儲存與未提供的功能

Server 在單一 process 記憶體保留最新 JPEG、接收時間與遞增序號；序號只供 server 內部比較，
不會放在訊息內。重啟 server 會清空狀態，所以部署必須使用單一 worker。
不同觀看端可以收到不同影像，協定不保證每張都送達所有觀看者。

目前沒有多 camera／影像房間路由、歷史影像、錄影下載、影像 metadata、骨架疊圖或認證 API。
姿勢 JSON 走獨立 board WebSocket。若要同步骨架與畫面，需另增 frame ID／timestamp 與資料協定，
不能把姿勢 JSON 混送到現有 publish 端點。

## 驗收與排錯

1. 先啟動 server，觀看 client 連 `/ws/camera/view` 並送 `next`，應收到 `waiting`。
2. 發布測試動畫或 camera，觀看 client 應收到可解碼的 JPEG。
3. 開兩個觀看 client，確認互不阻塞。刻意放慢其中一個觀看者，恢復後應跳到最新影像。
4. 停止發布，觀看 client 下一個 `next` 應收到 `waiting`；重新發布後應取得新 JPEG。
5. 連續觀看 5 分鐘，用鏡頭前的時鐘估計延遲，記錄 Wi-Fi 頻寬與有效 FPS。

- `No module named gi`：檢查 OS PyGObject 與 venv 的 system-site-packages。
- `not-negotiated` / 沒有影像：檢查 MJPG、尺寸、FPS 和正確 /dev/videoN。
- `device busy`：關掉原本獨立執行的 movenet_test.py 或其他 camera 程式，改用下方整合入口。
- 連不上：檢查 server IP、TCP 8000、防火牆，以及 Wi-Fi 是否啟用用戶端隔離。
- 畫面卡：先降 FPS 或解析度；板子不轉碼，JPEG 品質要用鏡頭支援的控制設定調整。
- server 顯示 A camera is already publishing：先停止前一個發布程式。

後端回歸測試（另需 `pip install httpx`）：

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
```

參考：[GStreamer appsink](https://gstreamer.freedesktop.org/documentation/app/appsink.html)、
[WebSocket Python client](https://websockets.readthedocs.io/en/stable/reference/sync/client.html)。

`unknown` 仍以 `current_posture: null` 上傳，後端將它判為 `out_of_bed`（離床），
即使 `in_camera: true` 也一樣。保留原程式連續 2 秒非人形才進入 unknown 的規則。
房間狀態 WebSocket 新增 `location` 欄位，前端顯示「目前位置：離床」；
尚未收到板子資料時 `location: null`，顯示「等待辨識」。真實廁所訊號仍優先，101 不使用隨機廁所訊號。

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

## 協定

- `/ws/camera/publish`：server 先回 `ready`；每則 binary message 是完整 JPEG，server 回 `ok`。
  上限 2 MiB，10 秒沒送新影像則斷線。只檢查 JPEG 頭尾，不進行完整解碼驗證。
- `/ws/camera/view`：觀看端送文字 `next`，server 回最新 JPEG 或 JSON
  `{"status":"waiting"}` / `{"status":"unchanged"}`。一次只應有一個未完成請求。
- `/camera`：FastAPI 提供的監看頁，顯示尺寸、實際接收 FPS、最近影像大小與連線狀態。

## 驗收與排錯

1. 先啟動 server，開頁面應看到「等待攝影機」。
2. 發布測試動畫或 camera，應看到即時影像與 FPS。
3. 開兩個觀看頁，確認互不阻塞。刻意放慢其中一個觀看者，恢復後應跳到最新影像。
4. 停止發布，頁面應隱藏舊影像；重新啟動後自動恢復。
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

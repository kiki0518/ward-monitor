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

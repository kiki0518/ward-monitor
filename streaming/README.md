# Camera 即時監看實驗

## 規劃與範圍

先完成單一 camera → GStreamer → H.264 / RTSP TCP → MediaMTX → WebRTC 瀏覽器。
使用 MediaMTX 內建播放器，本階段不必啟動 FastAPI / React。
不做姿勢推論、骨架疊圖、音訊或錄影。影片是未疊圖的攝影機畫面，H.264 為有損壓縮。
先以測試動畫驗證網路，再切換真實 camera，最後驗證斷線與重新發布。

## 1. Server 啟動

需要 Docker Engine / Docker Desktop（必須已啟動）及 Docker Compose。
在本目錄執行；將 IP 換成觀看端與板子皆可連到的 server 區網 IPv4：

```bash
SERVER_IP=192.168.1.100 docker compose up -d
SERVER_IP=192.168.1.100 docker compose logs -f mediamtx
```

`SERVER_IP` 是 WebRTC 回報給瀏覽器的地址，不可填 Docker 內部 IP、`0.0.0.0`，
跨機器測試也不可填 `localhost`。每次執行 compose 都帶上相同變數。
需允許 TCP 8554（板子推流）、TCP 8889（觀看頁與協商）、UDP 8189（影片）。
此配置沒有帳密，限受信任區網實驗，勿直接開放到網際網路。

不用 Docker 也可下載 **MediaMTX v1.21.0** 對應平台的官方 binary，在本目錄執行：

```bash
MTX_WEBRTCADDITIONALHOSTS=192.168.1.100 ./mediamtx mediamtx.yml
```

## 2. 發送端依賴與鏡頭確認

發送端需要 Python 3、GStreamer、`rtspclientsink`、`h264parse`、`rtph264pay`。
raw / MJPEG / test 模式另需 `x264enc`（CPU 軟體編碼）；MJPEG 另需 `jpegdec`。
不假設 i.MX93 有 H.264 硬體編碼器。Ubuntu / Debian 可安裝：

```bash
sudo apt-get install python3 v4l-utils gstreamer1.0-tools \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-rtsp
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

Yocto / NXP BSP 應使用系統映像對應的套件或建置配方，不能直接套用 apt 指令。
MIPI CSI 若需要 ISP / media-controller 初始化，請先用板廠 pipeline 確認能出圖；
本腳本只處理已能直接透過 V4L2 取圖的節點，不會自動初始化 CSI。

## 3. 先測試動畫，再換鏡頭

在有上述 GStreamer plugins 的發送端，從專案根目錄執行：

```bash
python3 streaming/publish_camera.py --server 192.168.1.100 --source test
```

在瀏覽器開啟 `http://192.168.1.100:8889/camera`，應看到移動球體。
這是 server 提供的即時播放器，不需 React。若 autoplay 被擋，點播放。
停止測試動畫（Ctrl+C）後，再選一個鏡頭模式：

```bash
# YUYV / NV12 等 raw 格式 → CPU H.264 編碼
python3 streaming/publish_camera.py --server 192.168.1.100 --source raw --device /dev/video0

# MJPG → 解 JPEG → CPU H.264 編碼
python3 streaming/publish_camera.py --server 192.168.1.100 --source mjpeg --device /dev/video0

# 鏡頭本身輸出 H.264 → 直接傳送，不重新編碼
python3 streaming/publish_camera.py --server 192.168.1.100 --source h264 --device /dev/video0
```

預設 640×480、15 FPS、軟體編碼 1500 kbit/s；必須符合鏡頭列出的格式組合。
可加 `--width 1280 --height 720 --fps 30 --bitrate 3000` 調整。
H.264 直傳忽略 bitrate，攝影機需輸出瀏覽器支援的 profile 且不含 B frames，
建議 baseline、約每秒一個 keyframe；請透過鏡頭設定控制，MediaMTX 不會轉碼。
若直傳在 VLC 能看、瀏覽器不能看，改用 raw / MJPEG 模式測試 baseline 軟體編碼。

加 `--dry-run` 可只列印 pipeline，不開鏡頭、不需要安裝 GStreamer。
腳本不會自動重新連線，出错後檢查 stderr 並重新執行。每個 camera path 同時只允許一個發布者。

## 驗收

1. 測試動畫能在另一台電腦瀏覽器播放，server log 出現 camera publisher 與 WebRTC reader。
2. 換真實 camera 後，揮手與鏡頭前的時鐘持續更新。比較實物與播放畫面估計延遲，
   記錄解析度、FPS、CPU 使用率與網路；區網試驗以小於 1 秒為目標，不視為保證。
3. 連續播放 5 分鐘，確認延遲沒有持續累積。CPU 滿載時降低解析度 / FPS。
4. Ctrl+C 停止發布，確認畫面不再更新；重新執行發布器，必要時重整播放器，確認恢復。
5. 另一個發布者不能覆蓋現有串流；不要同時用推論程式占用同一個 camera。

測試結束停止 server：

```bash
SERVER_IP=192.168.1.100 docker compose down
```

## 排錯與後续

- `not-negotiated`：格式、解析度、FPS 不符鏡頭；重查 `--list-formats-ext`。
- 缺 `x264enc`：安裝對應 plugin，或鏡頭支援 H.264 時使用直傳模式。
- RTSP 連不上：檢查 server log、IP、TCP 8554、防火牆。
- 頁面能開但沒有影片：先確認有發布者，再檢查 SERVER_IP、UDP 8189 與 codec。
  用 VLC 開 `rtsp://192.168.1.100:8554/camera` 可以分辨 RTSP 與 WebRTC 問題。
- `device busy`：停止正在占用鏡頭的其他程式。
- 之後接姿勢判斷時，將現有單一擷取 pipeline 透過 `tee` 分支到 appsink，
  每路獨立 queue；不要再開第二個 V4L2 capture。本階段未加入這個分支。

## 官方參考

- [MediaMTX 安裝與 Docker 網路](https://mediamtx.org/docs/kickoff/install)
- [GStreamer 發布 RTSP](https://mediamtx.org/docs/publish/gstreamer)
- [瀏覽器觀看及內嵌播放器](https://mediamtx.org/docs/read/web-browsers)

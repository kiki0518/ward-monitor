#!/usr/bin/env python3
"""Demo 用：偵測到鏡頭前有人坐著，才觸發 103 床「長時間維持坐姿」。

用法：
    python backend/scripts/trigger_long_sitting.py [server_url]

103 沒有真的感測器，借用 101 床共用鏡頭的即時資料（/ws/room/101）：等偵測到
「鏡頭前有人坐著」（in_camera=true 且 current_posture=="sitting"）才呼叫
POST /api/beds/103/demo-event。Ctrl+C 可以中途取消。預設 server_url 是
http://localhost:8000。重複觸發不會開出多筆重複事件（backend 有去重機制，
見 API_CONTRACT.md「事件生命週期」）。
"""

import json
import sys

import requests
from websockets.sync.client import connect

BED_ID = "103"
SOURCE_BED_ID = "101"  # 借用共用鏡頭的 current_posture 訊號，103 本身沒有真的感測器


def wait_for_sitting(ws_url: str) -> None:
    print(f"等待偵測：鏡頭前有人坐著（模擬 {BED_ID} 床長時間坐姿）...")
    with connect(ws_url) as ws:
        while True:
            state = json.loads(ws.recv())
            if state.get("in_camera") and state.get("current_posture") == "sitting":
                return


def main() -> None:
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws/room/{SOURCE_BED_ID}"

    try:
        wait_for_sitting(ws_url)
    except KeyboardInterrupt:
        print("已取消")
        return

    url = f"{server_url}/api/beds/{BED_ID}/demo-event"
    response = requests.post(url, json={"scenario": "long_sitting"})
    response.raise_for_status()
    print(f"偵測到坐姿，觸發成功：{BED_ID} 床 長時間維持坐姿")
    print(response.json())


if __name__ == "__main__":
    main()

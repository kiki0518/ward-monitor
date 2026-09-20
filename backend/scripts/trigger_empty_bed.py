#!/usr/bin/env python3
"""Demo 用：偵測到鏡頭前沒有人，才觸發 102 床「空床」（離床超過半小時）。

用法：
    python backend/scripts/trigger_empty_bed.py [server_url]

102 沒有真的感測器，借用 101 床共用鏡頭的即時資料（/ws/room/101）：等偵測到
「鏡頭前沒有人」（in_camera=false）才呼叫 POST /api/beds/102/demo-event。
Ctrl+C 可以中途取消。預設 server_url 是 http://localhost:8000。重複觸發
不會開出多筆重複事件（backend 有去重機制，見 API_CONTRACT.md「事件生命週期」）。
"""

import json
import sys

import requests
from websockets.sync.client import connect

BED_ID = "102"
SOURCE_BED_ID = "101"  # 借用共用鏡頭的 in_camera 訊號，102 本身沒有真的感測器


def wait_for_empty(ws_url: str) -> None:
    print(f"等待偵測：鏡頭前沒有人（模擬 {BED_ID} 床空床）...")
    with connect(ws_url) as ws:
        while True:
            state = json.loads(ws.recv())
            if state.get("in_camera") is False:
                return


def main() -> None:
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws/room/{SOURCE_BED_ID}"

    try:
        wait_for_empty(ws_url)
    except KeyboardInterrupt:
        print("已取消")
        return

    url = f"{server_url}/api/beds/{BED_ID}/demo-event"
    response = requests.post(url, json={"scenario": "empty_bed"})
    response.raise_for_status()
    print(f"偵測到空床，觸發成功：{BED_ID} 床 空床")
    print(response.json())


if __name__ == "__main__":
    main()

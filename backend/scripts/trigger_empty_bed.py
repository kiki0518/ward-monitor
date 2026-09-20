#!/usr/bin/env python3
"""Demo 用：偵測到鏡頭前沒有人，才觸發 102 床「空床」（離床超過半小時）。

用法：
    python backend/scripts/trigger_empty_bed.py [server_url] [--debug]

102 沒有真的感測器，借用 101 床共用鏡頭的即時資料（/ws/room/101）：等偵測到
「鏡頭前沒有人」（in_camera=false）才呼叫 POST /api/beds/102/demo-event。
Ctrl+C 可以中途取消。預設 server_url 是 http://localhost:8000。

backend 的 report_event() 有去重機制（同一床同一種 state 只要還沒 resolve，
重複回報只會更新既有那筆的 last_seen_at，started_at 不變）。但這樣拿來 demo
會出現「明明剛剛才觸發，畫面卻顯示是幾分鐘前發生」的問題（前端顯示的時間是
started_at）。所以這支腳本觸發前會先自己呼叫 resolve 清掉 102 床任何還在
active 的空床事件，確保每次執行都是全新的一筆、時間戳記一定是剛剛。

`--debug`：板子/攝影機不在或還沒接上時測試用，最多等 5 秒，時間到了不管有沒有
真的偵測到都直接觸發，方便單獨測 backend 這條事件流程。
"""

import json
import sys
import time

import requests
from websockets.sync.client import connect

BED_ID = "102"
SOURCE_BED_ID = "101"  # 借用共用鏡頭的 in_camera 訊號，102 本身沒有真的感測器
STATE = "bed_exit"
DEBUG_TIMEOUT_SECONDS = 5.0


def clear_stale_event(server_url: str) -> None:
    """觸發前先 resolve 掉 102 床任何還 active 的空床事件，讓這次一定是全新的一筆。"""
    try:
        events = requests.get(f"{server_url}/api/beds/{BED_ID}/events").json()
    except requests.RequestException as exc:
        print(f"查詢舊事件失敗，跳過清除：{exc}")
        return
    for event in events:
        if event["state"] != STATE:
            continue
        try:
            requests.post(
                f"{server_url}/api/events/{event['event_id']}/resolve",
                json={
                    "completed_actions": "demo 腳本重新觸發，自動清除舊事件",
                    "follow_up": "無",
                    "notes": "auto-cleared by trigger_empty_bed.py",
                },
            ).raise_for_status()
        except requests.RequestException as exc:
            print(f"清除舊事件 {event['event_id']} 失敗，跳過：{exc}")


def parse_args(argv: list[str]) -> tuple[str, bool]:
    debug = "--debug" in argv
    positional = [arg for arg in argv if not arg.startswith("--")]
    server_url = positional[0] if positional else "http://localhost:8000"
    return server_url, debug


def wait_for_empty(ws_url: str, debug: bool) -> None:
    suffix = f"（--debug：最多等 {DEBUG_TIMEOUT_SECONDS:.0f} 秒，時間到強制觸發）" if debug else ""
    print(f"等待偵測：鏡頭前沒有人（模擬 {BED_ID} 床空床）...{suffix}")
    deadline = time.monotonic() + DEBUG_TIMEOUT_SECONDS if debug else None
    with connect(ws_url) as ws:
        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    print(f"--debug：{DEBUG_TIMEOUT_SECONDS:.0f} 秒到了，沒偵測到也強制觸發")
                    return
                try:
                    raw = ws.recv(timeout=remaining)
                except TimeoutError:
                    continue
            else:
                raw = ws.recv()
            state = json.loads(raw)
            if state.get("in_camera") is False:
                return


def main() -> None:
    server_url, debug = parse_args(sys.argv[1:])
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws/room/{SOURCE_BED_ID}"

    try:
        wait_for_empty(ws_url, debug)
    except KeyboardInterrupt:
        print("已取消")
        return

    clear_stale_event(server_url)

    url = f"{server_url}/api/beds/{BED_ID}/demo-event"
    response = requests.post(url, json={"scenario": "empty_bed"})
    response.raise_for_status()
    print(f"觸發成功：{BED_ID} 床 空床")
    print(response.json())


if __name__ == "__main__":
    main()

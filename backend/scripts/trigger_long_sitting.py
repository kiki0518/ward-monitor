#!/usr/bin/env python3
"""Demo 用：偵測到鏡頭前有人坐著，才觸發 101 床「長時間維持坐姿」。

用法：
    python backend/scripts/trigger_long_sitting.py [server_url] [--debug]

連到 101 床即時姿勢資料（/ws/room/101，跟真的板子共用同一份 in_camera/
current_posture），等偵測到「鏡頭前有人坐著」（in_camera=true 且
current_posture=="sitting"）才呼叫 POST /api/beds/101/demo-event。
Ctrl+C 可以中途取消。預設 server_url 是 http://localhost:8000。

backend 的 report_event() 有去重機制（同一床同一種 state 只要還沒 resolve，
重複回報只會更新既有那筆的 last_seen_at，started_at 不變）。但這樣拿來 demo
會出現「明明剛剛才觸發，畫面卻顯示是幾分鐘前發生」的問題（前端顯示的時間是
started_at）。所以這支腳本觸發前會先自己呼叫 resolve 清掉 101 床所有還在
active 的事件（不分 state），確保每次執行 101 身上都只有這一筆全新的事件、
時間戳記一定是剛剛。

`--debug`：板子/攝影機不在或還沒接上時測試用，最多等 5 秒，時間到了不管有沒有
真的偵測到都直接觸發，方便單獨測 backend 這條事件流程。
"""

import json
import sys
import time

import requests
from websockets.sync.client import connect

BED_ID = "101"
DEBUG_TIMEOUT_SECONDS = 5.0


def clear_stale_event(server_url: str) -> None:
    """觸發前先 resolve 掉 101 床所有還 active 的事件（不分 state），讓這次一定是
    這個人身上唯一、全新的一筆，不會跟之前殘留的其他事件疊在一起。"""
    try:
        events = requests.get(f"{server_url}/api/beds/{BED_ID}/events").json()
    except requests.RequestException as exc:
        print(f"查詢舊事件失敗，跳過清除：{exc}")
        return
    for event in events:
        try:
            requests.post(
                f"{server_url}/api/events/{event['event_id']}/resolve",
                json={
                    "completed_actions": "demo 腳本重新觸發，自動清除舊事件",
                    "follow_up": "無",
                    "notes": "auto-cleared by trigger_long_sitting.py",
                },
            ).raise_for_status()
        except requests.RequestException as exc:
            print(f"清除舊事件 {event['event_id']} 失敗，跳過：{exc}")


def parse_args(argv: list[str]) -> tuple[str, bool]:
    debug = "--debug" in argv
    positional = [arg for arg in argv if not arg.startswith("--")]
    server_url = positional[0] if positional else "http://localhost:8000"
    return server_url, debug


def wait_for_sitting(ws_url: str, debug: bool) -> None:
    suffix = f"（--debug：最多等 {DEBUG_TIMEOUT_SECONDS:.0f} 秒，時間到強制觸發）" if debug else ""
    print(f"等待偵測：{BED_ID} 床鏡頭前有人坐著...{suffix}")
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
            if state.get("in_camera") and state.get("current_posture") == "sitting":
                return


def main() -> None:
    server_url, debug = parse_args(sys.argv[1:])
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws/room/{BED_ID}"

    try:
        wait_for_sitting(ws_url, debug)
    except KeyboardInterrupt:
        print("已取消")
        return

    clear_stale_event(server_url)

    url = f"{server_url}/api/beds/{BED_ID}/demo-event"
    response = requests.post(url, json={"scenario": "long_sitting"})
    response.raise_for_status()
    print(f"觸發成功：{BED_ID} 床 長時間維持坐姿")
    print(response.json())


if __name__ == "__main__":
    main()

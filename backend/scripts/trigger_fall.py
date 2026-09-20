#!/usr/bin/env python3
"""Demo 用：等真的板子回報 101 床「疑似跌倒」，不會自己用姿勢亂猜。

用法：
    python backend/scripts/trigger_fall.py [server_url] [--debug]

跌倒判斷完全是板子自己做（見 BOARD_API_SPEC.md），板子偵測到就直接呼叫
POST /api/beds/101/possible-fall，不會經過 /ws/room/101 的姿勢欄位——而且
current_posture 本來就只有 standing/sitting/lying/null 這幾種值，沒有
「fall」，躺著是正常姿勢（休息、睡覺都會躺著），不能拿來當作跌倒的代理訊號。

所以這支腳本的一般模式只是連到 101 床即時資料（/ws/room/101）等 active_events
裡真的出現 state=="possible_fall"（代表板子已經偵測到、已經自己 POST 過了），
確認後印出訊息就結束，不會另外再觸發一次。Ctrl+C 可以中途取消。預設 server_url
是 http://localhost:8000。

`--debug`：板子/攝影機不在或還沒接上時測試用，最多等 5 秒；這段時間如果真的等到
板子回報就跟一般模式一樣只是確認，不會重複觸發；時間到了都沒等到，才用這支腳本
自己模擬觸發一次（呼叫同一支 POST /api/beds/101/possible-fall），方便單獨測
backend 這條事件流程。
"""

import json
import sys
import time
from datetime import datetime, timezone

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
                    "notes": "auto-cleared by trigger_fall.py",
                },
            ).raise_for_status()
        except requests.RequestException as exc:
            print(f"清除舊事件 {event['event_id']} 失敗，跳過：{exc}")


def parse_args(argv: list[str]) -> tuple[str, bool]:
    debug = "--debug" in argv
    positional = [arg for arg in argv if not arg.startswith("--")]
    server_url = positional[0] if positional else "http://localhost:8000"
    return server_url, debug


def wait_for_fall(ws_url: str, debug: bool) -> bool:
    """回傳 True 代表真的等到板子回報的 possible_fall 事件；回傳 False 代表
    （只有 --debug 才可能發生）逾時都沒等到，呼叫端要自己模擬觸發一次。"""
    suffix = f"（--debug：最多等 {DEBUG_TIMEOUT_SECONDS:.0f} 秒，時間到會改成手動模擬）" if debug else ""
    print(f"等待板子真的回報 {BED_ID} 床疑似跌倒...{suffix}")
    deadline = time.monotonic() + DEBUG_TIMEOUT_SECONDS if debug else None
    with connect(ws_url) as ws:
        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    print(f"--debug：{DEBUG_TIMEOUT_SECONDS:.0f} 秒到了，板子沒有真的回報，改成手動模擬")
                    return False
                try:
                    raw = ws.recv(timeout=remaining)
                except TimeoutError:
                    continue
            else:
                raw = ws.recv()
            state = json.loads(raw)
            active_events = state.get("active_events") or []
            if any(event.get("state") == "possible_fall" for event in active_events):
                return True


def main() -> None:
    server_url, debug = parse_args(sys.argv[1:])
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws/room/{BED_ID}"

    try:
        already_reported = wait_for_fall(ws_url, debug)
    except KeyboardInterrupt:
        print("已取消")
        return

    if already_reported:
        print(f"確認：板子已經回報 {BED_ID} 床疑似跌倒，事件已經在畫面上了，不用再手動觸發")
        return

    clear_stale_event(server_url)

    url = f"{server_url}/api/beds/{BED_ID}/possible-fall"
    response = requests.post(url, json={"ts": datetime.now(timezone.utc).isoformat()})
    response.raise_for_status()
    print(f"（板子沒有真的回報，--debug 逾時後手動模擬）觸發成功：{BED_ID} 床 疑似跌倒")
    print(response.json())


if __name__ == "__main__":
    main()

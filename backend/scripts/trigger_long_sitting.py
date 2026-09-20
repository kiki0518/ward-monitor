#!/usr/bin/env python3
"""Demo 用：手動觸發 103 床「長時間維持坐姿」。

用法：
    python backend/scripts/trigger_long_sitting.py [server_url]

預設 server_url 是 http://localhost:8000。重複執行不會開出多筆重複事件
（backend 有去重機制，見 API_CONTRACT.md「事件生命週期」）。
"""

import sys

import requests

BED_ID = "103"


def main() -> None:
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    url = f"{server_url}/api/beds/{BED_ID}/demo-event"
    response = requests.post(url, json={"scenario": "long_sitting"})
    response.raise_for_status()
    print(f"觸發成功：{BED_ID} 床 長時間維持坐姿")
    print(response.json())


if __name__ == "__main__":
    main()

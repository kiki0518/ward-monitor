"""Read-only model connection check; sends fictional treatment text only."""
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.handover import summarize
from fastapi import HTTPException

base = os.environ.get('TAIDE_API_BASE', 'http://127.0.0.1:8080/v1')
os.environ.setdefault('TAIDE_API_BASE', base)
os.environ.setdefault('TAIDE_MODEL', 'taide-handover')
try:
    with urlopen(base.rstrip('/') + '/models', timeout=10) as response:
        models = json.load(response)
    print('模型服務已連接：' + ', '.join(item['id'] for item in models['data']))
    start = time.monotonic()
    result = summarize([
        {'resolved_at': '2026-09-20T09:00:00+08:00', 'completed_actions': '已協助回床。',
         'follow_up': '下一班持續觀察。', 'notes': '家屬在場。'},
        {'resolved_at': '2026-09-20T10:00:00+08:00', 'completed_actions': '已確認呼叫鈴放在床邊。',
         'follow_up': '提醒使用呼叫鈴。', 'notes': ''},
    ])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f'摘要完成，耗時 {time.monotonic() - start:.1f} 秒；未寫入病人或交班紀錄。')
except HTTPException as error:
    print(f'摘要測試失敗：{error.detail}', file=sys.stderr)
    sys.exit(1)
except (OSError, ValueError, KeyError) as error:
    print(f'無法連接模型服務：{error}', file=sys.stderr)
    sys.exit(1)

# 依 NEWS2（National Early Warning Score 2，英國 NHS 病房監測標準）改編的
# vitals 分級判斷：對照 heart_rate/spo2/bp_systolic/temperature 四項的官方
# 分數帶（Royal College of Physicians NEWS2 對照表），各自算出 0–3 分，取
# 單項最高分決定這筆 vitals 的 priority/reason。
#
# 跟原版 NEWS2 的差異：
#   - 原版還有呼吸速率、意識狀態，血壓只看收縮壓；我們的 Vitals schema 沒有
#     呼吸速率/意識狀態欄位，所以只用得到的四項。
#   - 單項 0–1 分（正常/低風險，NEWS2 原意也只需例行觀察、不用立即介入）不
#     產生事件，避免大量無意義的「正常波動」洗版；只有單項 ≥2 分才視為需要
#     護理站注意，對應 priority 2→yellow、3→red。
#   - 體溫沿用 NEWS2 雙向設計（過冷/過熱都扣分），比單一高溫門檻更適合高齡
#     族群（老年人發燒反應會鈍化，體溫過低反而常是更危險的訊號）。

from dataclasses import dataclass
from typing import Optional

from app.schemas import Priority, Vitals

_ALERT_PRIORITY: dict[int, Priority] = {2: "yellow", 3: "red"}


@dataclass
class VitalsAlert:
    priority: Priority
    reason: str


def _spo2_score(spo2: int) -> tuple[int, str]:
    if spo2 <= 91:
        return 3, f"血氧過低 ({spo2}%)"
    if spo2 <= 93:
        return 2, f"血氧偏低 ({spo2}%)"
    if spo2 <= 95:
        return 1, f"血氧輕微偏低 ({spo2}%)"
    return 0, ""


def _bp_systolic_score(sbp: int) -> tuple[int, str]:
    if sbp <= 90:
        return 3, f"血壓過低 ({sbp} mmHg)"
    if sbp >= 220:
        return 3, f"血壓過高 ({sbp} mmHg)"
    if sbp <= 100:
        return 2, f"血壓偏低 ({sbp} mmHg)"
    if sbp <= 110:
        return 1, f"血壓輕微偏低 ({sbp} mmHg)"
    return 0, ""


def _heart_rate_score(hr: int) -> tuple[int, str]:
    if hr <= 40:
        return 3, f"心跳過緩 ({hr} bpm)"
    if hr >= 131:
        return 3, f"心跳過快 ({hr} bpm)"
    if hr <= 50:
        return 1, f"心跳輕微偏緩 ({hr} bpm)"
    if hr <= 90:
        return 0, ""
    if hr <= 110:
        return 1, f"心跳輕微偏快 ({hr} bpm)"
    return 2, f"心跳偏快 ({hr} bpm)"


def _temperature_score(temp: float) -> tuple[int, str]:
    if temp <= 35.0:
        return 3, f"體溫過低 ({temp}°C)"
    if temp >= 39.1:
        return 2, f"體溫過高 ({temp}°C)"
    if temp <= 36.0:
        return 1, f"體溫輕微偏低 ({temp}°C)"
    if temp <= 38.0:
        return 0, ""
    return 1, f"體溫輕微偏高 ({temp}°C)"


def evaluate_vitals(vitals: Vitals) -> Optional[VitalsAlert]:
    """回傳單項最高分（NEWS2 風格）對應的 alert；四項都 ≤1 分（正常/低風險）回傳 None。"""
    scored = [
        _spo2_score(vitals.spo2),
        _bp_systolic_score(vitals.bp_systolic),
        _heart_rate_score(vitals.heart_rate),
        _temperature_score(vitals.temperature),
    ]
    top_score, top_reason = max(scored, key=lambda item: item[0])
    priority = _ALERT_PRIORITY.get(top_score)
    if priority is None:
        return None
    return VitalsAlert(priority=priority, reason=top_reason)

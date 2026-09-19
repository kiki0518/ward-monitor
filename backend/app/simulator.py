# demo 用的背景模擬任務。
#
# 現在真實鏡頭/behavior_engine/ward_agent 都還沒接上，store 裡的資料
# seed 完就不會再變，Overview/RoomDetail 頁面看起來會像死掉一樣。這個模組讓
# vitals 隨時間小幅波動、事件偶爾冒出來/被解決，demo 起來才有東西可以看。
#
# 之後真實邏輯做好，把這兩個背景任務關掉，換成真實資料寫進 store 即可，
# REST/WebSocket 的介面不用動。

import asyncio
import random
import uuid
from datetime import datetime, timezone

from app import store
from app.schemas import EventLocation, EventState, Priority, WardAgentOutput

# (state, reason, location) 的假事件劇本庫，模擬 Ward Agent 判斷出的結果
_EVENT_LIBRARY: list[tuple[EventState, str, EventLocation]] = [
    ("bed_exit", "夜間離床超過 5 分鐘", "out_of_bed"),
    ("possible_fall", "疑似跌倒", "out_of_bed"),
    ("abnormal_transition", "偵測到異常姿勢轉換", "in_bed"),
    ("prolonged_sitting", "長時間維持坐姿", "chair"),
    ("night_wandering", "夜間遊蕩", "near_door"),
    ("abnormal_vitals", "生理數據異常", "in_bed"),
]


def _jitter(value: float, spread: float, low: float, high: float) -> float:
    return max(low, min(high, value + random.uniform(-spread, spread)))


async def run_vitals_jitter(interval_seconds: float = 2.0) -> None:
    """每個床位的生理數據隨時間小幅波動，模擬 vitals_simulator 之後要做的事。"""
    while True:
        for bed in store.get_all_beds():
            vitals = store.get_vitals(bed.bed_id)
            if vitals is None:
                continue
            store.set_vitals(
                bed.bed_id,
                bp_systolic=round(_jitter(vitals.bp_systolic, 3, 90, 150)),
                bp_diastolic=round(_jitter(vitals.bp_diastolic, 2, 55, 95)),
                temperature=round(_jitter(vitals.temperature, 0.1, 35.5, 38.5), 1),
                heart_rate=round(_jitter(vitals.heart_rate, 4, 50, 130)),
                spo2=round(_jitter(vitals.spo2, 1, 90, 100)),
            )
        await asyncio.sleep(interval_seconds)


async def run_event_script(interval_seconds: float = 12.0) -> None:
    """每隔一段時間，隨機讓某床冒出一個新事件，或解決掉一個既有事件。"""
    while True:
        await asyncio.sleep(interval_seconds)
        beds = store.get_all_beds()
        if not beds:
            continue

        if random.random() < 0.5:
            candidates = [b for b in beds if not store.get_active_events(b.bed_id)] or beds
            bed = random.choice(candidates)
            state, reason, location = random.choice(_EVENT_LIBRARY)
            priority: Priority = "red" if state == "possible_fall" else random.choice(["yellow", "red"])
            store.add_event(
                WardAgentOutput(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    bed_id=bed.bed_id,
                    state=state,
                    priority=priority,
                    reason=reason,
                    location=location,
                    action="請護理師查看",
                    started_at=datetime.now(timezone.utc),
                    resolved_at=None,
                )
            )
        else:
            active_beds = [b for b in beds if store.get_active_events(b.bed_id)]
            if active_beds:
                bed = random.choice(active_beds)
                event = random.choice(store.get_active_events(bed.bed_id))
                store.resolve_event(event.event_id)

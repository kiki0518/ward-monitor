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

from app import store
from app.location_rules import evaluate_location
from app.schemas import EventLocation, EventState, Priority
from app.vitals_scoring import evaluate_vitals

# (state, reason, location) 的假事件劇本庫，模擬 Ward Agent 判斷出的結果
# 注意：abnormal_vitals、night_wandering、prolonged_bathroom 都不在這裡——這三個
# 現在各自由 run_vitals_alerting / run_location_alerting 依實際數據（vitals 門檻、
# 離床/如廁持續時間）產生，不用隨機劇本，避免兩邊各自開一筆互相打架。
_EVENT_LIBRARY: list[tuple[EventState, str, EventLocation]] = [
    ("bed_exit", "夜間離床超過 5 分鐘", "out_of_bed"),
    ("possible_fall", "疑似跌倒", "out_of_bed"),
    ("abnormal_transition", "偵測到異常姿勢轉換", "in_bed"),
    ("prolonged_sitting", "長時間維持坐姿", "chair"),
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


async def run_vitals_alerting(interval_seconds: float = 2.0) -> None:
    """依 NEWS2 改編門檻（見 app/vitals_scoring.py）持續評估每床目前的 vitals：
    數值異常就開新的/更新既有的 abnormal_vitals 事件，恢復正常就自動解除。"""
    while True:
        for bed in store.get_all_beds():
            vitals = store.get_vitals(bed.bed_id)
            if vitals is None:
                continue
            alert = evaluate_vitals(vitals)
            if alert is None:
                for event in store.get_active_events(bed.bed_id):
                    if event.state == "abnormal_vitals":
                        store.auto_resolve_event(event.event_id)
            else:
                store.report_event(
                    bed.bed_id,
                    state="abnormal_vitals",
                    priority=alert.priority,
                    reason=alert.reason,
                    location="in_bed",
                    action="請護理師查看",
                )
        await asyncio.sleep(interval_seconds)


async def run_bathroom_jitter(interval_seconds: float = 20.0, toggle_probability: float = 0.1) -> None:
    """Mock 廁所 sensor：demo 用，模擬病患偶爾進出廁所（真的感測器接上後這個任務就不用了，
    直接呼叫 store.set_in_bathroom() 寫入真實訊號即可，REST/WebSocket 介面不用動）。"""
    while True:
        for bed in store.get_all_beds():
            if bed.bed_id != "101" and random.random() < toggle_probability:
                store.set_in_bathroom(bed.bed_id, not store.get_in_bathroom(bed.bed_id))
        await asyncio.sleep(interval_seconds)


async def run_location_alerting(interval_seconds: float = 5.0) -> None:
    """持續評估每床目前離床/如廁多久（見 app/location_rules.py 的門檻）：
    超過門檻就開新的/更新既有的事件，回到床上／離開廁所就自動解除。"""
    tracked_states = {"night_wandering", "prolonged_bathroom"}
    while True:
        for bed in store.get_all_beds():
            location = store.get_location(bed.bed_id)
            duration = store.get_location_duration(bed.bed_id)
            alert = evaluate_location(location, duration)
            if alert is None:
                for event in store.get_active_events(bed.bed_id):
                    if event.state in tracked_states:
                        store.auto_resolve_event(event.event_id)
            else:
                store.report_event(
                    bed.bed_id,
                    state=alert.state,
                    priority=alert.priority,
                    reason=alert.reason,
                    location=alert.location,
                    action="請護理師查看",
                )
        await asyncio.sleep(interval_seconds)


async def run_event_script(interval_seconds: float = 12.0) -> None:
    """每隔一段時間，隨機讓某床冒出一個新事件。
    不會自動解決事件——事件唯一消失的方式是護理站在前端手動「標記已處理」（或「誤觸」，
    純前端行為），這樣測試時畫面上的變化才是可預期的，不會跟背景模擬互相干擾。"""
    while True:
        await asyncio.sleep(interval_seconds)
        beds = [bed for bed in store.get_all_beds() if bed.bed_id != "101"]
        if not beds:
            continue

        candidates = [b for b in beds if not store.get_active_events(b.bed_id)] or beds
        bed = random.choice(candidates)
        state, reason, location = random.choice(_EVENT_LIBRARY)
        priority: Priority = "red" if state == "possible_fall" else random.choice(["yellow", "red"])
        store.report_event(
            bed.bed_id,
            state=state,
            priority=priority,
            reason=reason,
            location=location,
            action="請護理師查看",
        )

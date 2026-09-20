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
from datetime import datetime, timedelta, timezone

from app import store
from app.location_rules import evaluate_location
from app.schemas import EventLocation, EventState, Posture, Priority
from app.vitals_scoring import evaluate_vitals

_POSTURE_CHOICES: list[Posture] = ["standing", "sitting", "lying"]

# (state, reason, location, 抽中權重) 的假事件劇本庫，模擬 Ward Agent 判斷出的結果。
# 權重刻意壓低 possible_fall——demo 背景樓層應該大多是綠燈、偶爾黃燈，紅燈（疑似
# 跌倒）只是極少數，不然滿版紅色會蓋過真正該注意的 101。
# 注意：abnormal_vitals、night_wandering、prolonged_bathroom 都不在這裡——這三個
# 現在各自由 run_vitals_alerting / run_location_alerting 依實際數據（vitals 門檻、
# 離床/如廁持續時間）產生，不用隨機劇本，避免兩邊各自開一筆互相打架。
_EVENT_LIBRARY: list[tuple[EventState, str, EventLocation, int]] = [
    ("bed_exit", "夜間離床超過 5 分鐘", "out_of_bed", 35),
    ("possible_fall", "疑似跌倒", "out_of_bed", 5),
    ("abnormal_transition", "偵測到異常姿勢轉換", "in_bed", 30),
    ("prolonged_sitting", "長時間維持坐姿", "chair", 30),
]
_RANDOM_EVENT_STATES = {state for state, _, _, _ in _EVENT_LIBRARY}
# 這幾個是 run_event_script 自己開的、沒有真實資料在背後持續驗證，不會像
# abnormal_vitals/night_wandering 那樣數值一恢復正常就自動解除，所以要自己訂個
# 存活時間到期自動清除，不然背景事件只會一直累積，最後所有床都變黃/紅。
_RANDOM_EVENT_LIFETIME = timedelta(minutes=5)
# 每次 tick 只有這個機率會真的冒出一筆新事件，搭配上面的存活期限，長時間跑下來
# 平均同時存在的背景事件數 ≈ (機率/interval) * 存活秒數，抓在個位數，符合「絕大多數
# 綠燈、零星黃燈、一兩個紅燈」的 demo 觀感。
_EVENT_TRIGGER_PROBABILITY = 0.12

# 生理數值假資料的健康基準值（對應 store.seed_demo_data() 的 seed 值）；隨機漫步
# 每次都會被拉回基準值一點，避免無界隨機漫步長時間下來到處飄進異常區間。
_VITALS_BASELINE = dict(bp_systolic=120, bp_diastolic=80, temperature=36.6, heart_rate=75, spo2=97)
_VITALS_PULL = 0.05


def _jitter(value: float, spread: float, low: float, high: float, baseline: float) -> float:
    pulled = value + _VITALS_PULL * (baseline - value)
    return max(low, min(high, pulled + random.uniform(-spread, spread)))


async def run_vitals_jitter(interval_seconds: float = 2.0) -> None:
    """每個床位的生理數據隨時間小幅波動，模擬 vitals_simulator 之後要做的事。
    帶一點拉回基準值的力道（見 _VITALS_PULL），數值多數時間維持在健康範圍附近，
    只是偶爾隨機飄出去，不會長時間下來到處都遊走到異常區間。"""
    while True:
        for bed in store.get_all_beds():
            vitals = store.get_vitals(bed.bed_id)
            if vitals is None:
                continue
            store.set_vitals(
                bed.bed_id,
                bp_systolic=round(_jitter(vitals.bp_systolic, 3, 90, 150, _VITALS_BASELINE["bp_systolic"])),
                bp_diastolic=round(_jitter(vitals.bp_diastolic, 2, 55, 95, _VITALS_BASELINE["bp_diastolic"])),
                temperature=round(_jitter(vitals.temperature, 0.1, 35.5, 38.5, _VITALS_BASELINE["temperature"]), 1),
                heart_rate=round(_jitter(vitals.heart_rate, 4, 50, 130, _VITALS_BASELINE["heart_rate"])),
                spo2=round(_jitter(vitals.spo2, 1, 90, 100, _VITALS_BASELINE["spo2"])),
            )
        await asyncio.sleep(interval_seconds)


async def run_posture_jitter(interval_seconds: float = 15.0, change_probability: float = 0.3) -> None:
    """Mock 姿勢/in_camera：demo 用，模擬病患姿勢偶爾改變、偶爾整個人離開鏡頭範圍。
    1 樓展示樓層（store.is_demo_floor_bed）完全不會被這個任務動到：101 的
    current_posture/in_camera 只能來自 /ws/room/{bed_id}?role=board 的真實資料，
    102/103 等其他 1 樓床是手動觸發的展示床，兩種都不該被隨機亂數蓋掉。"""
    while True:
        for bed in store.get_all_beds():
            if store.is_demo_floor_bed(bed.bed_id):
                continue
            if random.random() < change_probability:
                if random.random() < 0.15:
                    # 偶爾整個人離開鏡頭範圍：現實中「看不到人」時姿勢也判斷不出來
                    store.set_in_camera(bed.bed_id, False)
                    store.set_posture(bed.bed_id, None)
                else:
                    store.set_in_camera(bed.bed_id, True)
                    store.set_posture(bed.bed_id, random.choice(_POSTURE_CHOICES))
        await asyncio.sleep(interval_seconds)


async def run_vitals_alerting(interval_seconds: float = 2.0) -> None:
    """依 NEWS2 改編門檻（見 app/vitals_scoring.py）持續評估每床目前的 vitals：
    數值異常就開新的/更新既有的 abnormal_vitals 事件，恢復正常就自動解除。
    1 樓展示樓層排除在外——vitals 數字還是會跳（run_vitals_jitter 不受影響，畫面才不會
    看起來死掉），但不會因為亂數剛好跳過門檻就冒出計畫外的事件打亂 demo 節奏。"""
    while True:
        for bed in store.get_all_beds():
            if store.is_demo_floor_bed(bed.bed_id):
                continue
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
    直接呼叫 store.set_in_bathroom() 寫入真實訊號即可，REST/WebSocket 介面不用動）。
    1 樓展示樓層排除在外，理由同 run_posture_jitter。"""
    while True:
        for bed in store.get_all_beds():
            if store.is_demo_floor_bed(bed.bed_id):
                continue
            if random.random() < toggle_probability:
                store.set_in_bathroom(bed.bed_id, not store.get_in_bathroom(bed.bed_id))
        await asyncio.sleep(interval_seconds)


async def run_location_alerting(interval_seconds: float = 5.0) -> None:
    """持續評估每床目前離床/如廁多久（見 app/location_rules.py 的門檻）：
    超過門檻就開新的/更新既有的事件，回到床上／離開廁所就自動解除。
    1 樓展示樓層排除在外，理由同 run_posture_jitter。"""
    tracked_states = {"night_wandering", "prolonged_bathroom"}
    while True:
        for bed in store.get_all_beds():
            if store.is_demo_floor_bed(bed.bed_id):
                continue
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
    """背景樓層的事件劇本：每個 tick 有 _EVENT_TRIGGER_PROBABILITY 的機率讓隨機一床
    冒出一個新事件，且它自己開的事件會在 _RANDOM_EVENT_LIFETIME 後自動解除——這兩者
    加起來讓同時存在的背景事件數維持在個位數（絕大多數綠燈、零星黃燈、極少數紅燈），
    不會因為只開不關而隨時間單調累積到所有床都變黃/紅。護理站在前端手動「標記已處理」
    （或「誤觸」，純前端行為）一樣可以隨時提前清掉。
    1 樓展示樓層排除在外，理由同 run_posture_jitter：101 的事件要嘛來自真的板子，要嘛用
    scripts/trigger_*.py 手動觸發，102~124 則是刻意維持乾淨、永遠綠燈的對照組。"""
    while True:
        await asyncio.sleep(interval_seconds)
        beds = [b for b in store.get_all_beds() if not store.is_demo_floor_bed(b.bed_id)]
        if not beds:
            continue

        now = datetime.now(timezone.utc)
        for bed in beds:
            for event in store.get_active_events(bed.bed_id):
                if event.state in _RANDOM_EVENT_STATES and now - event.started_at >= _RANDOM_EVENT_LIFETIME:
                    store.auto_resolve_event(event.event_id)

        if random.random() >= _EVENT_TRIGGER_PROBABILITY:
            continue

        bed = random.choice(beds)
        state, reason, location, _weight = random.choices(
            _EVENT_LIBRARY, weights=[w for *_, w in _EVENT_LIBRARY], k=1
        )[0]
        priority: Priority = "red" if state == "possible_fall" else random.choices(
            ["yellow", "red"], weights=[9, 1], k=1
        )[0]
        store.report_event(
            bed.bed_id,
            state=state,
            priority=priority,
            reason=reason,
            location=location,
            action="請護理師查看",
        )

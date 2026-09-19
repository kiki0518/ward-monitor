# B3 負責：in-memory 資料存放
# 「房間目前狀態」(RoomState) 跟「事件歷史」(Event Store) 分開存。
# risk_level 不存在 RoomState 裡：risk 只屬於事件，room 沒有自己的 risk 欄位，
# 查詢時一律從這個 bed_id 最新一筆事件動態算出來，見 get_risk_level()。
#
# 目前用假資料塞滿這個 store，之後 B1(MQTT)/B2(behavior_engine, ward_agent)/
# vitals_simulator 的邏輯做好了，換成呼叫 update_room()/add_event() 寫入即可，
# REST/WebSocket 的介面完全不用動。

from datetime import datetime, timezone
from typing import Optional

from app.schemas import (
    EventEntry,
    HabitBaseline,
    MedicalOrders,
    RoomState,
    Vitals,
)

_rooms: dict[str, RoomState] = {}
_events: dict[str, list[EventEntry]] = {}


def seed_demo_data() -> None:
    """Demo 用假資料：4-6 間房，1 間有已觸發的跌倒事件當劇本。"""
    _rooms.clear()
    _events.clear()

    now = datetime.now(timezone.utc)

    demo_rooms = [
        RoomState(
            bed_id="B203-1",
            patient_name="王OO",
            is_live=True,
            current_posture="lying",
            latest_keypoints=None,
            latest_vitals=Vitals(bp_systolic=132, bp_diastolic=85, temperature=36.7, heart_rate=78, spo2=97),
            habit_baseline=HabitBaseline(usual_wake_time="06:30", usual_bathroom_duration_min=3),
            medical_orders=MedicalOrders(no_leg_raise=True),
            last_updated=now,
        ),
        RoomState(
            bed_id="B203-2",
            patient_name="陳OO",
            is_live=False,
            current_posture="lying",
            latest_keypoints=None,
            latest_vitals=Vitals(bp_systolic=145, bp_diastolic=92, temperature=37.1, heart_rate=88, spo2=95),
            habit_baseline=HabitBaseline(usual_wake_time="07:00", usual_bathroom_duration_min=5),
            medical_orders=MedicalOrders(no_leg_raise=False),
            last_updated=now,
        ),
        RoomState(
            bed_id="B204-1",
            patient_name="林OO",
            is_live=False,
            current_posture="sitting",
            latest_keypoints=None,
            latest_vitals=Vitals(bp_systolic=118, bp_diastolic=76, temperature=36.5, heart_rate=72, spo2=98),
            habit_baseline=HabitBaseline(usual_wake_time="06:00", usual_bathroom_duration_min=4),
            medical_orders=MedicalOrders(no_leg_raise=False),
            last_updated=now,
        ),
        RoomState(
            bed_id="B204-2",
            patient_name="張OO",
            is_live=False,
            current_posture="walking",
            latest_keypoints=None,
            latest_vitals=Vitals(bp_systolic=125, bp_diastolic=80, temperature=36.8, heart_rate=75, spo2=97),
            habit_baseline=HabitBaseline(usual_wake_time="05:45", usual_bathroom_duration_min=3),
            medical_orders=MedicalOrders(no_leg_raise=True),
            last_updated=now,
        ),
        RoomState(
            bed_id="B205-1",
            patient_name="黃OO",
            is_live=False,
            current_posture="standing",
            latest_keypoints=None,
            latest_vitals=Vitals(bp_systolic=130, bp_diastolic=84, temperature=36.6, heart_rate=80, spo2=96),
            habit_baseline=HabitBaseline(usual_wake_time="06:15", usual_bathroom_duration_min=4),
            medical_orders=MedicalOrders(no_leg_raise=False),
            last_updated=now,
        ),
    ]

    for room in demo_rooms:
        _rooms[room.bed_id] = room
        _events[room.bed_id] = []

    # 劇本：B203-2 已經發生過一次跌倒事件，讓 demo 一開始就有一間房是 high risk
    _events["B203-2"].append(
        EventEntry(
            event_id="evt_20260919_0220",
            bed_id="B203-2",
            timestamp=now,
            event="POSSIBLE_FALL",
            risk="high",
            reason="偵測到跌倒姿勢，且該病患有跌倒病史，事發於凌晨時段",
            priority=1,
            action="立即通知當班護理師，同步記錄事件",
        )
    )


def get_all_rooms() -> list[RoomState]:
    return list(_rooms.values())


def get_room(bed_id: str) -> Optional[RoomState]:
    return _rooms.get(bed_id)


def room_exists(bed_id: str) -> bool:
    return bed_id in _rooms


def get_events(bed_id: str, limit: int = 50) -> list[EventEntry]:
    events = _events.get(bed_id, [])
    return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]


def get_risk_level(bed_id: str) -> str:
    """risk 只屬於事件：取最新一筆事件的 risk，完全沒有事件時是 normal。"""
    events = _events.get(bed_id, [])
    if not events:
        return "normal"
    latest = max(events, key=lambda e: e.timestamp)
    return latest.risk

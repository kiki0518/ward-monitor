# in-memory 資料存放，對應 API_CONTRACT.md
#
# 三種資料分開存：
#   - _beds：床位靜態名冊 (BedInfo)，從 app/data/beds.csv 讀入，GET /api/beds 用
#   - _vitals：每個床位最新一筆生理數據 (Vitals)
#   - _events：每個床位的事件列表 (WardAgentOutput)，resolved_at 為 None 代表 active
#
# OverviewUpdate 的 priority/reason 不是獨立儲存的欄位：從該床目前 active
# （resolved_at is None）的事件裡取 priority 最高的一筆；沒有 active 事件時
# 固定是 green /「生理數據正常」。

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.schemas import BedInfo, OverviewUpdate, Vitals, WardAgentOutput

_PRIORITY_RANK = {"green": 0, "yellow": 1, "red": 2}
_GENDER_FROM_CSV = {"男": "male", "女": "female"}
_BEDS_CSV_PATH = Path(__file__).parent / "data" / "beds.csv"

_beds: dict[str, BedInfo] = {}
_vitals: dict[str, Vitals] = {}
_events: dict[str, list[WardAgentOutput]] = {}


def _load_beds_from_csv() -> list[BedInfo]:
    with _BEDS_CSV_PATH.open(encoding="utf-8") as f:
        return [
            BedInfo(
                bed_id=row["bed_id"],
                patient_name=row["patient_name"],
                gender=_GENDER_FROM_CSV[row["gender"]],
                age=int(row["age"]),
                diagnosis=row["diagnosis"],
            )
            for row in csv.DictReader(f)
        ]


def seed_demo_data() -> None:
    """Demo 用假資料：床位名冊從 beds.csv 讀入，103 有一筆尚未處理的疑似跌倒事件當劇本。"""
    _beds.clear()
    _vitals.clear()
    _events.clear()

    now = datetime.now(timezone.utc)

    for bed in _load_beds_from_csv():
        _beds[bed.bed_id] = bed
        _events[bed.bed_id] = []
        _vitals[bed.bed_id] = Vitals(
            bed_id=bed.bed_id,
            bp_systolic=120,
            bp_diastolic=80,
            temperature=36.6,
            heart_rate=75,
            spo2=97,
            ts=now,
        )

    _events["103"].append(
        WardAgentOutput(
            event_id="evt_8f2a",
            bed_id="103",
            state="possible_fall",
            priority="red",
            reason="疑似跌倒",
            location="out_of_bed",
            action="請護理師查看",
            started_at=now,
            resolved_at=None,
        )
    )


def get_all_beds() -> list[BedInfo]:
    return list(_beds.values())


def bed_exists(bed_id: str) -> bool:
    return bed_id in _beds


def get_vitals(bed_id: str) -> Optional[Vitals]:
    return _vitals.get(bed_id)


def set_vitals(
    bed_id: str,
    *,
    bp_systolic: int,
    bp_diastolic: int,
    temperature: float,
    heart_rate: int,
    spo2: int,
) -> None:
    _vitals[bed_id] = Vitals(
        bed_id=bed_id,
        bp_systolic=bp_systolic,
        bp_diastolic=bp_diastolic,
        temperature=temperature,
        heart_rate=heart_rate,
        spo2=spo2,
        ts=datetime.now(timezone.utc),
    )


def add_event(event: WardAgentOutput) -> None:
    _events.setdefault(event.bed_id, []).append(event)


def get_active_events(bed_id: str) -> list[WardAgentOutput]:
    return [event for event in _events.get(bed_id, []) if event.resolved_at is None]


def get_event(event_id: str) -> Optional[WardAgentOutput]:
    for events in _events.values():
        for event in events:
            if event.event_id == event_id:
                return event
    return None


def resolve_event(event_id: str) -> Optional[WardAgentOutput]:
    event = get_event(event_id)
    if event is None:
        return None
    event.resolved_at = datetime.now(timezone.utc)
    return event


def get_overview(bed_id: str) -> OverviewUpdate:
    active = get_active_events(bed_id)
    if not active:
        return OverviewUpdate(
            bed_id=bed_id,
            priority="green",
            reason="生理數據正常",
            updated_at=datetime.now(timezone.utc),
        )
    top = max(active, key=lambda event: _PRIORITY_RANK[event.priority])
    return OverviewUpdate(
        bed_id=bed_id,
        priority=top.priority,
        reason=top.reason,
        updated_at=datetime.now(timezone.utc),
    )


def get_all_overviews() -> list[OverviewUpdate]:
    return [get_overview(bed_id) for bed_id in _beds]

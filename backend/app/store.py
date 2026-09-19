# in-memory 資料存放，對應 API_CONTRACT.md
#
# 三種資料分開存：
#   - _beds：床位靜態名冊 (BedInfo)，從 app/data/beds.csv 讀入，GET /api/beds 用
#   - _vitals：每個床位最新一筆生理數據 (Vitals)
#   - _events：每個床位的事件列表 (WardAgentOutput)，resolved_at 為 None 代表 active。
#     resolved 之後不會被清除（demo scope 不做 retention），但 GET /api/beds/{bed_id}/events
#     只回傳還 active 的，resolved 的不會出現在查詢結果裡，也沒有其他方式能查到它們
#
# OverviewUpdate 的 priority/reason/active_event_count 不是獨立儲存的欄位：從該床
# 目前 active（resolved_at is None）的事件動態算出來；沒有 active 事件時固定是
# green /「生理數據正常」/ 0。

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.schemas import (
    BedInfo,
    CaseReport,
    EventLocation,
    EventState,
    OverviewUpdate,
    Priority,
    Vitals,
    WardAgentOutput,
)

_PRIORITY_RANK = {"green": 0, "yellow": 1, "red": 2}
_GENDER_FROM_CSV = {"男": "male", "女": "female"}
_BEDS_CSV_PATH = Path(__file__).parent / "data" / "beds.csv"
_EVENT_HISTORY_JSON_PATH = Path(__file__).parent / "data" / "event_history.json"
_CASE_REPORTS_JSON_PATH = Path(__file__).parent / "data" / "case_reports.json"

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


def _generate_event_id(started_at: datetime) -> str:
    return f"evt_{started_at.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}"


def _init_event_history_file() -> None:
    """每次啟動都清空事件歷史 JSON 檔案：只記錄這次執行期間處理過的事件，不是跨重啟的永久紀錄。"""
    _EVENT_HISTORY_JSON_PATH.write_text("[]", encoding="utf-8")


def _append_to_event_history_file(event: WardAgentOutput) -> None:
    history = json.loads(_EVENT_HISTORY_JSON_PATH.read_text(encoding="utf-8"))
    history.append(event.model_dump(mode="json"))
    _EVENT_HISTORY_JSON_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _init_case_reports_file() -> None:
    """每次啟動都清空病例紀錄 JSON 檔案：只記錄這次執行期間護理站填寫的紀錄。"""
    _CASE_REPORTS_JSON_PATH.write_text("[]", encoding="utf-8")


def _append_to_case_reports_file(report: CaseReport) -> None:
    reports = json.loads(_CASE_REPORTS_JSON_PATH.read_text(encoding="utf-8"))
    reports.append(report.model_dump(mode="json"))
    _CASE_REPORTS_JSON_PATH.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


def get_case_reports() -> list[CaseReport]:
    reports = json.loads(_CASE_REPORTS_JSON_PATH.read_text(encoding="utf-8"))
    return [CaseReport(**r) for r in reports]


def clear_case_reports() -> None:
    """匯出報告之後呼叫：清空 case_reports.json，避免下次匯出重複包含同一批病例。"""
    _init_case_reports_file()


def seed_demo_data() -> None:
    """Demo 用假資料：床位名冊從 beds.csv 讀入，103 有一筆尚未處理的疑似跌倒事件當劇本。"""
    _beds.clear()
    _vitals.clear()
    _events.clear()
    _init_event_history_file()
    _init_case_reports_file()

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

    report_event(
        "103",
        state="possible_fall",
        priority="red",
        reason="疑似跌倒",
        location="out_of_bed",
        action="請護理師查看",
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


def report_event(
    bed_id: str,
    *,
    state: EventState,
    priority: Priority,
    reason: str,
    location: EventLocation,
    action: Optional[str] = None,
) -> WardAgentOutput:
    """回報一次偵測結果。

    同一個 (bed_id, state) 若已經有一筆 active（resolved_at is None）事件，
    更新既有那筆的 reason/priority/location/last_seen_at，不開新的
    event_id；started_at 保持第一次偵測到的時間不變。location 不算在去重
    key 裡，因為同一件事發展過程中 location 本來就可能改變。
    """
    now = datetime.now(timezone.utc)
    for event in _events.get(bed_id, []):
        if event.state == state and event.resolved_at is None:
            event.priority = priority
            event.reason = reason
            event.location = location
            event.action = action
            event.last_seen_at = now
            return event

    event = WardAgentOutput(
        event_id=_generate_event_id(now),
        bed_id=bed_id,
        state=state,
        priority=priority,
        reason=reason,
        location=location,
        action=action,
        started_at=now,
        last_seen_at=now,
        resolved_at=None,
    )
    _events.setdefault(bed_id, []).append(event)
    return event


def get_active_events(bed_id: str) -> list[WardAgentOutput]:
    return [event for event in _events.get(bed_id, []) if event.resolved_at is None]


def get_event_history(bed_id: str) -> list[WardAgentOutput]:
    """該床目前 active 的事件，priority 高到低排序，同 priority 內新到舊（不含已 resolved 的）。
    不分頁：demo 規模一張床頂多幾筆。"""
    return sorted(
        get_active_events(bed_id),
        key=lambda event: (_PRIORITY_RANK[event.priority], event.started_at),
        reverse=True,
    )


def get_resolved_events(bed_id: str) -> list[WardAgentOutput]:
    """該床已處理的事件（resolved_at 不為 None），依 resolved_at 新到舊排序。不分頁。"""
    resolved = [event for event in _events.get(bed_id, []) if event.resolved_at is not None]
    return sorted(resolved, key=lambda event: event.resolved_at, reverse=True)


def get_event(event_id: str) -> Optional[WardAgentOutput]:
    for events in _events.values():
        for event in events:
            if event.event_id == event_id:
                return event
    return None


def resolve_event(
    event_id: str, *, completed_actions: str, follow_up: str, notes: str = ""
) -> Optional[WardAgentOutput]:
    """Idempotent：已經是 resolved 的事件再呼叫一次，直接回傳目前狀態，不覆寫 resolved_at、
    也不會重複寫入 event_history.json / case_reports.json（即使這次傳的內容不一樣）。"""
    event = get_event(event_id)
    if event is None:
        return None
    if event.resolved_at is None:
        event.resolved_at = datetime.now(timezone.utc)
        _append_to_event_history_file(event)
        _append_to_case_reports_file(
            CaseReport(
                event_id=event.event_id,
                bed_id=event.bed_id,
                completed_actions=completed_actions,
                follow_up=follow_up,
                notes=notes,
                resolved_at=event.resolved_at,
            )
        )
    return event


def get_overview(bed_id: str) -> OverviewUpdate:
    active = get_active_events(bed_id)
    if not active:
        return OverviewUpdate(
            bed_id=bed_id,
            priority="green",
            reason="生理數據正常",
            active_event_count=0,
            updated_at=datetime.now(timezone.utc),
        )
    top = max(active, key=lambda event: _PRIORITY_RANK[event.priority])
    return OverviewUpdate(
        bed_id=bed_id,
        priority=top.priority,
        reason=top.reason,
        active_event_count=len(active),
        # 用該事件實際開始的時間，不是「這次算出摘要」的時間，這樣前端才能正確
        # 顯示「異常已持續多久」，不會因為 /ws/overview 每次推送都重算而永遠是剛剛
        updated_at=top.started_at,
    )


def get_all_overviews() -> list[OverviewUpdate]:
    return [get_overview(bed_id) for bed_id in _beds]

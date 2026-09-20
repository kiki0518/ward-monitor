# in-memory 資料存放，對應 API_CONTRACT.md
#
# 七種資料分開存：
#   - _beds：床位靜態名冊 (BedInfo)，從 app/data/beds.csv 讀入，GET /api/beds 用
#   - _vitals：每個床位最新一筆生理數據 (Vitals)
#   - _postures：每個床位目前姿勢，board 算好直接傳過來，這裡只是存放/轉發，不做分類
#   - _in_camera：board 是否在畫面裡偵測到人（True/False/None＝還沒收過 board 資料）
#   - _in_bathroom：mock 廁所 sensor，是否偵測到病患在廁所（demo 用假資料，見 simulator.py）
#   - _location_since：目前 get_location() 的結果從什麼時候開始維持（用來算「已經多久」）
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.schemas import (
    BedInfo,
    CaseReport,
    EventLocation,
    EventState,
    OverviewUpdate,
    Posture,
    Priority,
    Vitals,
    WardAgentOutput,
)

# demo 唯一接真的板子的床（見 API_CONTRACT.md/BOARD_API_SPEC.md 的慣例）。
# current_posture/in_camera 只有這床應該來自 /ws/room/{bed_id}?role=board 的真實資料；
# 其他床由 simulator.run_posture_jitter 產生假資料，兩者不會互相覆蓋。
REAL_BOARD_BED_ID = "101"

# 1 樓（101~124）是精心佈置的展示樓層：不跑任何隨機模擬任務（姿勢/廁所/事件亂數劇本），
# 只能靠手動觸發（possible-fall / demo-event）或真的板子（101）產生資料，demo 現場才不會
# 冒出計畫外的事件打亂節奏。2 樓以上維持完全隨機，當作 Overview 頁面的背景氣氛。
_DEMO_FLOOR_PREFIX = "1"


def is_demo_floor_bed(bed_id: str) -> bool:
    return bed_id.startswith(_DEMO_FLOOR_PREFIX)


_PRIORITY_RANK = {"green": 0, "yellow": 1, "red": 2}
_GENDER_FROM_CSV = {"男": "male", "女": "female"}
_BEDS_CSV_PATH = Path(__file__).parent / "data" / "beds.csv"
_EVENT_HISTORY_JSON_PATH = Path(__file__).parent / "data" / "event_history.json"
_CASE_REPORTS_JSON_PATH = Path(__file__).parent / "data" / "case_reports.json"

_beds: dict[str, BedInfo] = {}
_vitals: dict[str, Vitals] = {}
_postures: dict[str, Optional[Posture]] = {}
_in_camera: dict[str, Optional[bool]] = {}
_in_bathroom: dict[str, bool] = {}
_location_since: dict[str, tuple[EventLocation, datetime]] = {}
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
                assigned_nurse=row.get("assigned_nurse") or None,
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
    _postures.clear()
    _in_camera.clear()
    _in_bathroom.clear()
    _location_since.clear()
    _events.clear()
    _init_event_history_file()
    _init_case_reports_file()

    now = datetime.now(timezone.utc)

    for bed in _load_beds_from_csv():
        _beds[bed.bed_id] = bed
        _events[bed.bed_id] = []
        # 預設躺在床上（demo 合理預設值），board 真的連上會直接覆寫；不用 None，
        # 不然每張模擬床永遠不會被判定為「在床上」，夜遊規則會對所有模擬床誤發事件
        _postures[bed.bed_id] = "lying"
        _in_camera[bed.bed_id] = None
        _in_bathroom[bed.bed_id] = False
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


def get_all_nurses() -> list[str]:
    """從床位名冊的 assigned_nurse 欄位去重取得護理師名單，給前端選擇自己身分用。"""
    return sorted({bed.assigned_nurse for bed in _beds.values() if bed.assigned_nurse})


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


def get_posture(bed_id: str) -> Optional[Posture]:
    return _postures.get(bed_id)


def set_posture(bed_id: str, posture: Optional[Posture]) -> None:
    _postures[bed_id] = posture


def get_in_camera(bed_id: str) -> Optional[bool]:
    return _in_camera.get(bed_id)


def set_in_camera(bed_id: str, in_camera: bool) -> None:
    _in_camera[bed_id] = in_camera


def get_in_bathroom(bed_id: str) -> bool:
    return _in_bathroom.get(bed_id, False)


def set_in_bathroom(bed_id: str, in_bathroom: bool) -> None:
    _in_bathroom[bed_id] = in_bathroom


def get_location(bed_id: str) -> EventLocation:
    """從廁所 sensor + 目前姿勢推導病患現在大概在哪，純計算、不記錄歷史。

    廁所 sensor 優先：patient 進廁所後鏡頭通常照不到（隱私），posture 這時大概率是
    None/不是 lying，用廁所 sensor 蓋過去才對。躺著視為在床上；其餘（站/坐/沒在
    鏡頭裡/廁所 sensor 沒觸發）一律算離床。
    Board 的 unknown 傳為 None，也算離床；in_camera=True 不代表在床上。
    """
    if get_in_bathroom(bed_id):
        return "bathroom"
    if get_posture(bed_id) == "lying":
        return "in_bed"
    return "out_of_bed"


def get_location_duration(bed_id: str) -> timedelta:
    """回傳目前 get_location() 的結果已經維持多久；location 一改變，計時器歸零重算。
    設計成每次呼叫都會更新內部記錄，所以要由背景任務固定頻率呼叫，不是純函式。
    """
    now = datetime.now(timezone.utc)
    current = get_location(bed_id)
    tracked = _location_since.get(bed_id)
    if tracked is None or tracked[0] != current:
        _location_since[bed_id] = (current, now)
        return timedelta(0)
    return now - tracked[1]


def report_event(
    bed_id: str,
    *,
    state: EventState,
    priority: Priority,
    reason: str,
    location: EventLocation,
    action: Optional[str] = None,
    ts: Optional[datetime] = None,
) -> WardAgentOutput:
    """回報一次偵測結果。

    同一個 (bed_id, state) 若已經有一筆 active（resolved_at is None）事件，
    更新既有那筆的 reason/priority/location/last_seen_at，不開新的
    event_id；started_at 保持第一次偵測到的時間不變。location 不算在去重
    key 裡，因為同一件事發展過程中 location 本來就可能改變。
    """
    now = ts if ts is not None else datetime.now(timezone.utc)
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


def _mark_resolved(event: WardAgentOutput) -> None:
    event.resolved_at = datetime.now(timezone.utc)
    _append_to_event_history_file(event)


def resolve_event(
    event_id: str, *, completed_actions: str, follow_up: str, notes: str = ""
) -> Optional[WardAgentOutput]:
    """護理站手動標記已處理，一定要附病例紀錄。Idempotent：已經是 resolved 的事件再呼叫
    一次，直接回傳目前狀態，不覆寫 resolved_at、也不會重複寫入 event_history.json /
    case_reports.json（即使這次傳的內容不一樣）。"""
    event = get_event(event_id)
    if event is None:
        return None
    if event.resolved_at is None:
        _mark_resolved(event)
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


def auto_resolve_event(event_id: str) -> Optional[WardAgentOutput]:
    """系統自動解除（例如 vitals 恢復正常、病患回到床上/離開廁所），不是護理站手動處理，
    所以不會產生病例紀錄（case_reports.json 不會多一筆、不會跑進 PDF 匯出）；還是會進
    event_history.json，RoomDetail 的處理紀錄看得到「這件事發生過、後來自動解除了」。
    Idempotent，跟 resolve_event 一樣不會覆寫已經存在的 resolved_at。"""
    event = get_event(event_id)
    if event is None:
        return None
    if event.resolved_at is None:
        _mark_resolved(event)
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

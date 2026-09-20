# 共用資料格式 (Pydantic models)
# 對應 API_CONTRACT.md（前後端 API 契約）
# Board 端姿勢推論/行為判斷內部格式不在 API_CONTRACT.md 範圍內，
# Keypoints / BehaviorEvent 維持 TODO。

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

Priority = Literal["green", "yellow", "red"]
Gender = Literal["male", "female"]
EventState = Literal[
    "bed_exit",
    "possible_fall",
    "abnormal_transition",
    "prolonged_sitting",
    "night_wandering",
    "medical_order_violation",
    "abnormal_vitals",
    "prolonged_bathroom",
]
EventLocation = Literal["in_bed", "out_of_bed", "chair", "near_door", "bathroom"]
Posture = Literal["standing", "sitting", "lying"]


# ---------------------------------------------------------------------------
# 姿勢推論/行為判斷內部資料流 schema：不在 API_CONTRACT.md 範圍內
# ---------------------------------------------------------------------------


class Keypoints(BaseModel):
    """Board 輸出：單幀姿勢關鍵點座標"""

    # TODO: 欄位待對齊
    pass


class BehaviorEvent(BaseModel):
    """behavior_engine 輸出：從關鍵點判斷出的行為狀態/事件"""

    # TODO: 欄位待對齊
    pass


# ---------------------------------------------------------------------------
# 前後端 API 契約 schema，對應 API_CONTRACT.md
# ---------------------------------------------------------------------------


class BedInfo(BaseModel):
    """GET /api/beds 回傳陣列的元素：床位/病患靜態名冊"""

    bed_id: str
    patient_name: str
    gender: Gender
    age: int
    diagnosis: str
    assigned_nurse: Optional[str] = None


class OverviewUpdate(BaseModel):
    """/ws/overview 推送內容"""

    bed_id: str
    priority: Priority
    reason: str
    active_event_count: int
    updated_at: datetime


class WardAgentOutput(BaseModel):
    """事件：RoomDetailUpdate.active_events 的元素，也是 resolve/歷史查詢的回傳值"""

    event_id: str
    bed_id: str
    state: EventState
    priority: Priority
    reason: str
    location: EventLocation
    action: Optional[str] = None
    started_at: datetime
    last_seen_at: datetime
    resolved_at: Optional[datetime] = None


class Vitals(BaseModel):
    bed_id: str
    bp_systolic: int
    bp_diastolic: int
    temperature: float
    heart_rate: int
    spo2: int
    ts: datetime


class RoomDetailUpdate(BaseModel):
    """/ws/room/{bed_id} 上 type: "state" 訊息，約 1-2 秒推一次"""

    type: Literal["state"] = "state"
    bed_id: str
    ts: datetime
    vitals: Vitals
    active_events: List[WardAgentOutput]
    current_posture: Optional[Posture] = None
    in_camera: Optional[bool] = None


class BoardPostureUpdate(BaseModel):
    """Board -> backend：連到 /ws/room/{bed_id}?role=board 送上來的姿勢訊息。

    影像不走這裡——demo 只有一床有真的攝影機，走 camera_stream.py 的全域 pipe
    （/ws/camera/publish、/ws/camera/view），不分 bed_id。這裡只傳 board 算好的姿勢。
    """

    bed_id: str
    ts: datetime
    in_camera: bool
    current_posture: Optional[Posture] = None


class ResolveReportRequest(BaseModel):
    """POST /api/events/{event_id}/resolve 的 request body：護理站標記已處理時順便填的病例紀錄"""

    completed_actions: str
    follow_up: str
    notes: str = ""


class CaseReport(BaseModel):
    """寫進 case_reports.json 的一筆紀錄：ResolveReportRequest 補上事件/床位/時間資訊"""

    event_id: str
    bed_id: str
    completed_actions: str
    follow_up: str
    notes: str
    resolved_at: datetime


class PossibleFallReport(BaseModel):
    """Board -> backend：POST /api/beds/{bed_id}/possible-fall 的 request body。

    Board 已經自己判斷完「這是疑似跌倒」，backend 不重新驗證，收到就建立/更新事件。
    """

    ts: datetime

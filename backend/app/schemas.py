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
]
EventLocation = Literal["in_bed", "out_of_bed", "chair", "near_door", "bathroom"]


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


class OverviewUpdate(BaseModel):
    """/ws/overview 推送內容"""

    bed_id: str
    priority: Priority
    reason: str
    updated_at: datetime


class WardAgentOutput(BaseModel):
    """事件：RoomDetailUpdate.active_events 的元素，也是 resolve 的回傳值"""

    event_id: str
    bed_id: str
    state: EventState
    priority: Priority
    reason: str
    location: EventLocation
    action: Optional[str] = None
    started_at: datetime
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


class WebRTCSignal(BaseModel):
    """/ws/room/{bed_id} 上的 WebRTC signaling 訊息，跟 state 訊息共用同一條連線"""

    type: Literal["webrtc_offer", "webrtc_answer", "webrtc_ice"]
    bed_id: str
    sdp: Optional[str] = None
    candidate: Optional[dict] = None

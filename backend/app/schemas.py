# 共用資料格式 (Pydantic models)
# 對應 API_SPEC.md 的資料結構章節
# B1 / B2 / B3 都應該用這裡定義的格式互相溝通，避免各自定義造成對不上

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

RiskLevel = Literal["normal", "warning", "high"]
Posture = Literal["standing", "sitting", "lying", "walking"]


# ---------------------------------------------------------------------------
# 內部資料流 schema：B1/B2/B3 之間互相溝通用，不是 REST response 的形狀
# ---------------------------------------------------------------------------


class Keypoints(BaseModel):
    """B1 輸出：單幀姿勢關鍵點座標，每個關鍵點是 [x, y, confidence]，參考 API_SPEC.md 第 2 節"""

    nose: List[float]
    left_eye: List[float]
    right_eye: List[float]
    left_ear: List[float]
    right_ear: List[float]
    left_shoulder: List[float]
    right_shoulder: List[float]
    left_elbow: List[float]
    right_elbow: List[float]
    left_wrist: List[float]
    right_wrist: List[float]
    left_hip: List[float]
    right_hip: List[float]
    left_knee: List[float]
    right_knee: List[float]
    left_ankle: List[float]
    right_ankle: List[float]


class BehaviorEvent(BaseModel):
    """B2 (Behavior Engine) 輸出：從關鍵點判斷出的行為狀態/事件"""

    timestamp: datetime
    bed_id: str
    event: str  # 例如 STANDING / SITTING / LYING / WALKING / BED_EXIT / POSSIBLE_FALL / ABNORMAL_TRANSITION
    state_before: Optional[Posture] = None
    state_after: Optional[Posture] = None
    location: Optional[str] = None  # 例如 "bed" / "floor"，判斷跌倒是否發生在床區域內
    confidence: Optional[float] = None


class WardAgentOutput(BaseModel):
    """B2 (Ward Agent) 輸出：彙整 BehaviorEvent + patient_context 後的決策結果"""

    event_id: str
    bed_id: str
    risk: RiskLevel
    reason: str
    priority: int
    action: str


class Vitals(BaseModel):
    """B3 假生理數據輸出：血壓/體溫/心跳/血氧"""

    bp_systolic: int
    bp_diastolic: int
    temperature: float
    heart_rate: int
    spo2: int


# ---------------------------------------------------------------------------
# REST response schema：給前端消費的 HTTP response 形狀，參考 API_SPEC.md 第 3 節
# ---------------------------------------------------------------------------


class HabitBaseline(BaseModel):
    usual_wake_time: str
    usual_bathroom_duration_min: int


class MedicalOrders(BaseModel):
    no_leg_raise: bool


class RoomSummary(BaseModel):
    """GET /api/rooms 裡單一房間的狀態總覽"""

    bed_id: str
    patient_name: str
    is_live: bool
    risk_level: RiskLevel
    last_updated: datetime


class RoomsResponse(BaseModel):
    rooms: List[RoomSummary]


class RoomDetailResponse(BaseModel):
    """GET /api/rooms/{bed_id} 的完整回應"""

    bed_id: str
    patient_name: str
    is_live: bool
    current_posture: Optional[Posture] = None
    risk_level: RiskLevel
    latest_keypoints: Optional[Keypoints] = None
    latest_vitals: Vitals
    habit_baseline: HabitBaseline
    medical_orders: MedicalOrders


class EventEntry(BaseModel):
    """事件歷史單筆項目，同時也是 WS risk_update 的 data 格式"""

    event_id: str
    bed_id: str
    timestamp: datetime
    event: str
    risk: RiskLevel
    reason: str
    priority: int
    action: str


class EventsResponse(BaseModel):
    events: List[EventEntry]


# ---------------------------------------------------------------------------
# 內部狀態儲存用：不直接暴露給前端（risk_level 不存在這裡，見 store.py 動態計算）
# ---------------------------------------------------------------------------


class RoomState(BaseModel):
    """B3 內部使用：in-memory 房間目前狀態"""

    bed_id: str
    patient_name: str
    is_live: bool
    current_posture: Optional[Posture] = None
    latest_keypoints: Optional[Keypoints] = None
    latest_vitals: Vitals
    habit_baseline: HabitBaseline
    medical_orders: MedicalOrders
    last_updated: datetime

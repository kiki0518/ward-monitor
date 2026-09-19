# 共用資料格式 (Pydantic models)
# 對應 病房監測系統_Spec.md 的資料結構章節
# B1 / B2 / B3 都應該用這裡定義的格式互相溝通，避免各自定義造成對不上

from pydantic import BaseModel
from typing import Optional


class Keypoints(BaseModel):
    """B1 輸出：單幀姿勢關鍵點座標，格式參考 spec 5.1 節"""
    # TODO: 17 個關鍵點欄位，每個是 [x, y, confidence]
    pass


class BehaviorEvent(BaseModel):
    """B2 (Behavior Engine) 輸出：行為狀態/事件，格式參考 spec 5.2 節"""
    # TODO: timestamp, bed_id, event, state_before, state_after, location, confidence
    pass


class WardAgentOutput(BaseModel):
    """B2 (Ward Agent) 輸出：決策結果，格式參考 spec 5.5 節"""
    # TODO: event_id, bed_id, risk, reason, priority, action
    pass


class Vitals(BaseModel):
    """B3 假生理數據輸出：血壓/體溫/心跳/血氧"""
    # TODO: bed_id, bp_systolic, bp_diastolic, temperature, heart_rate, spo2
    pass

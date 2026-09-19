// 對應 API_CONTRACT.md 的 enum 中文標籤，BedMarker/AlertPanel/EventsList 共用

export const PRIORITY_LABEL = {
  green: "正常",
  yellow: "注意",
  red: "高風險",
};

export const EVENT_STATE_LABEL = {
  bed_exit: "離床",
  possible_fall: "疑似跌倒",
  abnormal_transition: "異常姿勢轉換",
  prolonged_sitting: "長期坐著",
  night_wandering: "夜間遊蕩",
  medical_order_violation: "違反醫囑限制",
  abnormal_vitals: "生理數據異常",
};

export const LOCATION_LABEL = {
  in_bed: "床上",
  out_of_bed: "離床",
  chair: "椅子上",
  near_door: "門邊",
  bathroom: "浴廁",
};

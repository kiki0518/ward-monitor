# B2 負責：把關鍵點轉換成 站/坐/躺/走 狀態，並判斷跌倒/離床/夜間遊蕩事件
# 對應 spec 5.2 節：STANDING / SITTING / LYING / WALKING / BED_EXIT / POSSIBLE_FALL / ABNORMAL_TRANSITION
#
# 開發時不用等 B1，先用固定的假關鍵點 JSON 檔測邏輯即可

def classify_posture(keypoints):
    # TODO: 用肩/髖/膝/踝角度判斷 standing/sitting/lying
    pass


def detect_events(keypoint_history):
    # TODO: 比對連續幀，判斷 walking / bed_exit / possible_fall / abnormal_transition
    # 注意：要用「床區域 (bed zone)」判斷 lying 是在床內(正常睡覺)還是床外(疑似跌倒)
    pass

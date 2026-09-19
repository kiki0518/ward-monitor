# B2 負責：決策層，彙整 behavior event + patient context，輸出 risk/reason/priority/action
# 對應 spec 5.5 節
#
# 先做規則式判斷即可，LLM 推理層時間夠再疊加，不要卡在這裡

def decide(behavior_event, patient_context):
    # TODO: 規則式風險判斷，輸出 WardAgentOutput (參考 app/schemas.py)
    pass

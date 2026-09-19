# 把 case_reports.json 的病例紀錄整理成一份 PDF 報告
#
# _summarize() 目前回傳固定格式的假摘要，之後要換成真的 LLM API：
# 把 reports 序列化後丟給 LLM，用回傳的摘要文字取代這個函式的回傳值即可，
# generate_report_pdf() 的其他部分不用動。

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from app.schemas import CaseReport

_FONT_PATH = Path(__file__).parent / "data" / "fonts" / "NotoSansTC-Regular.ttf"


def _summarize(reports: list[CaseReport]) -> str:
    """TODO: 換成真的 LLM API 呼叫。先回傳假資料讓前後端流程接起來。"""
    if not reports:
        return "本次匯出範圍內沒有已處理的病例紀錄。"
    follow_up_count = sum(1 for r in reports if r.follow_up.strip())
    return (
        f"本報告涵蓋 {len(reports)} 筆已處理病例，其中 {follow_up_count} 筆註記需要下一位人員接續處理。"
        "整體而言護理站處理及時，建議交班時特別留意標註「需要下一位處理」的項目。"
        "（此為系統產生的假摘要，之後會替換成真正的 LLM 摘要）"
    )


def generate_report_pdf(reports: list[CaseReport]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("NotoSansTC", "", str(_FONT_PATH))
    pdf.set_font("NotoSansTC", size=18)
    pdf.cell(0, 12, "病房監測系統 - 護理處理報告", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("NotoSansTC", size=11)
    pdf.cell(0, 8, f"匯出時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"涵蓋病例數：{len(reports)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("NotoSansTC", size=13)
    pdf.cell(0, 10, "摘要", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoSansTC", size=11)
    pdf.multi_cell(0, 7, _summarize(reports), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("NotoSansTC", size=13)
    pdf.cell(0, 10, "病例明細", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("NotoSansTC", size=11)

    if not reports:
        pdf.cell(0, 8, "（無）", new_x="LMARGIN", new_y="NEXT")
    for report in reports:
        pdf.ln(2)
        pdf.set_font("NotoSansTC", size=12)
        pdf.cell(0, 8, f"床號 {report.bed_id}　事件 {report.event_id}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("NotoSansTC", size=11)
        pdf.cell(0, 7, f"處理時間：{report.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 7, f"已完成的處理：{report.completed_actions}", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 7, f"需要下一位處理：{report.follow_up or '（無）'}", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 7, f"備註：{report.notes or '（無）'}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())

// 匯出按鈕：呼叫 GET /api/reports/export 下載病例紀錄 PDF，Overview/RoomDetail 頁共用

import { useState } from "react";
import { exportReports } from "../services/ws";
import "./ExportButton.css";

export default function ExportButton() {
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setExporting(true);
    try {
      await exportReports();
    } catch {
      alert("匯出失敗，請確認後端是否正常運作");
    } finally {
      setExporting(false);
    }
  }

  return (
    <button type="button" className="export-button" onClick={handleExport} disabled={exporting}>
      {exporting ? "匯出中..." : "匯出"}
    </button>
  );
}

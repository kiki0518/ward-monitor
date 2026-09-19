// F2 負責
// 「標記已處理」彈窗：填完已完成的處理/需要下一位處理/備註才會真的送出
// 對應 API_CONTRACT.md 的 ResolveReportRequest

import { useState } from "react";
import "./ResolveModal.css";

export default function ResolveModal({ onCancel, onConfirm }) {
  const [completedActions, setCompletedActions] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = completedActions.trim() !== "" && followUp.trim() !== "" && !submitting;

  async function handleConfirm() {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await onConfirm({
        completed_actions: completedActions.trim(),
        follow_up: followUp.trim(),
        notes: notes.trim(),
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="resolve-modal__overlay" onClick={onCancel}>
      <div className="resolve-modal" onClick={(e) => e.stopPropagation()}>
        <h3>標記已處理</h3>

        <label className="resolve-modal__field">
          <span>已完成的處理</span>
          <textarea
            value={completedActions}
            onChange={(e) => setCompletedActions(e.target.value)}
            rows={3}
            placeholder="例如：協助病患回床並安撫情緒"
          />
        </label>

        <label className="resolve-modal__field">
          <span>需要下一位處理</span>
          <textarea
            value={followUp}
            onChange={(e) => setFollowUp(e.target.value)}
            rows={3}
            placeholder="例如：持續觀察生命徵象"
          />
        </label>

        <label className="resolve-modal__field">
          <span>備註</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="選填"
          />
        </label>

        <div className="resolve-modal__actions">
          <button type="button" className="resolve-modal__cancel" onClick={onCancel} disabled={submitting}>
            取消
          </button>
          <button type="button" className="resolve-modal__confirm" onClick={handleConfirm} disabled={!canSubmit}>
            {submitting ? "送出中..." : "確認"}
          </button>
        </div>
      </div>
    </div>
  );
}

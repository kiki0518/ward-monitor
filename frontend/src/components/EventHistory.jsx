// F2 負責
// 已處理事件紀錄：唯讀清單，跟 EventsList 共用 state/priority 標籤，但沒有「標記已處理」按鈕
// refreshKey 變動時重新拉取（RoomDetail 每次 resolve 成功就會更新它）

import { useEffect, useState } from "react";
import { fetchEventHistory, handoverRequest } from "../services/ws";
import { EVENT_STATE_LABEL, PRIORITY_LABEL } from "../constants/labels";
import "./EventHistory.css";

export default function EventHistory({ bedId, refreshKey }) {
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchEventHistory(bedId), handoverRequest(bedId, "handover-sources")])
      .then(([events, reports]) => {
        if (cancelled) return;
        const merged = new Map(events.map(event => [event.event_id, event]));
        for (const report of reports) merged.set(report.event_id, { ...merged.get(report.event_id), ...report });
        setHistory([...merged.values()].sort((a, b) => new Date(b.resolved_at) - new Date(a.resolved_at)));
        setError("");
      })
      .catch(() => { if (!cancelled) setError("處理紀錄載入失敗，請重新整理"); });
    return () => {
      cancelled = true;
    };
  }, [bedId, refreshKey]);

  if (error) return <p role="alert">{error}</p>;

  if (history.length === 0) {
    return <p className="event-history event-history--empty">目前無已處理紀錄</p>;
  }

  return (
    <ul className="event-history">
      {history.map((event) => (
        <li key={event.event_id} className={`event-history__item event-history__item--${event.priority}`}>
          <div className="event-history__header">
            <span className="event-history__state">{EVENT_STATE_LABEL[event.state] ?? event.state ?? "護理處理紀錄"}</span>
            {event.priority && <span className="event-history__badge">{PRIORITY_LABEL[event.priority] ?? event.priority}</span>}
          </div>
          <p className="event-history__reason">{event.reason}</p>
          <p className="event-history__meta">
            處理時間：{new Date(event.resolved_at).toLocaleString("zh-TW", { hour12: false })}
          </p>
          {event.completed_actions !== undefined && <div style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            <p>已完成的處理：{event.completed_actions}</p>
            <p>需要下一位處理：{event.follow_up || "無"}</p>
            <p>備註：{event.notes || "無"}</p>
          </div>}
        </li>
      ))}
    </ul>
  );
}

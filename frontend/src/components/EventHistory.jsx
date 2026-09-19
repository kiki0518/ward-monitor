// F2 負責
// 已處理事件紀錄：唯讀清單，跟 EventsList 共用 state/priority 標籤，但沒有「標記已處理」按鈕
// refreshKey 變動時重新拉取（RoomDetail 每次 resolve 成功就會更新它）

import { useEffect, useState } from "react";
import { fetchEventHistory } from "../services/ws";
import { EVENT_STATE_LABEL, PRIORITY_LABEL } from "../constants/labels";
import "./EventHistory.css";

export default function EventHistory({ bedId, refreshKey }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    let cancelled = false;
    fetchEventHistory(bedId)
      .then((events) => {
        if (!cancelled) setHistory(events);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [bedId, refreshKey]);

  if (history.length === 0) {
    return <p className="event-history event-history--empty">目前無已處理紀錄</p>;
  }

  return (
    <ul className="event-history">
      {history.map((event) => (
        <li key={event.event_id} className={`event-history__item event-history__item--${event.priority}`}>
          <div className="event-history__header">
            <span className="event-history__state">{EVENT_STATE_LABEL[event.state] ?? event.state}</span>
            <span className="event-history__badge">{PRIORITY_LABEL[event.priority] ?? event.priority}</span>
          </div>
          <p className="event-history__reason">{event.reason}</p>
          <p className="event-history__meta">
            處理時間：{new Date(event.resolved_at).toLocaleTimeString("zh-TW", { hour12: false })}
          </p>
        </li>
      ))}
    </ul>
  );
}

// F2 負責
// 待處理事件列表：依 priority/發生時間排序，每筆可標記已處理

import { useState } from "react";
import { resolveEvent } from "../services/ws";
import { EVENT_STATE_LABEL, LOCATION_LABEL, PRIORITY_LABEL } from "../constants/labels";
import "./EventsList.css";

const PRIORITY_ORDER = { red: 0, yellow: 1, green: 2 };

export default function EventsList({ events, onResolved }) {
  const [resolvingIds, setResolvingIds] = useState(() => new Set());

  const sorted = [...events].sort((a, b) => {
    const priorityDiff = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
    if (priorityDiff !== 0) return priorityDiff;
    return new Date(b.started_at) - new Date(a.started_at);
  });

  async function handleResolve(eventId) {
    setResolvingIds((prev) => new Set(prev).add(eventId));
    try {
      await resolveEvent(eventId);
      onResolved(eventId);
    } finally {
      setResolvingIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  }

  if (sorted.length === 0) {
    return <p className="events-list events-list--empty">目前無待處理事件</p>;
  }

  return (
    <ul className="events-list">
      {sorted.map((event) => (
        <li key={event.event_id} className={`events-list__item events-list__item--${event.priority}`}>
          <div className="events-list__header">
            <span className="events-list__state">{EVENT_STATE_LABEL[event.state] ?? event.state}</span>
            <span className="events-list__badge">{PRIORITY_LABEL[event.priority] ?? event.priority}</span>
          </div>
          <p className="events-list__reason">{event.reason}</p>
          <p className="events-list__meta">
            位置：{LOCATION_LABEL[event.location] ?? event.location} ·{" "}
            {new Date(event.started_at).toLocaleTimeString("zh-TW", { hour12: false })}
          </p>
          {event.action && <p className="events-list__action">建議：{event.action}</p>}
          <button
            className="events-list__resolve"
            disabled={resolvingIds.has(event.event_id)}
            onClick={() => handleResolve(event.event_id)}
          >
            標記已處理
          </button>
        </li>
      ))}
    </ul>
  );
}

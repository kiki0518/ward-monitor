// F2 負責
// 待處理事件列表：依 priority/發生時間排序，每筆可標記已處理

import { useState } from "react";
import { resolveEvent } from "../services/ws";
import { EVENT_STATE_LABEL, LOCATION_LABEL, PRIORITY_LABEL } from "../constants/labels";
import { formatRelativeTime } from "../utils/relativeTime";

const PRIORITY_ORDER = { red: 0, yellow: 1, green: 2 };

const CARD_STYLE = {
  red: "border-l-red-500",
  yellow: "border-l-amber-500",
  green: "border-l-emerald-500",
};

const BADGE_STYLE = {
  red: "bg-red-100 text-red-700",
  yellow: "bg-amber-100 text-amber-700",
  green: "bg-emerald-100 text-emerald-700",
};

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
    return <p className="text-sm text-slate-400 py-3">目前無待處理事件</p>;
  }

  return (
    <ul className="flex flex-col gap-2.5">
      {sorted.map((event) => (
        <li
          key={event.event_id}
          className={`rounded-xl border-l-4 border border-slate-100 bg-white p-3.5 shadow-sm ${
            CARD_STYLE[event.priority] ?? "border-l-slate-300"
          }`}
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-sm font-semibold text-slate-900">
              {EVENT_STATE_LABEL[event.state] ?? event.state}
            </span>
            <span
              className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${
                BADGE_STYLE[event.priority] ?? "bg-slate-100 text-slate-600"
              }`}
            >
              {PRIORITY_LABEL[event.priority] ?? event.priority}
            </span>
          </div>
          <p className="text-sm text-slate-700 mb-1">{event.reason}</p>
          <p className="text-xs text-slate-500 mb-1">
            位置：{LOCATION_LABEL[event.location] ?? event.location} · {formatRelativeTime(event.started_at)}
          </p>
          <button
            className="mt-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-default transition-colors"
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

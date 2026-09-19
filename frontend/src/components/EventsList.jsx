// F2 負責
// 待處理事件列表：依 priority/發生時間排序，每筆可標記已處理，或標記為誤觸
// 「誤觸」純粹是前端把這筆從畫面濾掉，不呼叫任何 API、不進處理紀錄（見 API_CONTRACT.md「誤觸」一節）

import { Fragment, useState } from "react";
import { resolveEvent } from "../services/ws";
import { EVENT_STATE_LABEL, PRIORITY_LABEL } from "../constants/labels";
import ResolveModal from "./ResolveModal";
import "./EventsList.css";

const PRIORITY_ORDER = { red: 0, yellow: 1, green: 2 };

export default function EventsList({ events, onResolved, onDismissed }) {
  const [resolvingEventId, setResolvingEventId] = useState(null);

  // 正在填表單的那筆先從畫面濾掉（樂觀 UI，不用等 API 回應）；
  // 取消的話 resolvingEventId 變回 null，濾掉的條件解除，卡片自動恢復顯示
  const sorted = events
    .filter((event) => event.event_id !== resolvingEventId)
    .sort((a, b) => {
      const priorityDiff = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
      if (priorityDiff !== 0) return priorityDiff;
      return new Date(b.started_at) - new Date(a.started_at);
    });

  async function handleConfirmResolve(report) {
    await resolveEvent(resolvingEventId, report);
    onResolved(resolvingEventId);
    setResolvingEventId(null);
  }

  return (
    <Fragment>
      {sorted.length === 0 ? (
        <p className="events-list events-list--empty">目前無待處理事件</p>
      ) : (
        <ul className="events-list">
          {sorted.map((event) => (
            <li key={event.event_id} className={`events-list__item events-list__item--${event.priority}`}>
              <div className="events-list__header">
                <span className="events-list__state">{EVENT_STATE_LABEL[event.state] ?? event.state}</span>
                <span className="events-list__badge">{PRIORITY_LABEL[event.priority] ?? event.priority}</span>
              </div>
              <p className="events-list__reason">{event.reason}</p>
              <p className="events-list__meta">
                時間：{new Date(event.started_at).toLocaleTimeString("zh-TW", { hour12: false })}
              </p>
              {event.action && <p className="events-list__action">建議：{event.action}</p>}
              <div className="events-list__actions">
                <button className="events-list__resolve" onClick={() => setResolvingEventId(event.event_id)}>
                  標記已處理
                </button>
                <button className="events-list__dismiss" onClick={() => onDismissed(event.event_id)}>
                  錯誤判斷
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {resolvingEventId && (
        <ResolveModal onCancel={() => setResolvingEventId(null)} onConfirm={handleConfirmResolve} />
      )}
    </Fragment>
  );
}

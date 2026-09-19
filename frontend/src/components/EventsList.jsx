// F2 負責
// 待處理事件列表：依 priority/發生時間排序，每筆可標記已處理，或標記為誤觸
// 「誤觸」純粹是前端把這筆從畫面濾掉，不呼叫任何 API、不進處理紀錄（見 API_CONTRACT.md「誤觸」一節）

import { Fragment, useState } from "react";
import { resolveEvent } from "../services/ws";
import { EVENT_STATE_LABEL, PRIORITY_LABEL } from "../constants/labels";
import { formatRelativeTime } from "../utils/relativeTime";
import ResolveModal from "./ResolveModal";

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
        <p className="text-sm text-[#82958e] py-3">目前無待處理事件</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {sorted.map((event) => (
            <li
              key={event.event_id}
              className={`rounded-xl border-l-4 border border-[#d7e2dc] bg-[#fbfdfb] p-3.5 shadow-sm ${
                CARD_STYLE[event.priority] ?? "border-l-slate-300"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-sm font-semibold text-[#18332d]">
                  {EVENT_STATE_LABEL[event.state] ?? event.state}
                </span>
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${
                    BADGE_STYLE[event.priority] ?? "bg-[#e7efea] text-[#526c63]"
                  }`}
                >
                  {PRIORITY_LABEL[event.priority] ?? event.priority}
                </span>
              </div>
              <p className="text-sm text-[#36574e] mb-1">{event.reason}</p>
              <p className="text-xs text-[#6c8179] mb-1">時間：{formatRelativeTime(event.started_at)}</p>
              {event.action && <p className="text-xs text-[#6c8179] mb-1">建議：{event.action}</p>}
              <div className="flex gap-2 mt-1.5">
                <button
                  className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-[#e1f2eb] text-[#176b5b] hover:bg-[#d2eadf] transition-colors"
                  onClick={() => setResolvingEventId(event.event_id)}
                >
                  標記已處理
                </button>
                <button
                  className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-[#f3f5f4] text-[#526c63] hover:bg-[#e7ebe9] transition-colors"
                  onClick={() => onDismissed(event.event_id)}
                >
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

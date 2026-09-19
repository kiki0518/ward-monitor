// F1 負責
// 右側警示側邊欄：持續顯示紅/黃 priority 的床位，跟著 /ws/overview 即時更新，
// 每筆是獨立卡片（左側粗紅色/橘色色條 + 徽章）。上方可切換「全部樓層」/「本樓層」範圍；
// hover 卡片會跟左側平面圖對應床位做聯動高亮，點擊導到該床的 RoomDetail

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, AlertCircle } from "lucide-react";
import { parseBedId } from "../config/floorLayout";
import { PRIORITY_LABEL } from "../constants/labels";
import { formatRelativeTime } from "../utils/relativeTime";

const PRIORITY_ORDER = { red: 0, yellow: 1 };

const CARD_STYLE = {
  red: "border-l-red-500",
  yellow: "border-l-amber-500",
};

const BADGE_STYLE = {
  red: "bg-red-100 text-red-700",
  yellow: "bg-amber-100 text-amber-700",
};

const ICON = {
  red: AlertTriangle,
  yellow: AlertCircle,
};

export default function AlertPanel({ beds, activeFloor, highlightedBedId, onHighlightBed }) {
  const [scope, setScope] = useState("all");

  const alerts = useMemo(() => {
    const filtered = beds.filter((bed) => bed.priority === "red" || bed.priority === "yellow");
    const scoped =
      scope === "floor"
        ? filtered.filter((bed) => parseBedId(bed.bed_id).floor === activeFloor)
        : filtered;

    return [...scoped].sort((a, b) => {
      const priorityDiff = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
      if (priorityDiff !== 0) return priorityDiff;
      return new Date(b.updated_at) - new Date(a.updated_at);
    });
  }, [beds, scope, activeFloor]);

  return (
    <div className="bg-white rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-5 sticky top-6">
      <div className="flex flex-col gap-3 mb-4">
        <h2 className="text-base font-semibold text-slate-900">異常警示</h2>
        <div className="inline-flex bg-slate-100 rounded-full p-1 gap-1">
          <button
            className={`flex-1 text-xs px-3 py-1.5 rounded-full transition-colors ${
              scope === "all" ? "bg-white shadow-sm text-slate-900 font-medium" : "text-slate-500 hover:text-slate-700"
            }`}
            onClick={() => setScope("all")}
          >
            全部樓層
          </button>
          <button
            className={`flex-1 text-xs px-3 py-1.5 rounded-full transition-colors ${
              scope === "floor" ? "bg-white shadow-sm text-slate-900 font-medium" : "text-slate-500 hover:text-slate-700"
            }`}
            onClick={() => setScope("floor")}
          >
            本樓層
          </button>
        </div>
      </div>

      {alerts.length === 0 ? (
        <p className="text-sm text-slate-400 py-3">目前無異常警示</p>
      ) : (
        <ul className="flex flex-col gap-2.5 max-h-[70vh] overflow-y-auto">
          {alerts.map((bed) => {
            const Icon = ICON[bed.priority] ?? AlertCircle;
            const isHighlighted = highlightedBedId === bed.bed_id;
            return (
              <li key={bed.bed_id}>
                <Link
                  to={`/room/${bed.bed_id}`}
                  className={`block rounded-xl border-l-4 bg-white p-3 shadow-sm border border-slate-100 transition-shadow hover:shadow-md ${
                    CARD_STYLE[bed.priority] ?? "border-l-slate-300"
                  } ${isHighlighted ? "ring-2 ring-sky-300" : ""}`}
                  onMouseEnter={() => onHighlightBed?.(bed.bed_id)}
                  onMouseLeave={() => onHighlightBed?.(null)}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-sm font-semibold text-slate-900">{bed.bed_id} 床</span>
                    <span
                      className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${
                        BADGE_STYLE[bed.priority] ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      <Icon size={12} />
                      {PRIORITY_LABEL[bed.priority]}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 mb-0.5">{bed.patient_name}</p>
                  <p className="text-xs text-slate-500">{bed.reason}</p>
                  {bed.updated_at && (
                    <p className="text-[11px] text-slate-400 mt-1">{formatRelativeTime(bed.updated_at)}</p>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

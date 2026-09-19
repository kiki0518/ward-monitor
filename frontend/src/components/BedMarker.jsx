// F1 負責
// 疊在平面圖上的互動床位標記：正常/注意用柔和小圓點，高風險用鮮紅色 + 光暈 + 呼吸動畫，
// 一眼就能鎖定異常床位。預設只顯示房內床號（A/B/C/D），hover/focus 才展開完整資訊。
// 跟右側 AlertPanel 用 highlighted/onHighlight 做雙向聯動高亮。

import { Link } from "react-router-dom";
import { PRIORITY_LABEL } from "../constants/labels";
import { formatRelativeTime } from "../utils/relativeTime";

const PIN_STYLE = {
  green: "bg-[#35a68d]",
  yellow: "bg-amber-400",
  red: "bg-red-500 animate-pulse shadow-[0_0_10px_3px_rgba(239,68,68,0.65)] scale-125",
};

const BADGE_STYLE = {
  green: "bg-[#dcefe8] text-[#176b5b]",
  yellow: "bg-amber-100 text-amber-700",
  red: "bg-red-100 text-red-700",
};

export default function BedMarker({ bed, bedLetter, left, top, expandDirection, highlighted, onHighlight }) {
  return (
    <Link
      to={`/room/${bed.bed_id}`}
      className="group absolute -translate-x-1/2 -translate-y-1/2 no-underline"
      style={{ left: `${left}%`, top: `${top}%`, zIndex: highlighted ? 20 : 1 }}
      onMouseEnter={() => onHighlight?.(bed.bed_id)}
      onMouseLeave={() => onHighlight?.(null)}
      onFocus={() => onHighlight?.(bed.bed_id)}
      onBlur={() => onHighlight?.(null)}
    >
      <span
        className={`flex items-center justify-center w-5 h-5 rounded-full text-[9px] font-bold text-white border-[1.5px] border-white shadow-sm transition-transform ${PIN_STYLE[bed.priority] ?? "bg-[#91a7a0]"} ${
          highlighted ? "ring-4 ring-offset-1 ring-[#62b7a6] scale-125" : "group-hover:scale-125"
        }`}
      >
        {bedLetter}
      </span>
      <div
        className={`absolute left-1/2 -translate-x-1/2 w-44 p-3 rounded-xl border border-[#d7e2dc] bg-[#fbfdfb] text-left shadow-lg opacity-0 pointer-events-none transition-opacity group-hover:opacity-100 group-hover:pointer-events-auto group-focus-visible:opacity-100 ${
          expandDirection === "down" ? "top-7" : "bottom-7"
        }`}
      >
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="text-sm font-semibold text-[#18332d]">{bed.bed_id} 床</span>
          <span className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${BADGE_STYLE[bed.priority] ?? "bg-[#e7efea] text-[#526c63]"}`}>
            {PRIORITY_LABEL[bed.priority] ?? bed.priority}
          </span>
        </div>
        <p className="text-sm text-[#18332d] mb-0.5">{bed.patient_name}</p>
        <p className="text-xs text-[#6c8179]">{bed.reason}</p>
        {bed.updated_at && <p className="text-[11px] text-[#82958e] mt-1">{formatRelativeTime(bed.updated_at)}</p>}
      </div>
    </Link>
  );
}

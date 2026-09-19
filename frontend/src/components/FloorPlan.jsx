// F1 負責
// 單一樓層的平面圖：SVG 背景（病房、走廊、護理站）+ 疊加的互動床位標記，
// 標記依 priority 上色，預設只顯示房內床號，hover 才展開完整資訊

import FloorPlanBackground from "./FloorPlanBackground";
import BedMarker from "./BedMarker";
import {
  FLOOR_PLAN_BED_SLOTS,
  FLOOR_PLAN_VIEWBOX,
  bedIndexToLetter,
  getBedSlotCenterPercent,
  getRoomLabels,
} from "../config/floorLayout";

export default function FloorPlan({ beds, highlightedBedId, onHighlightBed }) {
  const roomLabels = getRoomLabels();

  return (
    <div
      className="relative w-full"
      style={{ aspectRatio: `${FLOOR_PLAN_VIEWBOX.width} / ${FLOOR_PLAN_VIEWBOX.height}` }}
    >
      <FloorPlanBackground />
      {roomLabels.map(({ key, label, left, top }) => (
        <span
          key={key}
          className="absolute -translate-x-1/2 -translate-y-1/2 text-[11px] text-slate-400 pointer-events-none"
          style={{ left: `${left}%`, top: `${top}%` }}
        >
          {label}
        </span>
      ))}
      {beds.map((bed, index) => {
        const slot = FLOOR_PLAN_BED_SLOTS[index];
        if (!slot) return null;
        const { left, top } = getBedSlotCenterPercent(index);
        return (
          <BedMarker
            key={bed.bed_id}
            bed={bed}
            bedLetter={bedIndexToLetter(slot.bedIndexInRoom)}
            left={left}
            top={top}
            expandDirection={slot.room.doorSide === "bottom" ? "down" : "up"}
            highlighted={highlightedBedId === bed.bed_id}
            onHighlight={onHighlightBed}
          />
        );
      })}
    </div>
  );
}

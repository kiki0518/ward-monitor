// F1 負責
// 單一樓層的平面圖：走廊兩側排房間，房間格用 RoomCard 呈現並依 priority 上色

import RoomCard from "./RoomCard";
import { splitIntoRows } from "../config/floorLayout";
import "./FloorPlan.css";

export default function FloorPlan({ beds }) {
  const { topRow, bottomRow } = splitIntoRows(beds);

  return (
    <div className="floor-plan">
      <div className="floor-plan__row">
        {topRow.map((bed) => (
          <RoomCard key={bed.bed_id} {...bed} />
        ))}
      </div>
      <div className="floor-plan__corridor">走廊</div>
      <div className="floor-plan__row">
        {bottomRow.map((bed) => (
          <RoomCard key={bed.bed_id} {...bed} />
        ))}
      </div>
    </div>
  );
}

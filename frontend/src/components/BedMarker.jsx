// F1 負責
// 疊在平面圖上的互動床位標記：預設只顯示房內床號（A/B/C/D，每間房各自從 A 起算）
// + priority 顏色，hover/focus 時展開顯示完整 bed_id、病患姓名、priority、理由

import { Link } from "react-router-dom";
import { PRIORITY_LABEL } from "../constants/labels";
import "./BedMarker.css";

export default function BedMarker({ bed, bedLetter, left, top, expandDirection }) {
  return (
    <Link
      to={`/room/${bed.bed_id}`}
      className={`bed-marker bed-marker--${expandDirection}`}
      style={{ left: `${left}%`, top: `${top}%` }}
    >
      <span className={`bed-marker__pin bed-marker__pin--${bed.priority}`}>{bedLetter}</span>
      <div className="bed-marker__detail">
        <div className="bed-marker__detail-header">
          <span className="bed-marker__bed-id">{bed.bed_id} 床</span>
          <span className={`bed-marker__badge bed-marker__badge--${bed.priority}`}>
            {PRIORITY_LABEL[bed.priority] ?? bed.priority}
          </span>
        </div>
        <p className="bed-marker__patient">{bed.patient_name}</p>
        <p className="bed-marker__reason">{bed.reason}</p>
      </div>
    </Link>
  );
}

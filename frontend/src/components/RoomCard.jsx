// F1 負責
// 總覽頁裡的單一病房卡片元件（顏色代表 priority）

import { Link } from "react-router-dom";
import { PRIORITY_LABEL } from "../constants/labels";
import "./RoomCard.css";

export default function RoomCard({ bed_id, patient_name, priority, reason }) {
  return (
    <Link to={`/room/${bed_id}`} className={`room-card room-card--${priority}`}>
      <div className="room-card__header">
        <span className="room-card__id">{bed_id} 床</span>
        <span className="room-card__badge">{PRIORITY_LABEL[priority] ?? priority}</span>
      </div>
      <p className="room-card__patient">{patient_name}</p>
      <p className="room-card__reason">{reason}</p>
    </Link>
  );
}

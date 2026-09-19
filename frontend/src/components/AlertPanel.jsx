// F1 負責
// 右側警示側邊欄：持續顯示紅/黃 priority 的床位，跟著 /ws/overview 即時更新
// 上方可切換「全部樓層」/「本樓層」範圍；點擊項目導到該床的 RoomDetail

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { parseBedId } from "../config/floorLayout";
import { PRIORITY_LABEL } from "../constants/labels";
import "./AlertPanel.css";

const PRIORITY_ORDER = { red: 0, yellow: 1 };

export default function AlertPanel({ beds, activeFloor }) {
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
    <div className="alert-panel">
      <div className="alert-panel__header">
        <h2>異常警示</h2>
        <div className="alert-panel__scope">
          <button
            className={`alert-panel__scope-btn ${scope === "all" ? "alert-panel__scope-btn--active" : ""}`}
            onClick={() => setScope("all")}
          >
            全部樓層
          </button>
          <button
            className={`alert-panel__scope-btn ${scope === "floor" ? "alert-panel__scope-btn--active" : ""}`}
            onClick={() => setScope("floor")}
          >
            本樓層
          </button>
        </div>
      </div>

      {alerts.length === 0 ? (
        <p className="alert-panel__empty">目前無異常警示</p>
      ) : (
        <ul className="alert-panel__list">
          {alerts.map((bed) => (
            <li key={bed.bed_id}>
              <Link
                to={`/room/${bed.bed_id}`}
                className={`alert-panel__item alert-panel__item--${bed.priority}`}
              >
                <div className="alert-panel__item-header">
                  <span className="alert-panel__bed">{bed.bed_id} 床</span>
                  <span className="alert-panel__badge">{PRIORITY_LABEL[bed.priority]}</span>
                </div>
                <p className="alert-panel__patient">{bed.patient_name}</p>
                <p className="alert-panel__reason">{bed.reason}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

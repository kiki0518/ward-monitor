// F1 負責：總覽頁
// 功能：樓層平面圖，床位卡顏色代表 priority（綠=正常/黃=注意/紅=高風險）
// 點擊床位卡導到 RoomDetail 頁面
// 資料來源：GET /api/beds 拉名冊 + WS /ws/overview 持續推送 priority/reason 更新

import { useEffect, useMemo, useState } from "react";
import FloorPlan from "../components/FloorPlan";
import AlertPanel from "../components/AlertPanel";
import { fetchBeds, connectOverviewSocket } from "../services/ws";
import { groupBedsByFloor } from "../config/floorLayout";
import "./Overview.css";

export default function Overview() {
  const [beds, setBeds] = useState(null);
  const [error, setError] = useState(false);
  const [selectedFloor, setSelectedFloor] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let socket;

    fetchBeds()
      .then((list) => {
        if (cancelled) return;
        setBeds(
          list.map((bed) => ({
            ...bed,
            priority: "green",
            reason: "生理數據正常",
            updated_at: null,
          })),
        );
        socket = connectOverviewSocket(
          (updates) => {
            setBeds((prev) => {
              const byId = new Map(updates.map((u) => [u.bed_id, u]));
              return prev.map((bed) =>
                byId.has(bed.bed_id) ? { ...bed, ...byId.get(bed.bed_id) } : bed,
              );
            });
          },
          () => setError(true),
        );
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
      socket?.close();
    };
  }, []);

  const floors = useMemo(() => (beds ? groupBedsByFloor(beds) : new Map()), [beds]);
  const floorKeys = useMemo(() => [...floors.keys()], [floors]);
  const activeFloor = selectedFloor ?? floorKeys[0];

  if (error) {
    return (
      <div className="overview">
        <h1>病房總覽</h1>
        <p className="overview__status">無法連接伺服器，請確認後端已啟動</p>
      </div>
    );
  }

  if (!beds) {
    return (
      <div className="overview">
        <h1>病房總覽</h1>
        <p className="overview__status">載入中...</p>
      </div>
    );
  }

  return (
    <div className="overview">
      <h1>病房總覽</h1>
      <div className="overview__body">
        <div className="overview__main">
          <div className="overview__tabs">
            {floorKeys.map((floor) => (
              <button
                key={floor}
                className={`overview__tab ${floor === activeFloor ? "overview__tab--active" : ""}`}
                onClick={() => setSelectedFloor(floor)}
              >
                {floor} 樓
              </button>
            ))}
          </div>
          <FloorPlan beds={floors.get(activeFloor) ?? []} />
        </div>
        <AlertPanel beds={beds} activeFloor={activeFloor} />
      </div>
    </div>
  );
}

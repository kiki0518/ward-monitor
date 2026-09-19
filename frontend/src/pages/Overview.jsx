// F1 負責：總覽頁
// 功能：樓層平面圖，床位卡顏色代表 priority（綠=正常/黃=注意/紅=高風險）
// 點擊床位卡導到 RoomDetail 頁面
// 資料來源：GET /api/beds 拉名冊 + WS /ws/overview 持續推送 priority/reason 更新

import { useEffect, useMemo, useState } from "react";
import FloorPlan from "../components/FloorPlan";
import AlertPanel from "../components/AlertPanel";
import ExportButton from "../components/ExportButton";
import { fetchBeds, fetchBedEvents, connectOverviewSocket } from "../services/ws";
import { groupBedsByFloor } from "../config/floorLayout";
import { useDismissedEvents } from "../context/DismissedEventsContext";
import "./Overview.css";

const PRIORITY_RANK = { green: 0, yellow: 1, red: 2 };

export default function Overview() {
  const [beds, setBeds] = useState(null);
  const [error, setError] = useState(false);
  const [selectedFloor, setSelectedFloor] = useState(null);
  // bed_id -> 該床目前 active 事件明細，只為了把「誤觸」的事件排除在 priority 判斷之外
  const [bedEvents, setBedEvents] = useState({});
  const { dismissedIds } = useDismissedEvents();

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

  // 每張目前紅/黃的床都拉一次 active 事件明細，才知道濾掉「誤觸」後這張床還算不算紅/黃
  useEffect(() => {
    if (!beds) return;
    beds
      .filter((bed) => bed.priority !== "green")
      .forEach((bed) => {
        fetchBedEvents(bed.bed_id)
          .then((events) => {
            setBedEvents((prev) => ({ ...prev, [bed.bed_id]: events }));
          })
          .catch(() => {});
      });
  }, [beds]);

  // 把 dismissedIds 濾掉後重新算每張床的 priority/reason，濾完沒事件剩就當作正常
  const displayBeds = useMemo(() => {
    if (!beds) return beds;
    return beds.map((bed) => {
      if (bed.priority === "green") return bed;
      const events = bedEvents[bed.bed_id];
      if (!events) return bed; // 還沒拉到明細，先維持後端算好的 priority
      const remaining = events.filter((event) => !dismissedIds.has(event.event_id));
      if (remaining.length === 0) {
        return { ...bed, priority: "green", reason: "生理數據正常" };
      }
      const top = remaining.reduce((a, b) =>
        PRIORITY_RANK[b.priority] > PRIORITY_RANK[a.priority] ? b : a,
      );
      return { ...bed, priority: top.priority, reason: top.reason };
    });
  }, [beds, bedEvents, dismissedIds]);

  const floors = useMemo(
    () => (displayBeds ? groupBedsByFloor(displayBeds) : new Map()),
    [displayBeds],
  );
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
      <div className="overview__toolbar">
        <h1>病房總覽</h1>
        <ExportButton />
      </div>
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
        <AlertPanel beds={displayBeds} activeFloor={activeFloor} />
      </div>
    </div>
  );
}

// F1 負責：總覽頁
// 功能：樓層平面圖，床位標記顏色代表 priority（綠=正常/黃=注意/紅=高風險）
// 點擊床位標記導到 RoomDetail 頁面
// 資料來源：GET /api/beds 拉名冊 + WS /ws/overview 持續推送 priority/reason 更新

import { useEffect, useMemo, useState } from "react";
import FloorPlan from "../components/FloorPlan";
import AlertPanel from "../components/AlertPanel";
import HandoverButton from "../components/Handover";
import { fetchBeds, fetchBedEvents, connectOverviewSocket } from "../services/ws";
import { groupBedsByFloor } from "../config/floorLayout";
import { useDismissedEvents } from "../context/DismissedEventsContext";
import "./Overview.css";

const PRIORITY_RANK = { green: 0, yellow: 1, red: 2 };

export default function Overview() {
  const [beds, setBeds] = useState(null);
  const [error, setError] = useState(false);
  const [selectedFloor, setSelectedFloor] = useState(null);
  const [highlightedBedId, setHighlightedBedId] = useState(null);
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

  const floorsWithAlert = useMemo(() => {
    const set = new Set();
    for (const [floor, floorBeds] of floors) {
      if (floorBeds.some((bed) => bed.priority === "red" || bed.priority === "yellow")) {
        set.add(floor);
      }
    }
    return set;
  }, [floors]);

  if (error) {
    return (
      <div className="min-h-screen bg-white p-8">
        <h1 className="text-2xl font-bold text-[#18332d] mb-4">病房總覽</h1>
        <p className="text-sm text-red-600">無法連接伺服器，請確認後端已啟動</p>
      </div>
    );
  }

  if (!beds) {
    return (
      <div className="min-h-screen bg-white p-8">
        <h1 className="text-2xl font-bold text-[#18332d] mb-4">病房總覽</h1>
        <p className="text-sm text-[#82958e]">載入中...</p>
      </div>
    );
  }

  return (
    <div className="overview">
      <div className="overview__toolbar">
        <h1>病房總覽</h1>
        <HandoverButton />
      </div>
      <div className="overview__body">
        <div className="overview__main">
          <div className="overview__tabs">
            {floorKeys.map((floor) => (
              <button
                key={floor}
                className={`relative text-sm px-4 py-1.5 rounded-full transition-colors hover:bg-[#e5f0eb] hover:text-[#16796b] hover:shadow-sm ${
                  floor === activeFloor
                    ? "bg-white shadow-sm text-[#18332d] font-medium"
                    : "text-[#6c8179]"
                }`}
                onClick={() => setSelectedFloor(floor)}
              >
                {floor} 樓
                {floorsWithAlert.has(floor) && (
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500" />
                )}
              </button>
            ))}
          </div>
          <FloorPlan
            beds={floors.get(activeFloor) ?? []}
            highlightedBedId={highlightedBedId}
            onHighlightBed={setHighlightedBedId}
          />
        </div>
        <AlertPanel
          beds={displayBeds}
          activeFloor={activeFloor}
          highlightedBedId={highlightedBedId}
          onHighlightBed={setHighlightedBedId}
        />
      </div>
    </div>
  );
}

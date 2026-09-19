// F1 負責：總覽頁
// 功能：樓層平面圖，床位標記顏色代表 priority（綠=正常/黃=注意/紅=高風險）
// 點擊床位標記導到 RoomDetail 頁面
// 資料來源：GET /api/beds 拉名冊 + WS /ws/overview 持續推送 priority/reason 更新

import { useEffect, useMemo, useState } from "react";
import FloorPlan from "../components/FloorPlan";
import AlertPanel from "../components/AlertPanel";
import { fetchBeds, connectOverviewSocket } from "../services/ws";
import { groupBedsByFloor } from "../config/floorLayout";

export default function Overview() {
  const [beds, setBeds] = useState(null);
  const [error, setError] = useState(false);
  const [selectedFloor, setSelectedFloor] = useState(null);
  const [highlightedBedId, setHighlightedBedId] = useState(null);

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
      <div className="min-h-screen bg-slate-50 p-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">病房總覽</h1>
        <p className="text-sm text-red-600">無法連接伺服器，請確認後端已啟動</p>
      </div>
    );
  }

  if (!beds) {
    return (
      <div className="min-h-screen bg-slate-50 p-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">病房總覽</h1>
        <p className="text-sm text-slate-400">載入中...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">病房總覽</h1>
      <div className="grid grid-cols-1 lg:grid-cols-[2.4fr_1fr] gap-6 items-start">
        <div className="bg-white rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6">
          <div className="flex w-fit mx-auto bg-slate-100 rounded-full p-1 gap-1 mb-5 flex-wrap">
            {floorKeys.map((floor) => (
              <button
                key={floor}
                className={`relative text-sm px-4 py-1.5 rounded-full transition-colors ${
                  floor === activeFloor
                    ? "bg-white shadow-sm text-slate-900 font-medium"
                    : "text-slate-500 hover:text-slate-700"
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
          beds={beds}
          activeFloor={activeFloor}
          highlightedBedId={highlightedBedId}
          onHighlightBed={setHighlightedBedId}
        />
      </div>
    </div>
  );
}

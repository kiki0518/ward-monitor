// 護理師個人視角：手機/工作機用的窄版頁面。
// 第一次開啟先選自己的姓名（存在該裝置的 localStorage，不做帳密登入），
// 選完只顯示自己負責的床位；資料來源沿用 Overview 頁同一條 /ws/overview 推播，
// 差別只在前端多做一層 filter，不需要後端另外做「推播給特定護理師」的機制。
// 自己負責的床位一旦 priority 惡化（例如綠→黃/紅），額外用橫幅+聲音+瀏覽器通知提醒。

import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, AlertCircle, X } from "lucide-react";
import { fetchBeds, fetchNurses, connectOverviewSocket } from "../services/ws";
import { PRIORITY_LABEL } from "../constants/labels";
import { formatRelativeTime } from "../utils/relativeTime";
import { getStoredNurse, setStoredNurse, clearStoredNurse } from "../utils/nurseIdentity";
import { playAlertBeep, requestNotificationPermission, showBrowserNotification } from "../utils/notify";

const PRIORITY_RANK = { red: 0, yellow: 1, green: 2 };

const CARD_STYLE = {
  red: "border-l-red-500",
  yellow: "border-l-amber-500",
  green: "border-l-emerald-300",
};

const BADGE_STYLE = {
  red: "bg-red-100 text-red-700",
  yellow: "bg-amber-100 text-amber-700",
  green: "bg-emerald-50 text-emerald-600",
};

const ICON = {
  red: AlertTriangle,
  yellow: AlertCircle,
  green: null,
};

function NursePicker({ onPick }) {
  const [nurses, setNurses] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchNurses()
      .then(setNurses)
      .catch(() => setError(true));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 p-4 flex flex-col items-center justify-center gap-6">
      <h1 className="text-xl font-bold text-slate-900">請選擇你的姓名</h1>
      {error && <p className="text-sm text-red-600">無法連接伺服器，請確認後端已啟動</p>}
      {!error && !nurses && <p className="text-sm text-slate-400">載入中...</p>}
      <div className="w-full max-w-sm flex flex-col gap-2">
        {nurses?.map((name) => (
          <button
            key={name}
            onClick={() => onPick(name)}
            className="w-full text-base py-3 rounded-xl bg-white shadow-sm border border-slate-200 text-slate-900 font-medium hover:border-sky-300 hover:bg-sky-50 transition-colors"
          >
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function NurseView() {
  const [nurseName, setNurseName] = useState(getStoredNurse);
  const [beds, setBeds] = useState(null);
  const [error, setError] = useState(false);
  const [banners, setBanners] = useState([]);
  const lastPriorityRef = useRef(new Map());

  useEffect(() => {
    if (!nurseName) return;
    requestNotificationPermission();
  }, [nurseName]);

  useEffect(() => {
    if (!nurseName) return;
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
              if (!prev) return prev;
              const byId = new Map(updates.map((u) => [u.bed_id, u]));
              const next = prev.map((bed) =>
                byId.has(bed.bed_id) ? { ...bed, ...byId.get(bed.bed_id) } : bed,
              );

              for (const bed of next) {
                if (bed.assigned_nurse !== nurseName) continue;
                const lastPriority = lastPriorityRef.current.get(bed.bed_id) ?? "green";
                const worsened = PRIORITY_RANK[bed.priority] < PRIORITY_RANK[lastPriority];
                if (worsened && bed.priority !== "green") {
                  const bannerId = `${bed.bed_id}-${bed.updated_at}`;
                  setBanners((prevBanners) => [
                    ...prevBanners,
                    { id: bannerId, bedId: bed.bed_id, patientName: bed.patient_name, reason: bed.reason, priority: bed.priority },
                  ]);
                  setTimeout(() => {
                    setBanners((prevBanners) => prevBanners.filter((b) => b.id !== bannerId));
                  }, 10000);
                  playAlertBeep();
                  showBrowserNotification(
                    `${bed.bed_id} 床 ${bed.patient_name} — ${PRIORITY_LABEL[bed.priority]}`,
                    bed.reason,
                  );
                }
                lastPriorityRef.current.set(bed.bed_id, bed.priority);
              }

              return next;
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
  }, [nurseName]);

  const myBeds = useMemo(() => {
    if (!beds) return [];
    return beds
      .filter((bed) => bed.assigned_nurse === nurseName)
      .sort((a, b) => {
        const diff = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
        if (diff !== 0) return diff;
        return a.bed_id.localeCompare(b.bed_id);
      });
  }, [beds, nurseName]);

  const dismissBanner = (id) => setBanners((prev) => prev.filter((b) => b.id !== id));

  const switchNurse = () => {
    clearStoredNurse();
    setNurseName(null);
    setBeds(null);
    setBanners([]);
    lastPriorityRef.current = new Map();
  };

  if (!nurseName) {
    return (
      <NursePicker
        onPick={(name) => {
          setStoredNurse(name);
          setNurseName(name);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-4">
      {banners.length > 0 && (
        <div className="fixed top-0 inset-x-0 z-50 flex flex-col gap-1.5 p-3">
          {banners.map((banner) => (
            <div
              key={banner.id}
              className={`flex items-center justify-between gap-3 rounded-xl px-4 py-3 shadow-lg text-white animate-pulse ${
                banner.priority === "red" ? "bg-red-600" : "bg-amber-500"
              }`}
            >
              <Link to={`/room/${banner.bedId}`} className="flex-1 text-sm font-medium">
                {banner.bedId} 床 {banner.patientName}：{banner.reason}
              </Link>
              <button onClick={() => dismissBanner(banner.id)} aria-label="關閉">
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="text-xs text-slate-400">護理師</p>
          <h1 className="text-lg font-bold text-slate-900">{nurseName}</h1>
        </div>
        <button
          onClick={switchNurse}
          className="text-xs px-3 py-1.5 rounded-full bg-slate-100 text-slate-500 hover:text-slate-700"
        >
          切換護理師
        </button>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">無法連接伺服器，請確認後端已啟動</p>}
      {!error && !beds && <p className="text-sm text-slate-400">載入中...</p>}

      {beds && myBeds.length === 0 && (
        <p className="text-sm text-slate-400">目前沒有指派給你的床位</p>
      )}

      <ul className="flex flex-col gap-2.5">
        {myBeds.map((bed) => {
          const Icon = ICON[bed.priority];
          return (
            <li key={bed.bed_id}>
              <Link
                to={`/room/${bed.bed_id}`}
                className={`block rounded-xl border-l-4 bg-white p-3.5 shadow-sm border border-slate-100 ${
                  CARD_STYLE[bed.priority]
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-sm font-semibold text-slate-900">{bed.bed_id} 床 · {bed.patient_name}</span>
                  <span
                    className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${BADGE_STYLE[bed.priority]}`}
                  >
                    {Icon && <Icon size={12} />}
                    {PRIORITY_LABEL[bed.priority]}
                  </span>
                </div>
                <p className="text-xs text-slate-500">{bed.reason}</p>
                {bed.updated_at && bed.priority !== "green" && (
                  <p className="text-[11px] text-slate-400 mt-1">{formatRelativeTime(bed.updated_at)}</p>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

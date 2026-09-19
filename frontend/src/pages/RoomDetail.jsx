// F2 負責：單病房詳細頁
// 功能：攝影機畫面（/ws/camera/view JPEG relay）+ 體徵面板 + 待處理事件列表
// 資料來源：GET /api/beds 拿病患姓名、WS /ws/room/{bed_id} 拿 state(vitals+active_events)

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { connectRoomSocket, fetchBeds } from "../services/ws";
import { useDismissedEvents } from "../context/DismissedEventsContext";
import { GENDER_LABEL } from "../constants/labels";
import VideoFeed from "../components/VideoFeed";
import VitalsPanel from "../components/VitalsPanel";
import EventsList from "../components/EventsList";
import EventHistory from "../components/EventHistory";
import ExportButton from "../components/ExportButton";

const VITALS_HISTORY_LIMIT = 30;

export default function RoomDetail() {
  const { bedId } = useParams();
  // key=bedId 讓切換床位時整個內部元件重新掛載，各床的 state 天生互不沿用，不需手動重置
  return <RoomDetailView key={bedId} bedId={bedId} />;
}

function RoomDetailView({ bedId }) {
  const navigate = useNavigate();
  const [patient, setPatient] = useState(null);
  const [vitalsHistory, setVitalsHistory] = useState([]);
  const [activeEvents, setActiveEvents] = useState([]);
  const { dismissedIds, dismissEvent } = useDismissedEvents();
  const [historyRefresh, setHistoryRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchBeds()
      .then((beds) => {
        if (cancelled) return;
        setPatient(beds.find((bed) => bed.bed_id === bedId) ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [bedId]);

  useEffect(() => {
    const socket = connectRoomSocket(
      bedId,
      (state) => {
        setVitalsHistory((prev) => [...prev, state.vitals].slice(-VITALS_HISTORY_LIMIT));
        setActiveEvents(state.active_events);
      },
      () => {},
    );

    return () => socket.close();
  }, [bedId]);

  function handleResolved(eventId) {
    setActiveEvents((prev) => prev.filter((event) => event.event_id !== eventId));
    setHistoryRefresh((prev) => prev + 1);
  }

  function handleDismissed(eventId) {
    dismissEvent(eventId);
  }

  const visibleEvents = activeEvents.filter((event) => !dismissedIds.has(event.event_id));

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="flex items-center justify-between mb-4">
        <button
          type="button"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors"
          onClick={() => navigate(-1)}
        >
          <ArrowLeft size={16} />
          返回
        </button>
        <ExportButton />
      </div>
      <h1 className="text-2xl font-bold text-slate-900 mb-1">
        {bedId} 床{patient ? ` · ${patient.patient_name}` : ""}
      </h1>
      {patient && (
        <p className="text-sm text-slate-500 mb-6">
          {GENDER_LABEL[patient.gender] ?? patient.gender}・{patient.age} 歲・{patient.diagnosis}
        </p>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-6 items-start">
        <div className="flex flex-col gap-6">
          <div className="bg-white rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6">
            <VideoFeed bedId={bedId} />
          </div>
          <section className="bg-white rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6">
            <h2 className="text-base font-semibold text-slate-900 mb-4">處理紀錄</h2>
            <EventHistory bedId={bedId} refreshKey={historyRefresh} />
          </section>
        </div>
        <div className="flex flex-col gap-6">
          <section className="bg-white rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6">
            <h2 className="text-base font-semibold text-slate-900 mb-4">待處理事件</h2>
            <EventsList events={visibleEvents} onResolved={handleResolved} onDismissed={handleDismissed} />
          </section>
          <section className="bg-white rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6">
            <h2 className="text-base font-semibold text-slate-900 mb-4">生理數據</h2>
            <VitalsPanel history={vitalsHistory} />
          </section>
        </div>
      </div>
    </div>
  );
}

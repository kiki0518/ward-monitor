// F2 負責：單病房詳細頁
// 功能：攝影機畫面（/ws/camera/view JPEG relay）+ 體徵面板 + 待處理事件列表
// 資料來源：GET /api/beds 拿病患姓名、WS /ws/room/{bed_id} 拿 state(vitals+active_events)

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { connectRoomSocket, fetchBeds } from "../services/ws";
import { useDismissedEvents } from "../context/DismissedEventsContext";
import { GENDER_LABEL } from "../constants/labels";
import VideoFeed from "../components/VideoFeed";
import VitalsPanel from "../components/VitalsPanel";
import EventsList from "../components/EventsList";
import EventHistory from "../components/EventHistory";
import ExportButton from "../components/ExportButton";
import "./RoomDetail.css";

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
    <div className="room-detail">
      <div className="room-detail__toolbar">
        <button type="button" className="room-detail__back" onClick={() => navigate(-1)}>
          ← 返回
        </button>
        <ExportButton />
      </div>
      <h1>
        {bedId} 床{patient ? ` · ${patient.patient_name}` : ""}
      </h1>
      {patient && (
        <p className="room-detail__patient-meta">
          {GENDER_LABEL[patient.gender] ?? patient.gender}・{patient.age} 歲・{patient.diagnosis}
        </p>
      )}
      <div className="room-detail__layout">
        <div>
          <VideoFeed bedId={bedId} />
          <section className="room-detail__history">
            <h2>處理紀錄</h2>
            <EventHistory bedId={bedId} refreshKey={historyRefresh} />
          </section>
        </div>
        <div className="room-detail__side">
          <section>
            <h2>待處理事件</h2>
            <EventsList events={visibleEvents} onResolved={handleResolved} onDismissed={handleDismissed} />
          </section>
          <section>
            <h2>生理數據</h2>
            <VitalsPanel history={vitalsHistory} />
          </section>
        </div>
      </div>
    </div>
  );
}

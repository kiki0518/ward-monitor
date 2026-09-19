// F2 負責：單病房詳細頁
// 功能：攝影機畫面（WebRTC）+ 體徵面板 + 待處理事件列表
// 資料來源：GET /api/beds 拿病患姓名、WS /ws/room/{bed_id} 拿 state(vitals+active_events) + WebRTC signaling

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { connectRoomSocket, fetchBeds } from "../services/ws";
import VideoFeed from "../components/VideoFeed";
import VitalsPanel from "../components/VitalsPanel";
import EventsList from "../components/EventsList";
import "./RoomDetail.css";

const VITALS_HISTORY_LIMIT = 30;

export default function RoomDetail() {
  const { bedId } = useParams();
  // key=bedId 讓切換床位時整個內部元件重新掛載，各床的 state 天生互不沿用，不需手動重置
  return <RoomDetailView key={bedId} bedId={bedId} />;
}

function RoomDetailView({ bedId }) {
  const navigate = useNavigate();
  const [patientName, setPatientName] = useState(null);
  const [vitalsHistory, setVitalsHistory] = useState([]);
  const [activeEvents, setActiveEvents] = useState([]);
  const [roomSocket, setRoomSocket] = useState(null);
  const [error, setError] = useState(false);
  const signalHandlerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    fetchBeds()
      .then((beds) => {
        if (cancelled) return;
        setPatientName(beds.find((bed) => bed.bed_id === bedId)?.patient_name ?? null);
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
      (signal) => signalHandlerRef.current?.(signal),
      () => setError(true),
    );
    setRoomSocket(socket);

    return () => socket.close();
  }, [bedId]);

  function handleResolved(eventId) {
    setActiveEvents((prev) => prev.filter((event) => event.event_id !== eventId));
  }

  return (
    <div className="room-detail">
      <button type="button" className="room-detail__back" onClick={() => navigate(-1)}>
        ← 返回
      </button>
      <h1>
        {bedId} 床{patientName ? ` · ${patientName}` : ""}
      </h1>
      {error && <p className="room-detail__status">與伺服器的連線中斷</p>}
      <div className="room-detail__layout">
        <VideoFeed bedId={bedId} roomSocket={roomSocket} onSignalRef={signalHandlerRef} />
        <div className="room-detail__side">
          <section>
            <h2>生理數據</h2>
            <VitalsPanel history={vitalsHistory} />
          </section>
          <section>
            <h2>待處理事件</h2>
            <EventsList events={activeEvents} onResolved={handleResolved} />
          </section>
        </div>
      </div>
    </div>
  );
}

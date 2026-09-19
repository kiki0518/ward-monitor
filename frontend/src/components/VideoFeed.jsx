// F2 負責
// 攝影機畫面：透過 /ws/camera/view 用「送 next 換一張」的方式輪詢最新 JPEG frame
// 全系統目前只有一支攝影機（見 API_CONTRACT.md），不分 bed_id，僅用於顯示標籤

import { useEffect, useRef, useState } from "react";
import { connectCameraViewSocket } from "../services/ws";

const STATUS_LABEL = {
  connecting: "連線中",
  live: "已連線",
  waiting: "尚無攝影機畫面",
  disconnected: "連線中斷",
};

const STATUS_DOT = {
  connecting: "bg-amber-400",
  live: "bg-emerald-400",
  waiting: "bg-slate-400",
  disconnected: "bg-red-500",
};

export default function VideoFeed({ bedId }) {
  const imgRef = useRef(null);
  const objectUrlRef = useRef(null);
  const [status, setStatus] = useState("connecting");

  useEffect(() => {
    const socket = connectCameraViewSocket(
      (blob) => {
        const url = URL.createObjectURL(blob);
        if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = url;
        if (imgRef.current) imgRef.current.src = url;
        setStatus("live");
      },
      (serverStatus) => {
        if (serverStatus === "waiting") setStatus("waiting");
      },
      () => setStatus("disconnected"),
    );

    return () => {
      socket.close();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, [bedId]);

  return (
    <div className="relative bg-slate-900 rounded-xl overflow-hidden aspect-video">
      <img ref={imgRef} className="w-full h-full object-cover" alt={`${bedId} 床攝影機畫面`} />
      <span className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/55 text-white text-xs">
        <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[status] ?? "bg-slate-400"}`} />
        {STATUS_LABEL[status] ?? status}
      </span>
    </div>
  );
}

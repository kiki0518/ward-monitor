// F2 負責
// 攝影機畫面：瀏覽器發起 WebRTC offer，透過 roomSocket 做 SDP/ICE signaling，
// 影像本身是 board 與瀏覽器 P2P 直連（同區網，不架 STUN/TURN）

import { useEffect, useRef, useState } from "react";
import "./VideoFeed.css";

const STATUS_LABEL = {
  new: "連線中",
  connecting: "連線中",
  connected: "已連線",
  disconnected: "連線中斷",
  failed: "連線失敗",
  closed: "已關閉",
};

export default function VideoFeed({ bedId, roomSocket, onSignalRef }) {
  const videoRef = useRef(null);
  const [status, setStatus] = useState("new");

  useEffect(() => {
    if (!roomSocket) return;

    const pc = new RTCPeerConnection();
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.ontrack = (event) => {
      if (videoRef.current) videoRef.current.srcObject = event.streams[0];
    };
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        roomSocket.send({ type: "webrtc_ice", bed_id: bedId, candidate: event.candidate });
      }
    };
    pc.onconnectionstatechange = () => setStatus(pc.connectionState);

    onSignalRef.current = async (signal) => {
      if (signal.type === "webrtc_answer") {
        await pc.setRemoteDescription({ type: "answer", sdp: signal.sdp });
      } else if (signal.type === "webrtc_ice" && signal.candidate) {
        await pc.addIceCandidate(signal.candidate);
      }
    };

    pc.createOffer()
      .then((offer) => pc.setLocalDescription(offer))
      .then(() => {
        roomSocket.send({ type: "webrtc_offer", bed_id: bedId, sdp: pc.localDescription.sdp });
      });

    return () => {
      onSignalRef.current = null;
      pc.close();
    };
  }, [roomSocket, bedId, onSignalRef]);

  return (
    <div className="video-feed">
      <video ref={videoRef} className="video-feed__video" autoPlay muted playsInline />
      <span className="video-feed__status">{STATUS_LABEL[status] ?? status}</span>
    </div>
  );
}

// 跟 B3 對接：WebSocket / REST 連線邏輯
// 資料格式規範請參考根目錄 API_CONTRACT.md（前後端契約，F1/F2 都要跟這份對齊）

const API_BASE = "http://127.0.0.1:8000";
const WS_BASE = "ws://127.0.0.1:8000";

// GET /api/beds -> list[BedInfo]，進總覽頁前先拉一次床位/病患靜態名冊
export async function fetchBeds() {
  const res = await fetch(`${API_BASE}/api/beds`);
  if (!res.ok) throw new Error(`fetchBeds failed: ${res.status}`);
  return res.json();
}

// WS /ws/overview -> 持續推送 list[OverviewUpdate]（全床摘要）
// 回傳可呼叫 close() 的物件，供元件在 useEffect cleanup 時關閉連線
export function connectOverviewSocket(onMessage, onError) {
  const socket = new WebSocket(`${WS_BASE}/ws/overview`);

  socket.onmessage = (event) => {
    onMessage(JSON.parse(event.data));
  };
  socket.onerror = (event) => {
    onError?.(event);
  };
  socket.onclose = (event) => {
    if (!event.wasClean) onError?.(event);
  };

  return { close: () => socket.close() };
}

// WS /ws/room/{bed_id} -> 同一條連線上依 type 區分 state（vitals+events）跟 webrtc signaling
// 回傳 { send, close }，send() 用來送出 webrtc_offer/webrtc_ice 等 signaling 訊息
export function connectRoomSocket(bedId, onState, onSignal, onError) {
  const socket = new WebSocket(`${WS_BASE}/ws/room/${bedId}`);
  const pendingMessages = [];

  socket.onopen = () => {
    for (const message of pendingMessages.splice(0)) {
      socket.send(JSON.stringify(message));
    }
  };
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "state") {
      onState(data);
    } else {
      onSignal(data);
    }
  };
  socket.onerror = (event) => {
    onError?.(event);
  };
  socket.onclose = (event) => {
    if (!event.wasClean) onError?.(event);
  };

  return {
    // 建立連線是非同步的，送 offer 時 socket 可能還沒 OPEN，先排隊等 onopen 再送出
    send: (message) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(message));
      } else {
        pendingMessages.push(message);
      }
    },
    close: () => socket.close(),
  };
}

// POST /api/events/{event_id}/resolve -> 護理站標記事件已處理
export async function resolveEvent(eventId) {
  const res = await fetch(`${API_BASE}/api/events/${eventId}/resolve`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`resolveEvent failed: ${res.status}`);
  return res.json();
}

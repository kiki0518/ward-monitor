// 跟 B3 對接：WebSocket 連線邏輯
// 資料格式規範請參考 病房監測系統_Spec.md 及團隊另外對齊的「介面契約」

const WS_URL = "ws://localhost:8000/ws";

export function connectWebSocket(onMessage) {
  // TODO: 建立 WebSocket 連線，收到訊息時呼叫 onMessage(data)
}

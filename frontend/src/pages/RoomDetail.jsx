// F2 負責：單病房詳細頁
// 功能：
//   - 攝影機畫面 + 骨架關鍵點疊加 (canvas)
//   - 體徵顯示：心跳/血氧用即時曲線，血壓/體溫用數值卡片
// 資料來源：跟 B3 對好的 WebSocket 訊息格式（keypoints + vitals）

import { useParams } from "react-router-dom";

export default function RoomDetail() {
  const { roomId } = useParams();

  return (
    <div>
      <h1>病房詳細資訊：{roomId}</h1>
      {/* TODO: 攝影機畫面 + 骨架疊加 canvas */}
      {/* TODO: 體徵面板 (心跳/血氧即時曲線、血壓/體溫卡片) */}
    </div>
  );
}

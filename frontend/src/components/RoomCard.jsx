// F1 負責
// 總覽頁裡的單一病房卡片元件（顏色代表風險狀態）

export default function RoomCard({ roomId, riskLevel }) {
  return (
    <div>
      {/* TODO: 依 riskLevel 顯示不同顏色 (normal/warning/high) */}
      <p>{roomId}</p>
    </div>
  );
}

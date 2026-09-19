// F1 負責
// 平面圖背景：牆、11 間病房（各房內床位圖示）、門、主走廊、開放式護理站的靜態 SVG
// （不含互動床位標記，床位標記由 FloorPlan 疊加在上面）。顏色走 CSS 變數，深色模式會自動適配。

import {
  FLOOR_PLAN_ROOMS,
  FLOOR_PLAN_VIEWBOX,
  NURSES_STATION,
  getBedIconRectInRoom,
} from "../config/floorLayout";

export default function FloorPlanBackground() {
  return (
    <svg
      viewBox={`0 0 ${FLOOR_PLAN_VIEWBOX.width} ${FLOOR_PLAN_VIEWBOX.height}`}
      className="floor-plan-bg"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <g id="fp-bed">
          <rect width="40" height="65" rx="3" className="fp-bed__frame" />
          <rect x="5" y="5" width="30" height="15" rx="2" className="fp-bed__pillow" />
        </g>
      </defs>

      {/* 上排外牆（7 間病房，四面完整封閉） */}
      <rect x="50" y="50" width="1100" height="200" className="fp-wall" />

      {/* 下排外牆：只畫左、下、右三邊 + 病房區與護理站的分隔牆，
          護理站那側刻意不畫上緣，呈現與走廊連通的開放動線 */}
      <polyline points="50,350 50,550 1150,550 1150,350" className="fp-wall" />
      <line x1={NURSES_STATION.x} y1="350" x2={NURSES_STATION.x} y2="550" className="fp-wall" />

      {/* 病房 + 房內床位輪廓（實際狀態由疊加的互動標記顯示） */}
      {FLOOR_PLAN_ROOMS.map((room, roomIndex) => {
        const doorX = room.x + room.width / 2 - 15;
        const doorY = room.doorSide === "bottom" ? room.y + room.height - 2 : room.y - 2;
        return (
          <g key={roomIndex}>
            <rect x={room.x} y={room.y} width={room.width} height={room.height} className="fp-room" />
            {Array.from({ length: room.beds }, (_, bedIndex) => {
              const icon = getBedIconRectInRoom(room, bedIndex);
              return <use key={bedIndex} href="#fp-bed" x={icon.x} y={icon.y} />;
            })}
            <rect x={doorX} y={doorY} width="30" height="4" className="fp-door" />
          </g>
        );
      })}

      {/* 主走廊 */}
      <text x="300" y="305" className="fp-corridor-label" textAnchor="middle">
        主走廊
      </text>

      {/* 開放式護理站：無實體牆，U 型櫃檯 + 工作站示意，與走廊連通 */}
      <rect
        x={NURSES_STATION.x}
        y={NURSES_STATION.y}
        width={NURSES_STATION.width}
        height={NURSES_STATION.height}
        className="fp-station-area"
      />
      <path
        d={`M ${NURSES_STATION.x + 50} ${NURSES_STATION.y + 130}
            L ${NURSES_STATION.x + 50} ${NURSES_STATION.y + 30}
            L ${NURSES_STATION.x + 450} ${NURSES_STATION.y + 30}
            L ${NURSES_STATION.x + 450} ${NURSES_STATION.y + 130}`}
        className="fp-station-counter"
      />
      {[0, 1, 2, 3, 4].map((i) => (
        <rect
          key={i}
          x={NURSES_STATION.x + 100 + i * 70}
          y={NURSES_STATION.y + 15}
          width="30"
          height="15"
          className="fp-station-workstation"
        />
      ))}
      <text
        x={NURSES_STATION.x + NURSES_STATION.width / 2}
        y={NURSES_STATION.y + 100}
        className="fp-station-label"
        textAnchor="middle"
      >
        護理站
      </text>
      <text
        x={NURSES_STATION.x + NURSES_STATION.width / 2}
        y={NURSES_STATION.y + 122}
        className="fp-station-sublabel"
        textAnchor="middle"
      >
        NURSES&apos; STATION
      </text>
    </svg>
  );
}

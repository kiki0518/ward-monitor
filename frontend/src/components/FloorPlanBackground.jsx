// F1 負責
// 平面圖背景：像真實建築平面圖一樣用線條分間——所有房間統一用同一種線寬/顏色，
// 房門在牆上開口，不用卡片陰影。走廊留白、半透明青綠色開放式護理站。
// 不含互動床位標記（由 FloorPlan 疊加在上面）。

import { FLOOR_PLAN_ROOMS, FLOOR_PLAN_VIEWBOX, NURSES_STATION } from "../config/floorLayout";

export default function FloorPlanBackground() {
  return (
    <svg
      viewBox={`0 0 ${FLOOR_PLAN_VIEWBOX.width} ${FLOOR_PLAN_VIEWBOX.height}`}
      className="floor-plan-bg rounded-xl"
      preserveAspectRatio="xMidYMid meet"
    >
      {/* 房間分間線：統一線寬/顏色，外牆與隔間不做粗細區分 */}
      {FLOOR_PLAN_ROOMS.map((room, roomIndex) => (
        <rect
          key={roomIndex}
          x={room.x}
          y={room.y}
          width={room.width}
          height={room.height}
          className="fill-white stroke-[#8da9a0]"
          strokeWidth="1.5"
        />
      ))}

      {/* 護理站與病房區的分隔牆，跟房間線同寬同色 */}
      <line
        x1={NURSES_STATION.x}
        y1={NURSES_STATION.y}
        x2={NURSES_STATION.x}
        y2={NURSES_STATION.y + NURSES_STATION.height}
        className="stroke-[#8da9a0]"
        strokeWidth="1.5"
      />

      {/* 房門開口：在牆上切一段缺口，讓房間跟走廊視覺上是連通的 */}
      {FLOOR_PLAN_ROOMS.map((room, roomIndex) => {
        const doorX = room.x + room.width / 2 - 15;
        const doorY = room.doorSide === "bottom" ? room.y + room.height - 1 : room.y - 1;
        return <rect key={roomIndex} x={doorX} y={doorY} width="30" height="2" className="fill-white" />;
      })}

      {/* 主走廊 */}
      <text x="300" y="305" textAnchor="middle" className="fill-[#91a7a0] text-[13px] font-medium tracking-[4px]">
        主走廊
      </text>

      {/* 開放式護理站：半透明青綠色標示，無實體邊框，與走廊連通 */}
      <rect
        x={NURSES_STATION.x}
        y={NURSES_STATION.y}
        width={NURSES_STATION.width}
        height={NURSES_STATION.height}
        rx="20"
        className="fill-[#16796b]/10"
      />
      <path
        d={`M ${NURSES_STATION.x + 50} ${NURSES_STATION.y + 130}
            L ${NURSES_STATION.x + 50} ${NURSES_STATION.y + 30}
            L ${NURSES_STATION.x + 450} ${NURSES_STATION.y + 30}
            L ${NURSES_STATION.x + 450} ${NURSES_STATION.y + 130}`}
        className="fill-none stroke-[#62b7a6]"
        strokeWidth="8"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {[0, 1, 2, 3, 4].map((i) => (
        <rect
          key={i}
          x={NURSES_STATION.x + 100 + i * 70}
          y={NURSES_STATION.y + 15}
          width="30"
          height="15"
          rx="3"
          className="fill-white stroke-[#9ed5ca]"
        />
      ))}
      <text
        x={NURSES_STATION.x + NURSES_STATION.width / 2}
        y={NURSES_STATION.y + 100}
        textAnchor="middle"
        className="fill-[#126457] text-[20px] font-bold tracking-[3px]"
      >
        護理站
      </text>
      <text
        x={NURSES_STATION.x + NURSES_STATION.width / 2}
        y={NURSES_STATION.y + 122}
        textAnchor="middle"
        className="fill-[#238b7b] text-[11px] tracking-[2px]"
      >
        NURSES&apos; STATION
      </text>
    </svg>
  );
}

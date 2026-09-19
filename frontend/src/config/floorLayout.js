// Overview 平面圖的空間佈局設定（前端自訂，非後端資料）
// bed_id 格式為「樓層(1碼) + 房號(2碼)」，例如 "101" = 1 樓 01 房、"624" = 6 樓 24 房

export function parseBedId(bedId) {
  return {
    floor: bedId.slice(0, -2),
    room: bedId.slice(-2),
  };
}

// 依 bed_id 把床位分組成 { floor -> beds[] }，floor 依數字大小排序
export function groupBedsByFloor(beds) {
  const floors = new Map();
  for (const bed of beds) {
    const { floor } = parseBedId(bed.bed_id);
    if (!floors.has(floor)) floors.set(floor, []);
    floors.get(floor).push(bed);
  }
  for (const list of floors.values()) {
    list.sort((a, b) => a.bed_id.localeCompare(b.bed_id));
  }
  return new Map([...floors.entries()].sort((a, b) => a[0].localeCompare(b[0])));
}

// ---------------------------------------------------------------------------
// 平面圖幾何設定：每層樓固定 24 床，畫成上排 7 間病房（3 間三人房、3 間雙人房、
// 1 間單人房）+ 下排 4 間病房（四人房、雙人房、2 間單人房）+ 右下角開放式護理站。
// 房間寬度依床數比例分配，座標單位對應 FloorPlan SVG 的 viewBox。
// 床位依 bed_id 排序後的 index（0–23）依序對應到下面各房間，房內床位由左至右填入。
// ---------------------------------------------------------------------------

export const FLOOR_PLAN_VIEWBOX = { width: 1200, height: 620 };

const BED_WIDTH = 40;
const BED_HEIGHT = 65;
const BED_GAP = 10;
const BED_MARGIN = 20; // 床與「遠離走廊那側」牆的間距

// 上排 7 間房（門朝下接走廊）+ 下排 4 間房（門朝上接走廊），寬度依床數比例分配
const TOP_ROOMS = [
  { x: 50, width: 170, beds: 3 },
  { x: 220, width: 170, beds: 3 },
  { x: 390, width: 170, beds: 3 },
  { x: 560, width: 140, beds: 2 },
  { x: 700, width: 140, beds: 2 },
  { x: 840, width: 140, beds: 2 },
  { x: 980, width: 170, beds: 1 },
];

const BOTTOM_ROOMS = [
  { x: 50, width: 220, beds: 4 },
  { x: 270, width: 140, beds: 2 },
  { x: 410, width: 120, beds: 1 },
  { x: 530, width: 120, beds: 1 },
];

const ROOM_Y = { top: 50, bottom: 350 };
const ROOM_HEIGHT = 200;

export const NURSES_STATION = { x: 650, y: 350, width: 500, height: 200 };

export const FLOOR_PLAN_ROOMS = [
  ...TOP_ROOMS.map((room) => ({ ...room, y: ROOM_Y.top, height: ROOM_HEIGHT, doorSide: "bottom" })),
  ...BOTTOM_ROOMS.map((room) => ({ ...room, y: ROOM_Y.bottom, height: ROOM_HEIGHT, doorSide: "top" })),
];

// 床位總數（依序填入 FLOOR_PLAN_ROOMS，每間房從左到右排滿再換下一間）
export const FLOOR_PLAN_BED_COUNT = FLOOR_PLAN_ROOMS.reduce((sum, room) => sum + room.beds, 0);

// 房間內第 bedIndex（0-based）張床的圖示位置：水平置中排列、貼著遠離走廊門的那側牆
export function getBedIconRectInRoom(room, bedIndex) {
  const contentWidth = room.beds * BED_WIDTH + (room.beds - 1) * BED_GAP;
  const startX = room.x + (room.width - contentWidth) / 2;
  const x = startX + bedIndex * (BED_WIDTH + BED_GAP);
  const y =
    room.doorSide === "bottom"
      ? room.y + BED_MARGIN
      : room.y + room.height - BED_MARGIN - BED_HEIGHT;
  return { x, y, width: BED_WIDTH, height: BED_HEIGHT };
}

// 攤平成「每張床一筆」的清單，依房間順序、房內由左到右；bedIndexInRoom 只在房內計數，
// 每間房都是從 0 重新開始（不跨房累加），用來顯示 A/B/C/D 床號
export const FLOOR_PLAN_BED_SLOTS = FLOOR_PLAN_ROOMS.flatMap((room) =>
  Array.from({ length: room.beds }, (_, bedIndex) => ({
    room,
    bedIndexInRoom: bedIndex,
    icon: getBedIconRectInRoom(room, bedIndex),
  })),
);

// 房內床號：每間房各自從 A 開始（不跨房累加）
export function bedIndexToLetter(bedIndexInRoom) {
  return String.fromCharCode(65 + bedIndexInRoom);
}

// 互動床位標記要放的中心點（百分比座標，相對 viewBox），index 對應排序後的床位清單
export function getBedSlotCenterPercent(index) {
  const { icon } = FLOOR_PLAN_BED_SLOTS[index];
  return {
    left: ((icon.x + icon.width / 2) / FLOOR_PLAN_VIEWBOX.width) * 100,
    top: ((icon.y + icon.height / 2) / FLOOR_PLAN_VIEWBOX.height) * 100,
  };
}

// 房號標籤放在房內「床位與門之間」的空白處，避免跟床位圖示/標記重疊
const BED_ZONE_HEIGHT = BED_MARGIN + BED_HEIGHT;
const ROOM_LABEL_Y_OFFSET = {
  bottom: BED_ZONE_HEIGHT + (ROOM_HEIGHT - BED_ZONE_HEIGHT) / 2, // 床貼上緣，標籤放下半空白區
  top: (ROOM_HEIGHT - BED_ZONE_HEIGHT) / 2, // 床貼下緣，標籤放上半空白區
};

// 每間房的房號標籤：房號是獨立於 bed_id 的房間序號（每層樓 1–11，跟床號 A/B/C/D 分開），
// 回傳每間房要顯示的文字與位置（百分比座標）
export function getRoomLabels() {
  return FLOOR_PLAN_ROOMS.map((room, index) => ({
    key: index,
    label: `${index + 1}`,
    left: ((room.x + room.width / 2) / FLOOR_PLAN_VIEWBOX.width) * 100,
    top: ((room.y + ROOM_LABEL_Y_OFFSET[room.doorSide]) / FLOOR_PLAN_VIEWBOX.height) * 100,
  }));
}

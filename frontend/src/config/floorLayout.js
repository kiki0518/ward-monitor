// Overview 平面圖的空間佈局設定（前端自訂，非後端資料）
// bed_id 格式為「樓層(1碼) + 房號(2碼)」，例如 "101" = 1 樓 01 房、"606" = 6 樓 06 房

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

// 走廊式平面圖：把單一樓層的床位分成上排/下排，中間夾一條走廊
export function splitIntoRows(beds) {
  const mid = Math.ceil(beds.length / 2);
  return { topRow: beds.slice(0, mid), bottomRow: beds.slice(mid) };
}

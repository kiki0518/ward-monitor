// 粗顆粒度的相對時間：剛剛 / N 分鐘前 / N 小時前 / N 天前，不用到精確秒數。
// 畫面會隨 WS 推送頻繁重繪，時間文字自然就會跟著更新，不用額外開計時器。
export function formatRelativeTime(isoString) {
  if (!isoString) return "";

  const diffMin = Math.floor((Date.now() - new Date(isoString).getTime()) / 60000);
  if (diffMin < 1) return "剛剛";
  if (diffMin < 60) return `${diffMin} 分鐘前`;

  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小時前`;

  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay} 天前`;
}

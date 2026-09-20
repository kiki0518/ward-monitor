// 護理師畫面的「優先通知」：頁面要開著才會收到（靠 /ws/overview 的既有推送去比對前後
// priority，不是後端主動 push 給特定客戶端），所以用聲音 + 瀏覽器通知盡量讓人在滑別的
// App 時也能注意到。沒有 Service Worker/背景推播，鎖螢幕時不保證會響，這是現階段的已知限制。

let audioCtx = null;

// 短促的兩聲嗶，不用外部音檔，Web Audio 振盪器現場生成即可
export function playAlertBeep() {
  try {
    audioCtx ??= new (window.AudioContext || window.webkitAudioContext)();
    const now = audioCtx.currentTime;
    [0, 0.18].forEach((offset) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.001, now + offset);
      gain.gain.exponentialRampToValueAtTime(0.2, now + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + offset + 0.15);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + offset);
      osc.stop(now + offset + 0.16);
    });
  } catch {
    // 瀏覽器不支援 Web Audio，或使用者還沒跟頁面互動過導致 AudioContext 建立失敗時靜默跳過
  }
}

export function requestNotificationPermission() {
  if (!("Notification" in window)) return;
  if (Notification.permission === "default") {
    Notification.requestPermission();
  }
}

export function showBrowserNotification(title, body) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    new Notification(title, { body, tag: "ward-monitor-alert" });
  } catch {
    // 部分瀏覽器（尤其行動版）建構子行為不一致，通知失敗時不影響頁面內的橫幅提示
  }
}

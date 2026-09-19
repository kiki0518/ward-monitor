// F2 負責
// 體徵面板：心跳/血氧用即時滾動曲線，血壓/體溫用數值卡片
// history 由 RoomDetail 在收到每筆 WS state 訊息時累積傳入（最近 N 筆 Vitals）

import { Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import "./VitalsPanel.css";

export default function VitalsPanel({ history }) {
  const latest = history[history.length - 1];

  if (!latest) {
    return <div className="vitals-panel vitals-panel--loading">等待生理數據...</div>;
  }

  const chartData = history.map((v) => ({
    time: new Date(v.ts).toLocaleTimeString("zh-TW", { hour12: false }),
    heart_rate: v.heart_rate,
    spo2: v.spo2,
  }));

  return (
    <div className="vitals-panel">
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <XAxis dataKey="time" tick={{ fontSize: 11 }} minTickGap={24} />
          <YAxis yAxisId="hr" domain={[40, 140]} hide />
          <YAxis yAxisId="spo2" domain={[85, 100]} hide />
          <Tooltip />
          <Legend verticalAlign="top" height={24} wrapperStyle={{ top: -10 }} />
          <Line yAxisId="hr" type="monotone" dataKey="heart_rate" name="心跳 (bpm)" stroke="#c62828" dot={false} isAnimationActive={false} />
          <Line yAxisId="spo2" type="monotone" dataKey="spo2" name="血氧 (%)" stroke="#1565c0" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="vitals-panel__cards">
        <div className="vitals-card">
          <span className="vitals-card__label">心跳</span>
          <span className="vitals-card__value" style={{ color: "#c62828" }}>
            {latest.heart_rate}
          </span>
          <span className="vitals-card__unit">bpm</span>
        </div>
        <div className="vitals-card">
          <span className="vitals-card__label">血氧</span>
          <span className="vitals-card__value" style={{ color: "#1565c0" }}>
            {latest.spo2}
          </span>
          <span className="vitals-card__unit">%</span>
        </div>
        <div className="vitals-card">
          <span className="vitals-card__label">血壓</span>
          <span className="vitals-card__value">
            {latest.bp_systolic}/{latest.bp_diastolic}
          </span>
          <span className="vitals-card__unit">mmHg</span>
        </div>
        <div className="vitals-card">
          <span className="vitals-card__label">體溫</span>
          <span className="vitals-card__value">{latest.temperature}</span>
          <span className="vitals-card__unit">°C</span>
        </div>
      </div>
    </div>
  );
}

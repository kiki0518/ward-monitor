// F2 負責
// 體徵面板：心跳/血氧用即時滾動曲線，血壓/體溫用數值卡片
// history 由 RoomDetail 在收到每筆 WS state 訊息時累積傳入（最近 N 筆 Vitals）

import { Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const STAT_STYLE = {
  heart_rate: { label: "心跳", unit: "bpm", bg: "bg-red-50", text: "text-red-600" },
  spo2: { label: "血氧", unit: "%", bg: "bg-[#e2f3ef]", text: "text-[#16796b]" },
  bp: { label: "血壓", unit: "mmHg", bg: "bg-[#e8edf2]", text: "text-[#42657a]" },
  temperature: { label: "體溫", unit: "°C", bg: "bg-amber-50", text: "text-amber-600" },
};

export default function VitalsPanel({ history }) {
  const latest = history[history.length - 1];

  if (!latest) {
    return <div className="text-sm text-[#82958e] py-6">等待生理數據...</div>;
  }

  const chartData = history.map((v) => ({
    time: new Date(v.ts).toLocaleTimeString("zh-TW", { hour12: false }),
    heart_rate: v.heart_rate,
    spo2: v.spo2,
  }));

  return (
    <div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <XAxis dataKey="time" tick={{ fontSize: 11 }} minTickGap={24} />
          <YAxis yAxisId="hr" domain={[40, 140]} hide />
          <YAxis yAxisId="spo2" domain={[85, 100]} hide />
          <Tooltip />
          <Legend verticalAlign="top" height={24} wrapperStyle={{ top: -10 }} />
          <Line yAxisId="hr" type="monotone" dataKey="heart_rate" name="心跳 (bpm)" stroke="#ef4444" dot={false} isAnimationActive={false} />
          <Line yAxisId="spo2" type="monotone" dataKey="spo2" name="血氧 (%)" stroke="#16796b" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="grid grid-cols-2 gap-3 mt-2">
        <div className={`flex flex-col items-start p-4 rounded-xl ${STAT_STYLE.heart_rate.bg}`}>
          <span className="text-xs text-[#6c8179]">{STAT_STYLE.heart_rate.label}</span>
          <span className={`text-2xl font-semibold ${STAT_STYLE.heart_rate.text}`}>{latest.heart_rate}</span>
          <span className="text-[11px] text-[#82958e]">{STAT_STYLE.heart_rate.unit}</span>
        </div>
        <div className={`flex flex-col items-start p-4 rounded-xl ${STAT_STYLE.spo2.bg}`}>
          <span className="text-xs text-[#6c8179]">{STAT_STYLE.spo2.label}</span>
          <span className={`text-2xl font-semibold ${STAT_STYLE.spo2.text}`}>{latest.spo2}</span>
          <span className="text-[11px] text-[#82958e]">{STAT_STYLE.spo2.unit}</span>
        </div>
        <div className={`flex flex-col items-start p-4 rounded-xl ${STAT_STYLE.bp.bg}`}>
          <span className="text-xs text-[#6c8179]">{STAT_STYLE.bp.label}</span>
          <span className={`text-2xl font-semibold ${STAT_STYLE.bp.text}`}>
            {latest.bp_systolic}/{latest.bp_diastolic}
          </span>
          <span className="text-[11px] text-[#82958e]">{STAT_STYLE.bp.unit}</span>
        </div>
        <div className={`flex flex-col items-start p-4 rounded-xl ${STAT_STYLE.temperature.bg}`}>
          <span className="text-xs text-[#6c8179]">{STAT_STYLE.temperature.label}</span>
          <span className={`text-2xl font-semibold ${STAT_STYLE.temperature.text}`}>{latest.temperature}</span>
          <span className="text-[11px] text-[#82958e]">{STAT_STYLE.temperature.unit}</span>
        </div>
      </div>
    </div>
  );
}

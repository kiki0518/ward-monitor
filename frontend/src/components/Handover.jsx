import { useEffect, useRef, useState } from "react";
import { fetchBeds, handoverRequest } from "../services/ws";
import "./Handover.css";

const SHIFTS = { day: "白班", evening: "小夜班", night: "大夜班" };
const FIELDS = { completed_actions: "已完成的處理", follow_up: "需要下一位處理", notes: "備註" };
function today() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

export function HandoverHistory({ bedId, refreshKey }) {
  const [records, setRecords] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    handoverRequest(bedId, "handovers").then(data => {
      if (active) { setRecords(data); setError(""); }
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [bedId, refreshKey]);
  return <section className="handover-panel">
    <h2 className="text-base font-semibold text-[#18332d] mb-4">交班紀錄</h2>
    {error && <p role="alert">{error}</p>}
    {!error && records.length === 0 && <p>目前無交班紀錄</p>}
    {records.map(record => <article className="handover-record" key={record.id}>
      <h3>{record.handover_date}・{SHIFTS[record.shift]}</h3>
      <small>由 {record.source_event_ids.length} 筆處理紀錄整理・送出時間：{new Date(record.submitted_at).toLocaleString("zh-TW")}</small>
      {Object.entries(FIELDS).map(([key, label]) => <div key={key}><strong>{label}</strong><p>{record[key] || "無"}</p></div>)}
    </article>)}
  </section>;
}

export default function HandoverButton({ bedId, onSaved }) {
  const [open, setOpen] = useState(false);
  return <>
    <button className="handover-primary" onClick={() => setOpen(true)}>產生交班紀錄</button>
    {open && <Editor bedId={bedId} onClose={() => setOpen(false)} onSaved={onSaved} />}
  </>;
}

function Editor({ bedId, onClose, onSaved }) {
  const dialog = useRef(null);
  const [beds, setBeds] = useState([]);
  const [selectedBed, setSelectedBed] = useState(bedId || "");
  const [sources, setSources] = useState([]);
  const [selected, setSelected] = useState([]);
  const [draft, setDraft] = useState(null);
  const [form, setForm] = useState({ handover_date: today(), shift: "day" });
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(Boolean(bedId));
  const [error, setError] = useState("");
  useEffect(() => { dialog.current.showModal(); }, []);
  useEffect(() => {
    let active = true;
    fetchBeds().then(data => { if (active) setBeds(data); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!selectedBed) return;
    let active = true;
    handoverRequest(selectedBed, "handover-sources").then(data => {
      if (active) { setSources(data); setSelected(data.filter(r => !r.included_in_handover).map(r => r.event_id)); }
    }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedBed]);
  function change(key, value) { setForm(previous => ({ ...previous, [key]: value })); }
  async function generate() {
    setBusy(true); setError("");
    try {
      const result = await handoverRequest(selectedBed, "handover-drafts", {
        handover_date: form.handover_date, shift: form.shift, source_event_ids: selected,
      });
      setDraft(result);
      setForm({ handover_date: result.handover_date, shift: result.shift, ...Object.fromEntries(Object.keys(FIELDS).map(key => [key, result[key]])) });
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function save(event) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await handoverRequest(selectedBed, `handover-drafts/${draft.id}/submit`, form);
      onSaved?.(); onClose();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="handover-dialog" aria-labelledby="handover-title" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={draft ? save : event => { event.preventDefault(); generate(); }}>
      <h2 id="handover-title">{draft ? "編輯交班紀錄" : "產生交班紀錄"}</h2>
      <p>{draft ? "請確認並修改 AI 整理的內容，按送出後儲存。" : "選擇要整理的處理紀錄，預設勾選尚未交班的紀錄。"}</p>
      <fieldset disabled={busy}>
        <label>病人{bedId || draft ? (
          <input readOnly value={`${selectedBed} 床${(draft?.patient_name || beds.find(bed => bed.bed_id === selectedBed)?.patient_name) ? `・${draft?.patient_name || beds.find(bed => bed.bed_id === selectedBed)?.patient_name}` : ""}`} />
        ) : (
          <select value={selectedBed} required onChange={event => { setSelectedBed(event.target.value); setSources([]); setSelected([]); setLoading(Boolean(event.target.value)); setError(""); }}>
            <option value="">請選擇病人</option>
            {beds.map(bed => <option key={bed.bed_id} value={bed.bed_id}>{bed.bed_id} 床・{bed.patient_name}</option>)}
          </select>
        )}</label>
        <div className="handover-date-row">
          <label>交班日期<input type="date" required value={form.handover_date} onChange={event => change("handover_date", event.target.value)} /></label>
          <label>班別<select value={form.shift} onChange={event => change("shift", event.target.value)}>{Object.entries(SHIFTS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        </div>
        {!draft && <div className="handover-sources">
          {loading && <p role="status">載入處理紀錄中…</p>}
          {selectedBed && !loading && !error && sources.length === 0 && <p>此病人目前沒有可整理的處理紀錄。</p>}
          {sources.map(source => <label className="handover-source" key={source.event_id}>
            <input type="checkbox" checked={selected.includes(source.event_id)} onChange={event => setSelected(previous => event.target.checked ? [...previous, source.event_id] : previous.filter(id => id !== source.event_id))} />
            <span><strong>{new Date(source.resolved_at).toLocaleString("zh-TW")}{source.included_in_handover ? "（曾交班）" : ""}</strong>
              {Object.entries(FIELDS).map(([key, label]) => <span className="handover-source-text" key={key}>{label}：{source[key] || "無"}</span>)}
            </span>
          </label>)}
        </div>}
        {draft && Object.entries(FIELDS).map(([key, label]) => <label key={key}>{label}<textarea rows={5} maxLength={20000} required={key !== "notes"} value={form[key]} onChange={event => change(key, event.target.value)} /></label>)}
      </fieldset>
      {error && <p className="handover-error" role="alert">{error}</p>}
      {busy && <p role="status">{draft ? "儲存中…" : "AI 正在整理，請稍候…"}</p>}
      <div className="handover-actions">
        <button type="button" disabled={busy} onClick={onClose}>取消</button>
        <button className="handover-primary" type="submit" disabled={busy || loading || (!draft && !selected.length) || (draft && (!form.completed_actions.trim() || !form.follow_up.trim()))}>{draft ? "送出" : "AI 整理"}</button>
      </div>
    </form>
  </dialog>;
}

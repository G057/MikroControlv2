import { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import toast from 'react-hot-toast';
import { eventsAPI, routersAPI, type EventReport } from '../services/api';
import type { RouterDevice } from '../types';
import { useTheme } from '../contexts/ThemeContext';

function EventBars({ report, field, color, title }: { report: EventReport; field: 'critical' | 'warning' | 'info'; color: string; title: string }) {
  const maximum = Math.max(1, ...report.series.map(row => row[field]));
  return (
    <div>
      <p className="text-sm font-semibold mb-3">{title}</p>
      <div className="flex items-end gap-4 h-64 border-b border-l px-4 pt-4" style={{ borderColor: '#cbd5e1' }}>
        {report.series.map(row => {
          const value = row[field];
          const height = value ? Math.max(8, (value / maximum) * 190) : 0;
          return <div key={row.date} className="flex-1 min-w-0 h-full flex flex-col justify-end items-center gap-2">
            <span className="text-xs font-bold">{value || '-'}</span>
            <div className="w-full max-w-20 rounded-t transition-all" style={{ height, background: color }} />
            <span className="text-[11px] whitespace-nowrap">{row.date}</span>
          </div>;
        })}
      </div>
      <p className="text-xs mt-2 text-slate-500">Escala: 0 a {maximum}</p>
    </div>
  );
}

export default function EventReportPage() {
  const { c } = useTheme();
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [routerId, setRouterId] = useState(0);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [report, setReport] = useState<EventReport | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => { routersAPI.list().then(setRouters).catch(() => {}); }, []);
  const load = async () => {
    if (!routerId) return toast.error('Seleccioná un router');
    try { setReport(await eventsAPI.report(routerId, from || undefined, to || undefined)); }
    catch (e: any) { toast.error(e.message); }
  };
  const pdf = async () => {
    if (!reportRef.current || !report) return;
    const canvas = await html2canvas(reportRef.current, { scale: 2, backgroundColor: '#ffffff' });
    const doc = new jsPDF('p', 'mm', 'a4');
    const width = 190;
    doc.addImage(canvas.toDataURL('image/png'), 'PNG', 10, 10, width, canvas.height * width / canvas.width);
    doc.save(`informe_eventos_${report.router.name.replace(/\s+/g, '_')}.pdf`);
  };

  return <div className="space-y-5">
    <div><h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Informe de Eventos</h1><p className="text-sm" style={{ color: c.textMuted }}>Resumen temporal por router para entregar al edificio.</p></div>
    <div className="card flex flex-wrap gap-3"><select value={routerId} onChange={e => setRouterId(Number(e.target.value))} className="input"><option value={0}>Seleccionar router</option>{routers.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select><input type="date" value={from} onChange={e => setFrom(e.target.value)} className="input" /><input type="date" value={to} onChange={e => setTo(e.target.value)} className="input" /><button onClick={load} className="btn-primary">Generar informe</button>{report && <button onClick={pdf} className="btn-secondary"><Download className="w-4 h-4 inline mr-1" />PDF</button>}</div>
    {report && <div ref={reportRef} className="card space-y-6" style={{ background: '#fff', color: '#1e293b' }}>
      <div><h2 className="text-xl font-bold">Informe de eventos - {report.router.name}</h2><p>{report.router.clientName || 'Sin cliente asignado'} | {from || 'Inicio'} a {to || 'Actualidad'}</p></div>
      <div className="grid grid-cols-4 gap-3"><div>Total: <b>{report.summary.total}</b></div><div>Críticos: <b style={{ color: '#ef4444' }}>{report.summary.critical}</b></div><div>Warnings: <b style={{ color: '#f59e0b' }}>{report.summary.warning}</b></div><div>Info: <b style={{ color: '#3b82f6' }}>{report.summary.info}</b></div></div>
      <EventBars report={report} field="critical" color="#ef4444" title="Eventos críticos por día" />
      <EventBars report={report} field="warning" color="#f59e0b" title="Advertencias por día" />
      <EventBars report={report} field="info" color="#3b82f6" title="Eventos informativos por día" />
      <p className="text-sm">Cada gráfico usa una escala independiente y muestra el valor exacto sobre cada barra.</p>
    </div>}
  </div>;
}

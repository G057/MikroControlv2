import { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import toast from 'react-hot-toast';
import { eventsAPI, routersAPI, type EventReport } from '../services/api';
import type { RouterDevice } from '../types';
import { useTheme } from '../contexts/ThemeContext';

function EventBars({ report, field, color, title, mode }: { report: EventReport; field: 'critical' | 'warning' | 'info'; color: string; title: string; mode: 'daily' | 'average' }) {
  const rows = mode === 'average' ? [{ date: `Promedio (${report.periodDays} días)`, [field]: Number((report.summary[field] / report.periodDays).toFixed(1)) }] : report.series;
  const maximum = Math.max(1, ...rows.map(row => Number(row[field])));
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between"><p className="text-sm font-semibold">{title}</p><span className="text-xs text-slate-500">Máximo diario: {maximum}</span></div>
      <div className="space-y-2">
        {rows.map(row => {
          const value = Number(row[field]);
          return <div key={row.date} className="grid grid-cols-[90px_1fr_48px] items-center gap-3 text-xs">
            <span className="font-mono text-slate-600">{row.date}</span>
            <div className="h-6 rounded bg-slate-100 overflow-hidden">
              <div className="h-full min-w-0 rounded flex items-center px-2 text-white font-bold" style={{ width: value ? `${Math.max(3, (value / maximum) * 100)}%` : '0%', background: color }} />
            </div>
            <span className="text-right font-bold">{value}</span>
          </div>;
        })}
      </div>
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
  const [chartMode, setChartMode] = useState<'daily' | 'average'>('daily');
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
    <div className="card flex flex-wrap gap-3"><select value={routerId} onChange={e => setRouterId(Number(e.target.value))} className="input"><option value={0}>Seleccionar router</option>{routers.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select><input type="date" value={from} onChange={e => setFrom(e.target.value)} className="input" /><input type="date" value={to} onChange={e => setTo(e.target.value)} className="input" /><button onClick={load} className="btn-primary">Generar informe</button>{report && <><div className="flex rounded-lg overflow-hidden border"><button onClick={() => setChartMode('daily')} className="px-3 text-sm" style={{ background: chartMode === 'daily' ? c.accent : 'transparent', color: chartMode === 'daily' ? '#fff' : c.textSecondary }}>Por día</button><button onClick={() => setChartMode('average')} className="px-3 text-sm" style={{ background: chartMode === 'average' ? c.accent : 'transparent', color: chartMode === 'average' ? '#fff' : c.textSecondary }}>Promedio</button></div><button onClick={pdf} className="btn-secondary"><Download className="w-4 h-4 inline mr-1" />PDF</button></>}</div>
    {report && <div ref={reportRef} className="card space-y-6" style={{ background: '#fff', color: '#1e293b' }}>
      <div><h2 className="text-xl font-bold">Informe de eventos - {report.router.name}</h2><p>{report.router.clientName || 'Sin cliente asignado'} | {from || 'Inicio'} a {to || 'Actualidad'}</p></div>
      <div className="grid grid-cols-4 gap-3"><div>Total: <b>{report.summary.total}</b></div><div>Críticos: <b style={{ color: '#ef4444' }}>{report.summary.critical}</b></div><div>Warnings: <b style={{ color: '#f59e0b' }}>{report.summary.warning}</b></div><div>Info: <b style={{ color: '#3b82f6' }}>{report.summary.info}</b></div></div>
      <EventBars report={report} field="critical" color="#ef4444" title={chartMode === 'daily' ? 'Eventos críticos por día' : 'Promedio diario de críticos'} mode={chartMode} />
      <EventBars report={report} field="warning" color="#f59e0b" title={chartMode === 'daily' ? 'Advertencias por día' : 'Promedio diario de advertencias'} mode={chartMode} />
      <EventBars report={report} field="info" color="#3b82f6" title={chartMode === 'daily' ? 'Eventos informativos por día' : 'Promedio diario de informativos'} mode={chartMode} />
      <p className="text-sm">Cada gráfico usa una escala independiente y muestra el valor exacto sobre cada barra.</p>
    </div>}
  </div>;
}

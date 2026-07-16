import { useEffect, useState } from 'react';
import * as XLSX from 'xlsx';
import { Download, Search } from 'lucide-react';
import toast from 'react-hot-toast';
import { eventsAPI, routersAPI, type EventExplorerItem } from '../services/api';
import type { RouterDevice } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import { formatDateTime } from '../utils/date';

export default function EventExplorerPage() {
  const { c } = useTheme();
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [items, setItems] = useState<EventExplorerItem[]>([]);
  const [total, setTotal] = useState(0);
  const [routerId, setRouterId] = useState(0);
  const [severity, setSeverity] = useState('');
  const [search, setSearch] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [loading, setLoading] = useState(false);
  const params = { router_id: routerId || undefined, severity: severity || undefined, search: search || undefined, date_from: from || undefined, date_to: to || undefined };
  const load = async () => { setLoading(true); try { const data = await eventsAPI.explorer({ ...params, page_size: 200 }); setItems(data.items); setTotal(data.total); } catch (e: any) { toast.error(e.message); } finally { setLoading(false); } };
  useEffect(() => { routersAPI.list().then(setRouters).catch(() => {}); load(); }, []);
  const exportXlsx = async () => {
    try {
      const data = await eventsAPI.explorer({ ...params, page_size: 1000 });
      const rows = data.items.map(e => ({ Recibido: formatDateTime(e.receivedAt), Router: e.routerName, Severidad: e.severity, Tipo: e.eventType, Topics: e.topics, Mensaje: e.message, Fuente: e.source, 'Hora RouterOS': e.routerTime }));
      const book = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(book, XLSX.utils.json_to_sheet(rows), 'Eventos');
      XLSX.writeFile(book, `eventos_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch (e: any) { toast.error(e.message); }
  };
  return <div className="space-y-5"><div className="flex items-center justify-between gap-3"><div><h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Explorador de Eventos</h1><p className="text-sm" style={{ color: c.textMuted }}>Búsqueda histórica por router, fecha, severidad y texto.</p></div><button onClick={exportXlsx} className="btn-secondary text-sm"><Download className="w-4 h-4 inline mr-1" />Excel</button></div>
    <div className="card grid grid-cols-1 md:grid-cols-6 gap-3"><select value={routerId} onChange={e => setRouterId(Number(e.target.value))} className="input"><option value={0}>Todos los routers</option>{routers.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select><select value={severity} onChange={e => setSeverity(e.target.value)} className="input"><option value="">Todas las severidades</option><option value="critical">Crítico</option><option value="warning">Advertencia</option><option value="info">Info</option></select><input type="datetime-local" value={from} onChange={e => setFrom(e.target.value)} className="input" /><input type="datetime-local" value={to} onChange={e => setTo(e.target.value)} className="input" /><input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} placeholder="Buscar mensaje" className="input" /><button onClick={load} className="btn-primary"><Search className="w-4 h-4 inline mr-1" />Buscar</button></div>
    <p className="text-sm" style={{ color: c.textMuted }}>{loading ? 'Buscando...' : `${total} eventos encontrados. Mostrando los últimos ${items.length}.`}</p>
    <div className="card overflow-x-auto"><table className="w-full text-sm"><thead style={{ color: c.textMuted }}><tr className="text-left"><th className="p-2">Recibido</th><th className="p-2">Router</th><th className="p-2">Severidad</th><th className="p-2">Evento</th><th className="p-2">Mensaje</th></tr></thead><tbody>{items.map(e => <tr key={e.id} style={{ borderTop: `1px solid ${c.border}` }}><td className="p-2 whitespace-nowrap">{formatDateTime(e.receivedAt)}</td><td className="p-2">{e.routerName}</td><td className="p-2">{e.severity}</td><td className="p-2">{e.eventType}</td><td className="p-2">{e.message}</td></tr>)}</tbody></table></div></div>;
}

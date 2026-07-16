import { useState, useEffect } from 'react';
import { eventsAPI, alertsAPI, type RouterEvent } from '../services/api';
import type { RouterDevice } from '../types';
import { routersAPI } from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import { CheckCircle, AlertTriangle, AlertCircle, RefreshCw, ChevronDown, Info, Search, Server, X, Save } from 'lucide-react';
import toast from 'react-hot-toast';
import { formatDateTime, formatTime } from '../utils/date';

function TopicBadge({ topic, c }: { topic: string; c: any }) {
  const t = topic.trim().toLowerCase();
  const map: Record<string, [string, string]> = {
    ipsec: [c.redBg, c.red], error: [c.redBg, c.red],
    dhcp: [c.yellowBg, c.yellow], warning: [c.yellowBg, c.yellow],
    pppoe: [c.purpleBg, c.purple], system: [c.bgHover, c.textMuted],
    account: [c.blueBg, c.blue], certificate: [c.orangeBg, c.orange],
    l2tp: [c.cyanBg, c.cyan], interface: [c.greenBg, c.green],
    ppp: [c.purpleBg, c.purple],
  };
  const [bg, col] = map[t] || [c.bgHover, c.textSecondary];
  return <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold" style={{ background: bg, color: col }}>{topic.trim()}</span>;
}

function ResolveModal({ visible, onClose, onConfirm, title, c }: {
  visible: boolean; onClose: () => void; onConfirm: (comment: string) => void; title: string; c: any;
}) {
  const [comment, setComment] = useState('');
  if (!visible) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
      <div className="card w-full max-w-md m-4" style={{ background: c.bgCard }}>
        <div className="flex items-center justify-between p-4" style={{ borderBottom: `1px solid ${c.border}` }}>
          <h2 className="text-sm font-bold" style={{ color: c.textPrimary }}>Resolver Alerta</h2>
          <button onClick={onClose} style={{ color: c.textMuted }}><X className="w-5 h-5" /></button>
        </div>
        <div className="p-4 space-y-3">
          <p className="text-sm" style={{ color: c.textSecondary }}>{title}</p>
          <div>
            <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Comentario (opcional)</label>
            <textarea className="input w-full text-sm" rows={3} placeholder="Describí qué se hizo para resolver..."
              value={comment} onChange={e => setComment(e.target.value)} style={{ resize: 'vertical' }} />
          </div>
        </div>
        <div className="flex gap-2 p-4" style={{ borderTop: `1px solid ${c.border}` }}>
          <button onClick={() => { onConfirm(comment); setComment(''); }} className="btn-primary text-sm flex-1">
            <Save className="w-4 h-4 inline mr-1" />Resolver
          </button>
          <button onClick={() => { onClose(); setComment(''); }} className="btn-secondary text-sm">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

export default function EventsPage() {
  const [events, setEvents] = useState<RouterEvent[]>([]);
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [loading, setLoading] = useState(false);
  const [severityFilter, setSeverityFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [routerFilter, setRouterFilter] = useState(0);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [counts, setCounts] = useState({ critical: 0, warning: 0, info: 0, unresolved: 0 });
  const [resolveModal, setResolveModal] = useState<{ visible: boolean; eventId: string; title: string }>({ visible: false, eventId: '', title: '' });
  const { c } = useTheme();

  const loadCounts = async () => {
    try {
      const params: any = {};
      if (sourceFilter !== 'all') params.source = sourceFilter;
      if (routerFilter) params.router_id = routerFilter;
      if (search.trim()) params.search = search.trim();
      const ct = await eventsAPI.countsBySeverity(params);
      setCounts(ct);
    } catch {}
  };

  const load = async () => {
    setLoading(true);
    try {
      // Keep the first render responsive; the API default is also a recent
      // window rather than the whole event history.
      const params: any = { limit: 200 };
      if (severityFilter === 'unresolved') {
        params.is_resolved = false;
        params.source = 'health';
      } else if (severityFilter !== 'all') {
        params.severity = severityFilter;
      }
      if (sourceFilter !== 'all' && severityFilter !== 'unresolved') params.source = sourceFilter;
      if (routerFilter) params.router_id = routerFilter;
      if (search.trim()) params.search = search.trim();
      const data = await eventsAPI.list(params);
      setEvents(data);
    } catch (err: any) { toast.error(err.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { routersAPI.list().then(setRouters).catch(() => {}); }, []);
  useEffect(() => { load(); loadCounts(); }, [severityFilter, sourceFilter, routerFilter]);

  const handleRefresh = async () => {
    setLoading(true);
    try { await eventsAPI.refresh(); await load(); toast.success('Logs actualizados'); }
    catch (err: any) { toast.error(err.message); }
    finally { setLoading(false); }
  };

  const handleResolveClick = (ev: RouterEvent) => {
    if (ev.source !== 'health') return;
    setResolveModal({ visible: true, eventId: ev.id, title: ev.message || '' });
  };

  const handleResolveConfirm = async (comment: string) => {
    const id = resolveModal.eventId;
    if (!id.startsWith('a_')) return;
    try {
      await alertsAPI.resolve(parseInt(id.replace('a_', '')), comment || undefined);
      toast.success('Alerta resuelta');
      setResolveModal({ visible: false, eventId: '', title: '' });
      load();
    } catch (err: any) { toast.error(err.message); }
  };

  const sevMap: Record<string, { icon: any; color: string; bg: string; label: string }> = {
    critical: { icon: AlertCircle, color: c.red, bg: c.redBg, label: 'Crítico' },
    warning: { icon: AlertTriangle, color: c.yellow, bg: c.yellowBg, label: 'Advertencia' },
    info: { icon: Info, color: c.blue, bg: c.blueBg, label: 'Info' },
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Eventos</h1>
        <button onClick={handleRefresh} disabled={loading} className="btn-secondary text-sm">
          <RefreshCw className={`w-4 h-4 inline mr-1 ${loading ? 'animate-spin' : ''}`} />Actualizar logs
        </button>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {(['critical', 'warning', 'info', 'unresolved'] as const).map(key => {
          if (key === 'unresolved') {
            const active = severityFilter === 'unresolved';
            return (
              <button key={key} onClick={() => setSeverityFilter(active ? 'all' : 'unresolved')}
                className="card text-left transition-all"
                style={{ background: active ? c.orangeBg : c.bgCard, borderColor: active ? c.orange : c.border }}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-medium" style={{ color: c.textMuted }}>Sin resolver</p>
                    <p className="text-2xl font-bold" style={{ color: c.orange }}>{counts.unresolved}</p>
                  </div>
                  <AlertCircle className="w-6 h-6" style={{ color: c.orange }} />
                </div>
              </button>
            );
          }
          const s = sevMap[key];
          return (
            <button key={key} onClick={() => setSeverityFilter(severityFilter === key ? 'all' : key)}
              className="card text-left transition-all"
              style={{ background: severityFilter === key ? s.bg : c.bgCard, borderColor: severityFilter === key ? s.color : c.border }}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium" style={{ color: c.textMuted }}>{s.label}</p>
                  <p className="text-2xl font-bold" style={{ color: s.color }}>{counts[key]}</p>
                </div>
                <s.icon className="w-6 h-6" style={{ color: s.color }} />
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 rounded-lg p-1" style={{ background: c.bgCard, border: `1px solid ${c.border}` }}>
          {[{ key: 'all', label: 'Todos' }, { key: 'router', label: 'Router logs' }, { key: 'health', label: 'Health alerts' }].map(f => (
            <button key={f.key} onClick={() => setSourceFilter(f.key)}
              className="px-3 py-1.5 rounded-md text-xs font-semibold transition-colors"
              style={{ background: sourceFilter === f.key ? c.textLink : 'transparent', color: sourceFilter === f.key ? '#fff' : c.textMuted }}>
              {f.label}
            </button>
          ))}
        </div>
        <select value={routerFilter} onChange={e => setRouterFilter(Number(e.target.value))} className="input text-sm py-1.5 w-auto">
          <option value={0}>Todos los routers</option>
          {routers.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <div className="flex-1 flex items-center gap-2">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: c.textMuted }} />
            <input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()}
              placeholder="Buscar en mensajes..." className="input pl-9 text-sm w-full" />
          </div>
          <button onClick={load} className="btn-secondary text-sm px-3">Buscar</button>
        </div>
        {severityFilter !== 'all' && (
          <button onClick={() => setSeverityFilter('all')} className="text-xs font-semibold" style={{ color: c.textLink }}>Limpiar filtro</button>
        )}
      </div>

      <div className="space-y-1.5">
        {loading && events.length === 0 && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-5 h-5 animate-spin mr-2" style={{ color: c.accent }} />
            <span style={{ color: c.textMuted }}>Cargando eventos...</span>
          </div>
        )}
        {!loading && events.length === 0 && (
          <div className="text-center py-12">
            <CheckCircle className="w-12 h-12 mx-auto mb-3" style={{ color: c.green }} />
            <p className="text-lg font-semibold" style={{ color: c.textPrimary }}>Sin eventos</p>
            <p className="text-sm" style={{ color: c.textMuted }}>No se encontraron eventos con los filtros actuales</p>
          </div>
        )}
        {events.map(ev => {
          const s = sevMap[ev.severity] || sevMap.info;
          const Icon = s.icon;
          const isExp = expandedId === ev.id;
          const isHealth = ev.source === 'health';
          return (
            <div key={ev.id} className="rounded-lg transition-all"
              style={{ background: isHealth && ev.is_resolved ? c.bgCard : s.bg, border: `1px solid ${isHealth && ev.is_resolved ? c.border : s.color + '40'}` }}>
              <div className="flex items-center gap-3 px-4 py-2.5 cursor-pointer" onClick={() => setExpandedId(isExp ? null : ev.id)}>
                <Icon className="w-4 h-4 shrink-0" style={{ color: s.color }} />
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] w-16 font-mono" style={{ color: c.textMuted }}>{formatTime(ev.created_at)}</span>
                  <Server className="w-3 h-3" style={{ color: c.textMuted }} />
                  <span className="text-xs font-medium truncate max-w-[100px]" style={{ color: c.textSecondary }}>
                    {ev.router_name || (ev.router_id ? `Router #${ev.router_id}` : 'Sistema')}
                  </span>
                </div>
                <div className="flex-1 min-w-0 flex items-center gap-1.5">
                  {ev.topics.split(',').filter(Boolean).map((t, i) => <TopicBadge key={i} topic={t} c={c} />)}
                  <span className="text-sm truncate ml-1" style={{ color: c.textPrimary }}>{ev.message}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {isHealth && ev.is_resolved && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold" style={{ background: c.greenBg, color: c.green }}>Resuelta</span>
                  )}
                  <ChevronDown className="w-3.5 h-3.5 transition-transform" style={{ color: c.textMuted, transform: isExp ? 'rotate(180deg)' : 'none' }} />
                </div>
              </div>
              {isExp && (
                <div className="px-4 pb-3 pt-2.5" style={{ borderTop: `1px solid ${c.borderLight}` }}>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Recibido</span><span style={{ color: c.textSecondary }}>{formatDateTime(ev.created_at)}</span></div>
                    {!isHealth && ev.time && <div><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Hora RouterOS</span><span style={{ color: c.textSecondary }}>{ev.time}</span></div>}
                    <div><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Severidad</span><span style={{ color: s.color }}>{s.label}</span></div>
                    <div><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Topics</span><div className="flex flex-wrap gap-1">{ev.topics.split(',').filter(Boolean).map((t, i) => <TopicBadge key={i} topic={t} c={c} />)}</div></div>
                    <div><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Fuente</span><span style={{ color: c.textSecondary }}>{isHealth ? 'Health Checker' : 'Router Log'}</span></div>
                    {isHealth && ev.resolved_by && <div><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Resuelto por</span><span style={{ color: c.textSecondary }}>{ev.resolved_by}</span></div>}
                    {isHealth && ev.resolved_at && <div><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Resuelto el</span><span style={{ color: c.textSecondary }}>{formatDateTime(ev.resolved_at)}</span></div>}
                    {isHealth && ev.resolution_comment && (
                      <div className="col-span-2"><span className="block mb-0.5 font-medium" style={{ color: c.textMuted }}>Comentario</span><span style={{ color: c.textSecondary }}>{ev.resolution_comment}</span></div>
                    )}
                  </div>
                  {isHealth && !ev.is_resolved && (
                    <div className="mt-3">
                      <button onClick={() => handleResolveClick(ev)} className="btn-secondary text-xs">
                        <CheckCircle className="w-3 h-3 inline mr-1" />Resolver alerta
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <ResolveModal visible={resolveModal.visible} onClose={() => setResolveModal({ visible: false, eventId: '', title: '' })} onConfirm={handleResolveConfirm} title={resolveModal.title} c={c} />
    </div>
  );
}

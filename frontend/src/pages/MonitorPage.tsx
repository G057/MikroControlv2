import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { monitorAPI } from '../services/api';
import type { MonitorRouter } from '../types';
import type { MonitorNotification } from '../services/api';
import {
  Radio,
  LayoutDashboard,
  Server,
  Bell,
  Settings,
  Search,
  X,
  Grid3X3,
  List,
  Sun,
  Moon,
  LogOut,
  Wifi,
  WifiOff,
  AlertTriangle,
  Monitor,
  ChevronDown,
  Filter,
  Volume2,
  VolumeX,
} from 'lucide-react';

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return 'Ahora';
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Ahora';
  if (mins < 60) return `Hace ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `Hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `Hace ${days}d`;
}

const SIDEBAR_ITEMS = [
  { icon: LayoutDashboard, path: '/', label: 'Dashboard' },
  { icon: Server, path: '/routers', label: 'Routers' },
  { icon: Radio, path: '/monitor', label: 'Monitor', current: true },
  { icon: Bell, path: '/events', label: 'Alertas' },
  { icon: Settings, path: '/settings', label: 'Configuración' },
];

export default function MonitorPage() {
  const { c, isDark, toggle: toggleTheme } = useTheme();
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const [routers, setRouters] = useState<MonitorRouter[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'online' | 'warning' | 'offline'>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [filterOpen, setFilterOpen] = useState(false);
  const [alertPopups, setAlertPopups] = useState<MonitorNotification[]>([]);
  const [muted, setMuted] = useState(() => localStorage.getItem('monitor_mute') === 'true');
  const [popupsPaused, setPopupsPaused] = useState(false);
  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const sinceEventLogRef = useRef<number>(0);
  const initializedRef = useRef(false);
  const notificationCursorRef = useRef(0);
  const receivedNotificationIds = useRef(new Set<number>());
  const playedNotificationIds = useRef(new Set<number>());

  const audioCtxRef = useRef<AudioContext | null>(null);
  const warmedRef = useRef(false);

  // Warm up AudioContext on first user click
  useEffect(() => {
    const warm = () => {
      if (!warmedRef.current) {
        try {
          const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
          audioCtxRef.current = ctx;
          if (ctx.state === 'suspended') ctx.resume();
          warmedRef.current = true;
        } catch {}
      }
      document.removeEventListener('click', warm);
    };
    document.addEventListener('click', warm);
    return () => document.removeEventListener('click', warm);
  }, []);

  const playAlertSound = useCallback(async () => {
    try {
      let ctx = audioCtxRef.current;
      if (!ctx) {
        ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioCtxRef.current = ctx;
      }
      if (ctx.state === 'suspended') await ctx.resume();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.5, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.3);
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(660, ctx.currentTime + 0.15);
      gain2.gain.setValueAtTime(0.4, ctx.currentTime + 0.15);
      gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
      osc2.start(ctx.currentTime + 0.15);
      osc2.stop(ctx.currentTime + 0.5);
    } catch (error) { console.warn('Notification audio failed', error); }
  }, []);

  const fetchData = useCallback(async () => {
    const isFirst = !initializedRef.current;
    initializedRef.current = true;
    try {
      const resp = await monitorAPI.list();
      setRouters(resp.routers);
      let hasMore = true;
      while (hasMore) {
        const batch = await monitorAPI.notifications(notificationCursorRef.current);
        hasMore = batch.hasMore;
        notificationCursorRef.current = batch.nextCursor;
        const fresh = batch.items.filter(item => !receivedNotificationIds.current.has(item.id));
        fresh.forEach(item => receivedNotificationIds.current.add(item.id));
        const displayable = isFirst ? fresh.filter(item => item.severity === 'critical') : fresh;
        if (!popupsPaused && displayable.length) {
          setAlertPopups(prev => {
            const critical = [...prev.filter(item => item.severity === 'critical'), ...fresh.filter(item => item.popupRequired && item.severity === 'critical')];
            const other = [...prev.filter(item => item.severity !== 'critical'), ...displayable.filter(item => item.popupRequired && item.severity !== 'critical')].slice(-50);
            return [...critical, ...other];
          });
          for (const item of displayable) {
            if (item.soundRequired && !mutedRef.current && !playedNotificationIds.current.has(item.id)) {
              playedNotificationIds.current.add(item.id);
              void playAlertSound();
            }
          }
        }
      }
    } catch (error) { console.warn('Monitor polling failed', error); }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 30000);
    return () => clearInterval(iv);
  }, [fetchData]);

  const filteredRouters = useMemo(() => {
    return routers.filter(r => {
      if (statusFilter === 'online' && !r.is_online) return false;
      if (statusFilter === 'warning' && !(r.is_online && r.alert_count > 0)) return false;
      if (statusFilter === 'offline' && r.is_online) return false;
      if (search) {
        const q = search.toLowerCase();
        const nameMatch = r.name.toLowerCase().includes(q);
        const clientMatch = (r.client_name || '').toLowerCase().includes(q);
        const cityMatch = (r.city || '').toLowerCase().includes(q);
        if (!nameMatch && !clientMatch && !cityMatch) return false;
      }
      return true;
    });
  }, [routers, search, statusFilter]);

  const summary = useMemo(() => ({
    total: routers.length,
    online: routers.filter(r => r.is_online).length,
    warnings: routers.filter(r => r.is_online && r.alert_count > 0).length,
    offline: routers.filter(r => !r.is_online).length,
    activeAlerts: routers.reduce((s, r) => s + r.alert_count, 0),
  }), [routers]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="h-screen flex overflow-hidden" style={{ background: c.bgPage, color: c.textPrimary }}>
      {/* Thin sidebar */}
      <aside
        className="flex flex-col items-center py-4 gap-1 flex-shrink-0 z-10"
        style={{ width: 72, background: c.bgSidebar, borderRight: `1px solid ${c.border}` }}
      >
        <div className="mb-4 p-2 rounded-xl" style={{ background: c.accent }}>
          <Radio className="w-6 h-6 text-white" />
        </div>
        {SIDEBAR_ITEMS.map(item => {
          const isCurrent = item.path === '/monitor';
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              title={item.label}
              className="flex items-center justify-center w-12 h-12 rounded-xl transition-all duration-150"
              style={{
                background: isCurrent ? c.bgActive : 'transparent',
                color: isCurrent ? c.accent : c.textMuted,
              }}
              onMouseEnter={e => { if (!isCurrent) (e.currentTarget as HTMLElement).style.background = c.bgHover; }}
              onMouseLeave={e => { if (!isCurrent) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
            >
              <item.icon className="w-5 h-5" />
            </button>
          );
        })}
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header
          className="flex items-center justify-between flex-shrink-0 px-6 gap-4"
          style={{ height: 64, background: c.bgSidebar, borderBottom: `1px solid ${c.border}` }}
        >
          <h1 className="text-lg font-semibold" style={{ color: c.textPrimary }}>
            <Monitor className="w-5 h-5 inline-block mr-2" style={{ color: c.accent }} />
            Monitoreo de Routers
          </h1>

          <div className="flex items-center gap-3">
            <div className="relative" style={{ width: 240 }}>
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: c.textMuted }} />
              <input
                type="text"
                placeholder="Buscar router, cliente..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-lg text-sm outline-none transition-all duration-150"
                style={{
                  background: c.bgInput,
                  color: c.textPrimary,
                  border: `1px solid ${c.border}`,
                }}
                onFocus={e => { e.currentTarget.style.borderColor = c.borderFocus; }}
                onBlur={e => { e.currentTarget.style.borderColor = c.border; }}
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2">
                  <X className="w-4 h-4" style={{ color: c.textMuted }} />
                </button>
              )}
            </div>

            <div className="relative">
              <button
                onClick={() => setFilterOpen(!filterOpen)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors"
                style={{ background: c.bgHover, color: c.textSecondary, border: `1px solid ${c.border}` }}
              >
                <Filter className="w-4 h-4" />
                Filtros
                <ChevronDown className="w-3 h-3" />
              </button>
              {filterOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setFilterOpen(false)} />
                  <div
                    className="absolute right-0 top-full mt-1 z-20 w-44 rounded-xl p-2 shadow-lg"
                    style={{ background: c.bgCard, border: `1px solid ${c.border}` }}
                  >
                    {(['all', 'online', 'warning', 'offline'] as const).map(s => (
                      <button
                        key={s}
                        onClick={() => { setStatusFilter(s); setFilterOpen(false); }}
                        className="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors"
                        style={{
                          background: statusFilter === s ? c.bgActive : 'transparent',
                          color: statusFilter === s ? c.accent : c.textPrimary,
                        }}
                      >
                        {s === 'all' ? 'Todos' : s === 'online' ? 'Online' : s === 'warning' ? 'Advertencia' : 'Offline'}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="flex rounded-lg overflow-hidden" style={{ border: `1px solid ${c.border}` }}>
              <button
                onClick={() => setViewMode('grid')}
                className="p-2 transition-colors"
                style={{ background: viewMode === 'grid' ? c.bgActive : 'transparent', color: viewMode === 'grid' ? c.accent : c.textMuted }}
              >
                <Grid3X3 className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className="p-2 transition-colors"
                style={{ background: viewMode === 'list' ? c.bgActive : 'transparent', color: viewMode === 'list' ? c.accent : c.textMuted }}
              >
                <List className="w-4 h-4" />
              </button>
            </div>

            {hasPermission('monitor:mute') && (
              <button onClick={() => { setMuted(!muted); localStorage.setItem('monitor_mute', String(!muted)); }} className="p-2 rounded-lg transition-colors" style={{ color: muted ? c.textMuted : c.accent }} title={muted ? 'Silencio activado' : 'Silenciar sonido'}>
                {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
              </button>
            )}
            <button onClick={() => setPopupsPaused(!popupsPaused)} className="px-2 py-1 rounded-lg text-xs" style={{ color: popupsPaused ? c.textMuted : c.accent, border: `1px solid ${c.border}` }} title="Pausar o reanudar popups">
              {popupsPaused ? 'Reanudar' : 'Pausar'}
            </button>
            <button onClick={toggleTheme} className="p-2 rounded-lg transition-colors" style={{ color: c.textMuted }} title={isDark ? 'Modo día' : 'Modo noche'}>
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            <div className="flex items-center gap-2 pl-3" style={{ borderLeft: `1px solid ${c.border}` }}>
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: c.accent, color: '#fff' }}>
                {(user?.full_name || user?.username || '?').charAt(0).toUpperCase()}
              </div>
              <span className="text-sm font-medium max-w-[120px] truncate" style={{ color: c.textPrimary }}>
                {user?.full_name || user?.username}
              </span>
              <button onClick={handleLogout} className="p-1.5 rounded-lg transition-colors" style={{ color: c.textMuted }} title="Cerrar sesión">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Summary cards */}
        <div className="flex-shrink-0 px-6 pt-4 pb-2">
          <div className="grid grid-cols-5 gap-4">
            {[
              { label: 'Total', value: summary.total, color: c.textPrimary },
              { label: 'Online', value: summary.online, color: c.green },
              { label: 'Advertencias', value: summary.warnings, color: c.yellow },
              { label: 'Offline', value: summary.offline, color: c.red },
              { label: 'Alertas', value: summary.activeAlerts, color: c.orange },
            ].map(s => (
              <div
                key={s.label}
                className="rounded-xl px-4 py-3 flex flex-col transition-shadow duration-150"
                style={{
                  background: c.bgCard,
                  boxShadow: c.shadow,
                  border: `1px solid ${c.borderLight}`,
                }}
              >
                <span className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</span>
                <span className="text-xs font-medium mt-0.5" style={{ color: c.textMuted }}>{s.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Main grid / list */}
        <div className="flex-1 px-6 pb-6 pt-3 overflow-y-auto">
          {filteredRouters.length === 0 ? (
            <div className="flex items-center justify-center h-full text-sm" style={{ color: c.textMuted }}>
              {routers.length === 0 ? 'Cargando routers...' : 'No se encontraron routers con los filtros actuales'}
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid gap-3" style={{
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            }}>
              {filteredRouters.map(r => {
                const isOffline = !r.is_online;
                const hasAlerts = r.alert_count > 0;
                const isSelected = selectedIds.has(r.id);
                const statusColor = isOffline ? c.red : hasAlerts ? c.yellow : c.green;
                const statusBg = isOffline ? c.redBg : hasAlerts ? c.yellowBg : c.greenBg;
                return (
                  <div
                    key={r.id}
                    onClick={() => toggleSelect(r.id)}
                    className="rounded-xl p-4 flex flex-col gap-2 cursor-pointer transition-all duration-150 select-none"
                    style={{
                      background: isSelected ? c.bgActive : c.bgCard,
                      border: `1px solid ${isSelected ? c.accent : c.borderLight}`,
                      boxShadow: isSelected ? `0 0 0 1px ${c.accent}` : c.shadow,
                    }}
                    onMouseEnter={e => {
                      if (!isSelected) {
                        (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)';
                        (e.currentTarget as HTMLElement).style.borderColor = c.border;
                      }
                    }}
                    onMouseLeave={e => {
                      if (!isSelected) {
                        (e.currentTarget as HTMLElement).style.boxShadow = c.shadow;
                        (e.currentTarget as HTMLElement).style.borderColor = c.borderLight;
                      }
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: statusBg }}>
                        {isOffline ? (
                          <WifiOff className="w-4 h-4" style={{ color: c.red }} />
                        ) : hasAlerts ? (
                          <AlertTriangle className="w-4 h-4" style={{ color: c.yellow }} />
                        ) : (
                          <Wifi className="w-4 h-4" style={{ color: c.green }} />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold truncate" style={{ color: c.textPrimary }}>{r.name}</div>
                        {r.client_name && (
                          <div className="text-xs truncate" style={{ color: c.textMuted }}>{r.client_name}</div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs" style={{ color: c.textMuted }}>
                      <span>{timeAgo(r.last_seen)}</span>
                      {hasAlerts && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: statusBg, color: statusColor }}>
                          {r.alert_count} {r.alert_count === 1 ? 'alerta' : 'alertas'}
                        </span>
                      )}
                      {!hasAlerts && isOffline && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: c.redBg, color: c.red }}>
                          Sin conexión
                        </span>
                      )}
                      {!hasAlerts && !isOffline && (
                        <span style={{ color: c.green }}>Sin alertas</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col gap-1" style={{ border: `1px solid ${c.borderLight}`, borderRadius: 12, overflow: 'hidden' }}>
              {filteredRouters.map(r => {
                const isOffline = !r.is_online;
                const hasAlerts = r.alert_count > 0;
                const isSelected = selectedIds.has(r.id);
                const statusColor = isOffline ? c.red : hasAlerts ? c.yellow : c.green;
                return (
                  <div
                    key={r.id}
                    onClick={() => toggleSelect(r.id)}
                    className="flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors duration-150"
                    style={{
                      background: isSelected ? c.bgActive : 'transparent',
                      borderBottom: `1px solid ${c.borderLight}`,
                    }}
                  >
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: statusColor }} />
                    <span className="text-sm font-medium flex-1 min-w-0 truncate" style={{ color: c.textPrimary }}>{r.name}</span>
                    {r.client_name && (
                      <span className="text-xs flex-shrink-0" style={{ color: c.textMuted }}>{r.client_name}</span>
                    )}
                    <span className="text-xs flex-shrink-0" style={{ color: c.textMuted }}>{timeAgo(r.last_seen)}</span>
                    {hasAlerts && (
                      <span className="text-xs font-medium flex-shrink-0 px-2 py-0.5 rounded-full" style={{ background: c.yellowBg, color: c.yellow }}>
                        {r.alert_count} alertas
                      </span>
                    )}
                    {isOffline && !hasAlerts && (
                      <span className="text-xs font-medium flex-shrink-0" style={{ color: c.red }}>Sin conexión</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {!popupsPaused && alertPopups.length > 0 && (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-h-[80vh] overflow-y-auto" style={{ maxWidth: 384, scrollbarWidth: 'thin' }}>
          {alertPopups.map(p => (
            <div key={p.id} className="w-96 rounded-xl p-4 shadow-2xl animate-slide-down flex-shrink-0" style={{ background: c.bgCard, border: `1px solid ${p.severity === 'critical' ? c.red : c.yellow}` }}>
              <div className="flex items-center justify-between mb-1">
                <h3 className="font-semibold truncate" style={{ color: c.textPrimary }}>
                  {p.severity === 'critical' ? 'Critica: ' : 'Advertencia: '}{p.title}
                </h3>
                <button onClick={() => { setAlertPopups(prev => prev.filter(x => x.id !== p.id)); void monitorAPI.acknowledge(p.id); }} className="p-1 rounded-lg hover:opacity-70 transition-opacity flex-shrink-0" style={{ color: c.textMuted }}>
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-[11px] mb-1 font-mono" style={{ color: c.textMuted }}>{p.createdAt ? new Date(p.createdAt).toLocaleString() : ''}</p>
              <p className="text-sm" style={{ color: c.textSecondary }}>
                {p.message}{p.occurrenceCount > 1 ? ` (${p.occurrenceCount} ocurrencias)` : ''}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

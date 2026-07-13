import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI, dashboardPrefAPI } from '../services/api';
import type { DashboardData, DashboardCharts } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import {
  Wifi, WifiOff, Cpu, Package, Activity, ArrowRight, Thermometer, HardDrive,
  AlertCircle, Zap, Settings, Check, X, MessageCircle, Terminal,
} from 'lucide-react';
import { formatTime } from '../utils/date';
import toast from 'react-hot-toast';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, Legend,
} from 'recharts';

const COLORS = ['#EF4444', '#F59E0B', '#3B82F6', '#10B981', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316', '#6366F1', '#14B8A6'];

const ALL_WIDGETS = [
  { id: 'routers_online', label: 'Routers Online', icon: Wifi, category: 'Stat' },
  { id: 'routers_offline', label: 'Routers Offline', icon: WifiOff, category: 'Stat' },
  { id: 'cpu_avg', label: 'CPU Promedio', icon: Cpu, category: 'Stat' },
  { id: 'temp_avg', label: 'Temperatura Promedio', icon: Thermometer, category: 'Stat' },
  { id: 'disk_free', label: 'Disco Libre', icon: HardDrive, category: 'Stat' },
  { id: 'alerts_active', label: 'Alertas Activas', icon: AlertCircle, category: 'Stat' },
  { id: 'events_today', label: 'Eventos Hoy', icon: MessageCircle, category: 'Stat' },
  { id: 'commands_today', label: 'Comandos Hoy', icon: Terminal, category: 'Stat' },
  { id: 'wireguard_tunnels', label: 'WireGuard Tunnels', icon: Zap, category: 'Stat' },
  { id: 'inventory', label: 'Inventario', icon: Package, category: 'Stat' },
  { id: 'chart_severity_hour', label: 'Severidad por Hora', icon: Activity, category: 'Gráfico' },
  { id: 'chart_events_router', label: 'Eventos por Router', icon: Activity, category: 'Gráfico' },
  { id: 'chart_topics', label: 'Top Topics', icon: Activity, category: 'Gráfico' },
  { id: 'chart_router_status', label: 'Estado de Routers', icon: Activity, category: 'Gráfico' },
  { id: 'chart_hardware', label: 'Distribución de Hardware', icon: Activity, category: 'Gráfico' },
  { id: 'recent_activity', label: 'Actividad Reciente', icon: ArrowRight, category: 'Panel' },
];

function CustomizeModal({ visible, onClose, enabled, onSave, c }: {
  visible: boolean; onClose: () => void; enabled: string[]; onSave: (w: string[]) => void; c: any;
}) {
  const [selected, setSelected] = useState<string[]>(enabled);
  useEffect(() => { setSelected(enabled); }, [enabled]);
  if (!visible) return null;

  const toggle = (id: string) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const stats = ALL_WIDGETS.filter(w => w.category === 'Stat');
  const charts = ALL_WIDGETS.filter(w => w.category === 'Gráfico');
  const panels = ALL_WIDGETS.filter(w => w.category === 'Panel');

  const Section = ({ title, items }: { title: string; items: typeof ALL_WIDGETS }) => (
    <div className="mb-4">
      <p className="text-[10px] uppercase font-bold mb-2" style={{ color: c.textMuted }}>{title}</p>
      <div className="grid grid-cols-2 gap-2">
        {items.map(w => {
          const active = selected.includes(w.id);
          return (
            <button key={w.id} onClick={() => toggle(w.id)}
              className="flex items-center gap-2 p-2 rounded-lg text-left text-sm transition-all"
              style={{ background: active ? `${c.accent}15` : c.bgHover, border: `1px solid ${active ? c.accent : 'transparent'}`, color: active ? c.textPrimary : c.textSecondary }}>
              <div className="w-5 h-5 rounded flex items-center justify-center shrink-0"
                style={{ background: active ? c.accent : c.border }}>
                {active ? <Check className="w-3 h-3 text-white" /> : <X className="w-3 h-3" style={{ color: c.textMuted }} />}
              </div>
              <w.icon className="w-4 h-4 shrink-0" style={{ color: active ? c.accent : c.textMuted }} />
              <span className="truncate">{w.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
      <div className="card w-full max-w-lg max-h-[80vh] overflow-y-auto m-4" style={{ background: c.bgCard }}>
        <div className="flex items-center justify-between p-4" style={{ borderBottom: `1px solid ${c.border}` }}>
          <h2 className="text-lg font-bold" style={{ color: c.textPrimary }}>Personalizar Dashboard</h2>
          <button onClick={onClose} style={{ color: c.textMuted }}><X className="w-5 h-5" /></button>
        </div>
        <div className="p-4">
          <Section title="Estadísticas" items={stats} />
          <Section title="Gráficos" items={charts} />
          <Section title="Paneles" items={panels} />
        </div>
        <div className="flex gap-2 p-4" style={{ borderTop: `1px solid ${c.border}` }}>
          <button onClick={() => { onSave(selected); onClose(); }} className="btn-primary text-sm flex-1">
            <Check className="w-4 h-4 inline mr-1" />Guardar
          </button>
          <button onClick={onClose} className="btn-secondary text-sm">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [charts, setCharts] = useState<DashboardCharts | null>(null);
  const [widgets, setWidgets] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCustomize, setShowCustomize] = useState(false);
  const { c } = useTheme();
  const navigate = useNavigate();

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    Promise.all([dashboardAPI.get(), dashboardAPI.charts(), dashboardPrefAPI.get()])
      .then(([d, ch, p]) => { setData(d); setCharts(ch); setWidgets(p.widgets); })
      .catch(console.error).finally(() => { if (!silent) setLoading(false); });
  }, []);

  useEffect(() => { load(); const iv = setInterval(() => load(true), 15000); return () => clearInterval(iv); }, [load]);

  const handleSaveWidgets = async (w: string[]) => {
    try { await dashboardPrefAPI.update(w); setWidgets(w); toast.success('Dashboard actualizado'); }
    catch { toast.error('Error al guardar'); }
  };

  const isWidget = (id: string) => widgets.includes(id);

  if (loading && !data) return <div style={{ color: c.textMuted }}>Cargando dashboard...</div>;
  if (!data) return <div style={{ color: c.textMuted }}>Error al cargar dashboard</div>;

  const statWidgets = [
    isWidget('routers_online') && { id: 'routers_online', label: 'Routers Online', value: data.routers.online, icon: Wifi, color: c.green, bg: c.greenBg },
    isWidget('routers_offline') && { id: 'routers_offline', label: 'Routers Offline', value: data.routers.offline, icon: WifiOff, color: c.red, bg: c.redBg },
    isWidget('cpu_avg') && { id: 'cpu_avg', label: 'CPU Promedio', value: `${data.metrics.avg_cpu}%`, icon: Cpu, color: data.metrics.avg_cpu > 80 ? c.red : c.accent, bg: data.metrics.avg_cpu > 80 ? c.redBg : c.accentLight },
    isWidget('temp_avg') && { id: 'temp_avg', label: 'Temp Promedio', value: data.metrics.avg_temp > 0 ? `${data.metrics.avg_temp}°C` : '--', icon: Thermometer, color: data.metrics.avg_temp > 70 ? c.red : data.metrics.avg_temp > 50 ? c.yellow : c.green, bg: data.metrics.avg_temp > 70 ? c.redBg : c.yellowBg },
    isWidget('disk_free') && { id: 'disk_free', label: 'Disco Libre', value: data.metrics.avg_hdd_free > 0 ? `${data.metrics.avg_hdd_free}MB` : '--', icon: HardDrive, color: c.purple, bg: c.purpleBg },
    isWidget('alerts_active') && { id: 'alerts_active', label: 'Alertas Activas', value: data.alerts.active, icon: AlertCircle, color: data.alerts.critical > 0 ? c.red : c.yellow, bg: data.alerts.critical > 0 ? c.redBg : c.yellowBg },
    isWidget('events_today') && { id: 'events_today', label: 'Eventos Hoy', value: data.today?.events ?? 0, icon: MessageCircle, color: c.blue, bg: c.blueBg },
    isWidget('commands_today') && { id: 'commands_today', label: 'Comandos Hoy', value: data.today?.commands ?? 0, icon: Terminal, color: c.accent, bg: c.accentLight },
    isWidget('wireguard_tunnels') && { id: 'wireguard_tunnels', label: 'WireGuard Tunnels', value: data.wireguard?.tunnels ?? 0, icon: Zap, color: c.green, bg: c.greenBg },
    isWidget('inventory') && { id: 'inventory', label: 'Inventario', value: data.inventory.total, icon: Package, color: c.purple, bg: c.purpleBg },
  ].filter(Boolean) as { id: string; label: string; value: string | number; icon: any; color: string; bg: string }[];

  const ttStyle = { background: c.chartTooltipBg, border: `1px solid ${c.chartTooltipBorder}`, borderRadius: 8, color: c.chartTooltipText, fontSize: 12 };
  const gridStroke = c.chartGrid;
  const axisTick = { fontSize: 10, fill: c.chartText };

  const statusPie = charts ? [
    { name: 'Online', value: charts.router_status.online, color: c.green },
    { name: 'Offline', value: charts.router_status.offline, color: c.red },
  ] : [] as { name: string; value: number; color: string }[];

  const hwPie = charts ? charts.hardware_distribution.map((h: { model: string; count: number }, i: number) => ({
    name: h.model, value: h.count, color: COLORS[i % COLORS.length],
  })) : [];

  const eventsByRouterData = charts ? charts.events_by_router.map(e => ({
    name: e.router_name.length > 20 ? e.router_name.slice(0, 18) + '...' : e.router_name, count: e.count,
  })) : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Dashboard NOC</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowCustomize(true)} className="btn-secondary text-sm">
            <Settings className="w-4 h-4 inline mr-1" />Personalizar
          </button>
          <button onClick={() => load()} className="btn-secondary text-sm">
            <Activity className="w-4 h-4 inline mr-1" />Actualizar
          </button>
        </div>
      </div>

      {statWidgets.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {statWidgets.map(s => (
            <div key={s.id} className="card flex items-center gap-3 !p-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: s.bg }}>
                <s.icon className="w-5 h-5" style={{ color: s.color }} />
              </div>
              <div className="min-w-0">
                <p className="text-xl font-bold" style={{ color: c.textPrimary }}>{s.value}</p>
                <p className="text-[11px] truncate" style={{ color: c.textMuted }}>{s.label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {(isWidget('chart_severity_hour') || isWidget('chart_events_router')) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {isWidget('chart_severity_hour') && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Severidad por Hora (últimas 24h)</h2>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={charts?.severity_by_hour || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="hour" tick={axisTick} interval={3} />
                  <YAxis tick={axisTick} />
                  <Tooltip contentStyle={ttStyle} />
                  <Legend wrapperStyle={{ fontSize: 11, color: c.textSecondary }} />
                  <Area type="monotone" dataKey="critical" stackId="1" stroke={c.red} fill={c.red} fillOpacity={0.7} name="Críticos" />
                  <Area type="monotone" dataKey="warning" stackId="1" stroke={c.yellow} fill={c.yellow} fillOpacity={0.7} name="Advertencias" />
                  <Area type="monotone" dataKey="info" stackId="1" stroke={c.blue} fill={c.blue} fillOpacity={0.4} name="Info" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
          {isWidget('chart_events_router') && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Eventos por Router</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={eventsByRouterData} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} horizontal={false} />
                  <XAxis type="number" tick={axisTick} />
                  <YAxis type="category" dataKey="name" tick={axisTick} width={120} />
                  <Tooltip contentStyle={ttStyle} />
                  <Bar dataKey="count" fill={c.accent} radius={[0, 4, 4, 0]} maxBarSize={20} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {(isWidget('chart_topics') || isWidget('chart_router_status')) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {isWidget('chart_topics') && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Top Topics</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={charts?.top_topics || []} margin={{ left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                  <XAxis dataKey="topic" tick={axisTick} />
                  <YAxis tick={axisTick} />
                  <Tooltip contentStyle={ttStyle} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={28}>
                    {(charts?.top_topics || []).map((_: { topic: string; count: number }, i: number) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {isWidget('chart_router_status') && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Estado de Routers</h2>
              <div className="flex items-center justify-center gap-6">
                <ResponsiveContainer width="50%" height={180}>
                  <PieChart>
                    <Pie data={statusPie} cx="50%" cy="50%" innerRadius={40} outerRadius={65} dataKey="value" strokeWidth={0}>
                      {statusPie.map((e: { name: string; value: number; color: string }, i: number) => <Cell key={i} fill={e.color} />)}
                    </Pie>
                    <Tooltip contentStyle={ttStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-3">
                  {statusPie.map(s => (
                    <div key={s.name} className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full shrink-0" style={{ background: s.color }} />
                      <span className="text-sm" style={{ color: c.textSecondary }}>{s.name}</span>
                      <span className="text-sm font-bold" style={{ color: c.textPrimary }}>{s.value}</span>
                    </div>
                  ))}
                  <div className="pt-1">
                    <span className="text-xs" style={{ color: c.textMuted }}>
                      {data.routers.total > 0 ? Math.round((data.routers.online / data.routers.total) * 100) : 0}% uptime
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {(isWidget('chart_hardware') || isWidget('recent_activity')) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {isWidget('chart_hardware') && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Distribución de Hardware</h2>
              {hwPie.length > 0 ? (
                <div className="flex items-center justify-center gap-6">
                  <ResponsiveContainer width="50%" height={180}>
                    <PieChart>
                      <Pie data={hwPie} cx="50%" cy="50%" innerRadius={35} outerRadius={65} dataKey="value" strokeWidth={0}>
                        {hwPie.map((e: { name: string; value: number; color: string }, i: number) => <Cell key={i} fill={e.color} />)}
                      </Pie>
                      <Tooltip contentStyle={ttStyle} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-2">
                    {hwPie.map(h => (
                      <div key={h.name} className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full shrink-0" style={{ background: h.color }} />
                        <span className="text-sm" style={{ color: c.textSecondary }}>{h.name}</span>
                        <span className="text-sm font-bold" style={{ color: c.textPrimary }}>{h.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-center py-8" style={{ color: c.textMuted }}>Sin datos de hardware</p>
              )}
            </div>
          )}
          {isWidget('recent_activity') && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold" style={{ color: c.textPrimary }}>Actividad Reciente</h2>
                <button onClick={() => navigate('/events')} className="text-xs font-semibold flex items-center gap-1" style={{ color: c.textLink }}>
                  Ver todos <ArrowRight className="w-3 h-3" />
                </button>
              </div>
              <div className="space-y-2.5">
                {data.recent_activity.length === 0 && <p className="text-sm" style={{ color: c.textMuted }}>Sin actividad reciente</p>}
                {data.recent_activity.slice(0, 8).map(log => (
                  <div key={log.id} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="font-semibold" style={{ color: c.textLink }}>{log.username}</span>
                      <span className="mx-2" style={{ color: c.textMuted }}>{log.action}</span>
                      <span style={{ color: c.textSecondary }}>{log.resource_name || log.resource_type}</span>
                    </div>
                    <span className="text-xs" style={{ color: c.textMuted }}>{log.timestamp ? formatTime(log.timestamp) : ''}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <CustomizeModal visible={showCustomize} onClose={() => setShowCustomize(false)} enabled={widgets} onSave={handleSaveWidgets} c={c} />
    </div>
  );
}

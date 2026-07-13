import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { routersAPI, routerosAPI, trafficAPI } from '../services/api';
import type { TrafficSample } from '../services/api';
import type { RouterDevice } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { formatTime, formatDateTime, getTimezone } from '../utils/date';
import ErrorBoundary from '../components/ErrorBoundary';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import {
  ArrowLeft, Wifi, WifiOff, Cpu, MemoryStick, HardDrive, Thermometer,
  Clock, Terminal, RefreshCw, Network, Shield, Users, Server, Plus,
  Search, Settings, Lock, Globe, Cable, Radio, Link2, Edit3, Trash2,
  CheckCircle2, XCircle, AlertTriangle, ArrowUpDown, Power, PowerOff, Zap, Activity, List
} from 'lucide-react';
import toast from 'react-hot-toast';

type Tab = 'overview' | 'interfaces' | 'traffic' | 'arp' | 'dhcp' | 'pppoe' | 'firewall' | 'wireguard' | 'config' | 'ping';

function formatBps(v: number): string {
  if (v < 1000) return `${v.toFixed(0)} bps`;
  if (v < 1e6) return `${(v / 1e3).toFixed(1)} Kbps`;
  if (v < 1e9) return `${(v / 1e6).toFixed(2)} Mbps`;
  return `${(v / 1e9).toFixed(2)} Gbps`;
}

function formatBytes(val: string | number | null | undefined): string {
  if (val === null || val === undefined || val === '') return '0 B';
  const bytes = typeof val === 'string' ? parseInt(val, 10) : val;
  if (isNaN(bytes)) return String(val);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1073741824).toFixed(2)} GB`;
}

function StatusBadge({ active, label, c }: { active: boolean; label?: string; c: any }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: active ? c.greenBg : c.redBg, color: active ? c.green : c.red }}>
      {active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {label || (active ? 'Activo' : 'Inactivo')}
    </span>
  );
}

function SectionHeader({ icon: Icon, title, count, c }: { icon: any; title: string; count?: number; c: any }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon className="w-5 h-5" style={{ color: c.textLink }} />
      <h3 className="text-lg font-semibold" style={{ color: c.textPrimary }}>{title}</h3>
      {count !== undefined && <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: c.bgHover, color: c.textMuted }}>{count}</span>}
    </div>
  );
}

function DataTable({ columns, data, emptyMessage, c }: { columns: { key: string; label: string; render?: (val: any, row: any) => React.ReactNode; className?: string }[]; data: any[]; emptyMessage?: string; c: any }) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [filter, setFilter] = useState('');

  const handleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  const filteredData = data.filter(row => {
    if (!filter) return true;
    const lf = filter.toLowerCase();
    return Object.values(row).some(v => String(v).toLowerCase().includes(lf));
  });

  const sortedData = [...filteredData].sort((a, b) => {
    if (!sortKey) return 0;
    const av = String(a[sortKey] ?? '');
    const bv = String(b[sortKey] ?? '');
    return sortDir === 'asc' ? av.localeCompare(bv, undefined, { numeric: true }) : bv.localeCompare(av, undefined, { numeric: true });
  });

  return (
    <div>
      {data.length > 5 && (
        <div className="mb-3 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: c.textMuted }} />
          <input type="text" placeholder="Filtrar..." value={filter} onChange={e => setFilter(e.target.value)} className="input pl-9 py-1.5 text-sm" />
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: `1px solid ${c.border}` }}>
              {columns.map(col => (
                <th key={col.key} onClick={() => handleSort(col.key)} className={`text-left px-3 py-2 font-medium cursor-pointer select-none ${col.className || ''}`} style={{ color: c.textMuted }}>
                  <span className="inline-flex items-center gap-1">{col.label}{sortKey === col.key && <ArrowUpDown className="w-3 h-3" />}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedData.length === 0 && (
              <tr><td colSpan={columns.length} className="text-center py-8" style={{ color: c.textMuted }}>{emptyMessage || 'Sin datos'}</td></tr>
            )}
            {sortedData.map((row, i) => (
              <tr key={row['.id'] || i} style={{ borderBottom: `1px solid ${c.border}` }}>
                {columns.map(col => (
                  <td key={col.key} className={`px-3 py-2 ${col.className || ''}`} style={{ color: c.textSecondary }}>
                    {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '-')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.length > 0 && <div className="mt-2 text-xs text-right" style={{ color: c.textMuted }}>{sortedData.length} de {data.length} registros</div>}
    </div>
  );
}

function getInterfaceIcon(type: string) {
  switch (type) {
    case 'ether': return Cable;
    case 'bridge': return Network;
    case 'wifi': return Radio;
    case 'lte': return Globe;
    case 'vlan': return Link2;
    case 'bonding': return Link2;
    default: return Cable;
  }
}

function getInterfaceColor(type: string, c: any) {
  switch (type) {
    case 'ether': return c.blue;
    case 'bridge': return c.purple;
    case 'wifi': return c.green;
    case 'lte': return c.yellow;
    case 'vlan': return c.cyan;
    default: return c.textMuted;
  }
}

// ─── Interfaces Tab ──────────────────────────────────────────
function InterfacesTab({ data, c }: { data: any; c: any }) {
  if (data?.error) return <div className="text-center py-8" style={{ color: c.red }}>{data.error}</div>;
  if (!Array.isArray(data)) return <div className="text-center py-8" style={{ color: c.textMuted }}>Sin datos</div>;
  const interfaces = data.filter((i: any) => i['.id'] && i.name);

  return (
    <div>
      <SectionHeader icon={Network} title="Interfaces" count={interfaces.length} c={c} />
      <DataTable columns={[
        { key: 'name', label: 'Nombre', render: (_: any, row: any) => {
          const Ico = getInterfaceIcon(row.type || 'ether');
          return <span className="inline-flex items-center gap-2"><Ico className="w-4 h-4" style={{ color: getInterfaceColor(row.type || 'ether', c) }} /><span className="font-medium" style={{ color: c.textPrimary }}>{row.name}</span></span>;
        }},
        { key: 'type', label: 'Tipo', render: (v: string) => <span style={{ color: c.textMuted }}>{v || '-'}</span> },
        { key: 'mac-address', label: 'MAC' },
        { key: 'actual-mtu', label: 'MTU', className: 'text-right' },
        { key: 'disabled', label: 'Estado', render: (v: string, row: any) => {
          if (v === 'true') return <StatusBadge active={false} label="Deshabilitada" c={c} />;
          if (row.running === 'true') return <StatusBadge active={true} label="Running" c={c} />;
          if (row['link-downs'] && parseInt(row['link-downs']) > 0) return <StatusBadge active={false} label="Link Down" c={c} />;
          return <StatusBadge active={true} label="Up" c={c} />;
        }},
        { key: 'comment', label: 'Comentario' },
      ]} data={interfaces} emptyMessage="No se encontraron interfaces" c={c} />
    </div>
  );
}

// ─── Traffic Tab ──────────────────────────────────────────
const TRAFFIC_RANGES = [
  { hours: 1, label: '1 hora' },
  { hours: 6, label: '6 horas' },
  { hours: 24, label: '24 horas' },
  { hours: 168, label: '7 días' },
];

function TrafficTab({ routerId, c }: { routerId: number; c: any }) {
  const [interfaces, setInterfaces] = useState<string[]>([]);
  const [iface, setIface] = useState<string>('');
  const [hours, setHours] = useState<number>(1);
  const [samples, setSamples] = useState<TrafficSample[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    trafficAPI.interfaces(routerId)
      .then(list => { setInterfaces(list); if (list.length && !iface) setIface(list[0]); })
      .catch(() => {});
  }, [routerId]);

  const load = useCallback(() => {
    if (!iface) return;
    setLoading(true);
    trafficAPI.series(routerId, { interface: iface, hours })
      .then(setSamples)
      .catch((err: any) => toast.error(err.message || 'Error al cargar tráfico'))
      .finally(() => setLoading(false));
  }, [routerId, iface, hours]);
  useEffect(() => { load(); }, [load]);

  const chartData = samples.map(s => ({
    ts: s.timestamp,
    rx: s.rx_bps,
    tx: s.tx_bps,
  }));
  const peakRx = samples.reduce((m, s) => Math.max(m, s.rx_bps), 0);
  const peakTx = samples.reduce((m, s) => Math.max(m, s.tx_bps), 0);

  return (
    <div>
      <SectionHeader icon={Activity} title="Tráfico por Interfaz" c={c} />
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select className="input py-1.5 text-sm" style={{ maxWidth: 220 }} value={iface} onChange={e => setIface(e.target.value)}>
          {interfaces.length === 0 && <option value="">Sin datos aún</option>}
          {interfaces.map(i => <option key={i} value={i}>{i}</option>)}
        </select>
        <div className="flex gap-1">
          {TRAFFIC_RANGES.map(r => (
            <button key={r.hours} onClick={() => setHours(r.hours)} className="px-3 py-1.5 text-xs font-medium rounded"
              style={{ background: hours === r.hours ? c.textLink : c.bgHover, color: hours === r.hours ? '#fff' : c.textMuted }}>
              {r.label}
            </button>
          ))}
        </div>
        <button onClick={load} className="btn-secondary text-sm"><RefreshCw className={`w-4 h-4 inline mr-1 ${loading ? 'animate-spin' : ''}`} />Recargar</button>
      </div>

      {interfaces.length === 0 ? (
        <div className="text-center py-12" style={{ color: c.textMuted }}>
          Todavía no hay muestras de tráfico. El sampler registra datos cada ~60s mientras el router está en línea; probá de nuevo en unos minutos.
        </div>
      ) : samples.length < 2 ? (
        <div className="text-center py-12" style={{ color: c.textMuted }}>
          {loading ? 'Cargando...' : 'Datos insuficientes para graficar este rango.'}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 mb-4" style={{ maxWidth: 420 }}>
            <div className="card p-3 text-center">
              <p className="text-xs" style={{ color: c.textMuted }}>Pico RX (bajada)</p>
              <p className="text-lg font-bold" style={{ color: c.green }}>{formatBps(peakRx)}</p>
            </div>
            <div className="card p-3 text-center">
              <p className="text-xs" style={{ color: c.textMuted }}>Pico TX (subida)</p>
              <p className="text-lg font-bold" style={{ color: c.blue }}>{formatBps(peakTx)}</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={chartData} margin={{ top: 10, right: 20, bottom: 0, left: 10 }}>
              <defs>
                <linearGradient id="rxGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={c.green} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={c.green} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="txGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={c.blue} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={c.blue} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={c.chartGrid} strokeDasharray="3 3" />
              <XAxis dataKey="ts" tickFormatter={(t) => hours > 24
                ? new Date(t).toLocaleString('es-AR', { timeZone: getTimezone(), day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
                : formatTime(t)} tick={{ fill: c.textMuted, fontSize: 11 }} minTickGap={40} />
              <YAxis tickFormatter={formatBps} tick={{ fill: c.textMuted, fontSize: 11 }} width={70} />
              <Tooltip
                contentStyle={{ background: c.chartTooltipBg, border: `1px solid ${c.chartTooltipBorder}`, color: c.chartTooltipText, borderRadius: 8 }}
                labelFormatter={(t) => formatDateTime(t as string)}
                formatter={(v: number, name: string) => [formatBps(v), name === 'rx' ? 'RX (bajada)' : 'TX (subida)']}
              />
              <Legend formatter={(v) => v === 'rx' ? 'RX (bajada)' : 'TX (subida)'} />
              <Area type="monotone" dataKey="rx" stroke={c.green} fill="url(#rxGrad)" strokeWidth={2} />
              <Area type="monotone" dataKey="tx" stroke={c.blue} fill="url(#txGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}

// ─── DHCP Tab ──────────────────────────────────────────
function DhcpTab({ data, c }: { data: any; c: any }) {
  if (data?.error) return <div className="text-center py-8" style={{ color: c.red }}>{data.error}</div>;
  if (!Array.isArray(data)) return <div className="text-center py-8" style={{ color: c.textMuted }}>Sin datos</div>;
  const leases = data.filter((l: any) => l['.id']);

  return (
    <div>
      <SectionHeader icon={Users} title="DHCP Leases" count={leases.length} c={c} />
      <DataTable columns={[
        { key: 'address', label: 'IP', render: (v: string) => <span className="font-mono" style={{ color: c.textPrimary }}>{v || '-'}</span> },
        { key: 'mac-address', label: 'MAC', render: (v: string) => <span className="font-mono" style={{ color: c.textMuted }}>{v || '-'}</span> },
        { key: 'host-name', label: 'Host', render: (v: string) => <span className="font-medium" style={{ color: c.textPrimary }}>{v || '-'}</span> },
        { key: 'server', label: 'Servidor' },
        { key: 'status', label: 'Estado', render: (v: string) => v === 'bound' ? <StatusBadge active={true} label="Bound" c={c} /> : v === 'waiting' ? <StatusBadge active={false} label="Waiting" c={c} /> : <span style={{ color: c.textMuted }}>{v || '-'}</span> },
        { key: 'expires-after', label: 'Expira', render: (v: string) => <span style={{ color: c.textMuted }}>{v || '-'}</span> },
        { key: 'active-mac-address', label: 'Active MAC' },
        { key: 'comment', label: 'Comentario' },
      ]} data={leases} emptyMessage="No hay leases DHCP activos" c={c} />
    </div>
  );
}

// ─── ARP Tab ──────────────────────────────────────────
function ArpTab({ data, c }: { data: any; c: any }) {
  if (data?.error) return <div className="text-center py-8" style={{ color: c.red }}>{data.error}</div>;
  if (!Array.isArray(data)) return <div className="text-center py-8" style={{ color: c.textMuted }}>Sin datos</div>;
  const entries = data.filter((e: any) => e['.id']);

  return (
    <div>
      <SectionHeader icon={List} title="Tabla ARP" count={entries.length} c={c} />
      <DataTable columns={[
        { key: 'address', label: 'IP', render: (v: string) => <span className="font-mono" style={{ color: c.textPrimary }}>{v || '-'}</span> },
        { key: 'mac-address', label: 'MAC', render: (v: string) => <span className="font-mono" style={{ color: c.textMuted }}>{v || '-'}</span> },
        { key: 'interface', label: 'Interfaz', render: (v: string) => <span style={{ color: c.textSecondary }}>{v || '-'}</span> },
        { key: 'complete', label: 'Completo', render: (v: string) => v === 'true' ? <StatusBadge active={true} label="Sí" c={c} /> : <StatusBadge active={false} label="No" c={c} /> },
        { key: 'dynamic', label: 'Tipo', render: (_: string, row: any) => <span style={{ color: c.textMuted }}>{row.dynamic === 'true' ? 'Dinámico' : 'Estático'}</span> },
        { key: 'comment', label: 'Comentario' },
      ]} data={entries} emptyMessage="No hay entradas ARP" c={c} />
    </div>
  );
}

// ─── PPPoE Tab ──────────────────────────────────────────
function PppoeTab({ data, c }: { data: any; c: any }) {
  if (data?.error) return <div className="text-center py-8" style={{ color: c.red }}>{data.error}</div>;
  if (!Array.isArray(data)) return <div className="text-center py-8" style={{ color: c.textMuted }}>Sin datos</div>;
  const sessions = data.filter((s: any) => s['.id']);

  return (
    <div>
      <SectionHeader icon={Globe} title="Sesiones PPPoE" count={sessions.length} c={c} />
      <DataTable columns={[
        { key: 'name', label: 'Nombre', render: (v: string) => <span className="font-medium" style={{ color: c.textPrimary }}>{v || '-'}</span> },
        { key: 'user', label: 'Usuario' }, { key: 'service', label: 'Servicio' }, { key: 'interface', label: 'Interfaz' },
        { key: 'caller-id', label: 'Caller ID' }, { key: 'uptime', label: 'Uptime' },
        { key: 'bytes-in', label: 'Rx', render: (v: string) => <span style={{ color: c.green }}>{formatBytes(v)}</span> },
        { key: 'bytes-out', label: 'Tx', render: (v: string) => <span style={{ color: c.blue }}>{formatBytes(v)}</span> },
        { key: 'encoding', label: 'Encoding' },
      ]} data={sessions} emptyMessage="No hay sesiones PPPoE activas" c={c} />
    </div>
  );
}

// ─── Firewall Tab ──────────────────────────────────────────
function FirewallTab({ data, c }: { data: any; c: any }) {
  if (data?.error) return <div className="text-center py-8" style={{ color: c.red }}>{data.error}</div>;
  if (!data) return <div className="text-center py-8" style={{ color: c.textMuted }}>Sin datos</div>;

  const [subTab, setSubTab] = useState<'filter' | 'nat' | 'mangle'>('filter');
  const rules = data[subTab] || [];

  const chainColor = (chain: string) => {
    const m: Record<string, { bg: string; text: string }> = {
      input: { bg: c.redBg, text: c.red }, forward: { bg: c.yellowBg, text: c.yellow },
      output: { bg: c.blueBg, text: c.blue }, srcnat: { bg: c.purpleBg || c.bgHover, text: c.purple || c.blue },
      dstnat: { bg: c.cyanBg || c.bgHover, text: c.cyan || c.blue },
    };
    return m[chain] || { bg: c.bgHover, text: c.textMuted };
  };

  return (
    <div>
      <SectionHeader icon={Shield} title="Firewall" count={rules.length} c={c} />
      <div className="flex gap-1 mb-4" style={{ borderBottom: `1px solid ${c.border}` }}>
        {(['filter', 'nat', 'mangle'] as const).map(st => (
          <button key={st} onClick={() => setSubTab(st)} className="px-4 py-2 text-sm font-medium border-b-2 transition-colors" style={{
            borderBottomColor: subTab === st ? c.textLink : 'transparent',
            color: subTab === st ? c.textLink : c.textMuted,
          }}>
            {st.toUpperCase()} ({(data[st] || []).length})
          </button>
        ))}
      </div>
      <DataTable columns={[
        { key: 'chain', label: 'Chain', render: (v: string) => {
          const cc = chainColor(v);
          return <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: cc.bg, color: cc.text }}>{v}</span>;
        }},
        { key: 'action', label: 'Acción', render: (v: string) => <span className="font-medium" style={{ color: c.textPrimary }}>{v || '-'}</span> },
        { key: 'src-address', label: 'Src Address', render: (v: string) => <span className="font-mono">{v || '*'}</span> },
        { key: 'dst-address', label: 'Dst Address', render: (v: string) => <span className="font-mono">{v || '*'}</span> },
        { key: 'src-port', label: 'Src Port', render: (v: string) => <span className="font-mono">{v || '*'}</span> },
        { key: 'dst-port', label: 'Dst Port', render: (v: string) => <span className="font-mono">{v || '*'}</span> },
        { key: 'protocol', label: 'Proto', render: (v: string) => <span style={{ color: c.textMuted }}>{v || '-'}</span> },
        { key: 'in-interface', label: 'In Iface' }, { key: 'out-interface', label: 'Out Iface' },
        { key: 'disabled', label: 'Estado', render: (v: string) => v === 'true' ? <StatusBadge active={false} label="Deshab." c={c} /> : <StatusBadge active={true} c={c} /> },
        { key: 'comment', label: 'Comentario' },
      ]} data={rules} emptyMessage={`No hay reglas ${subTab.toUpperCase()}`} c={c} />
    </div>
  );
}

// ─── WireGuard Tab ──────────────────────────────────────────
function WireGuardTab({ data, c }: { data: any; c: any }) {
  if (data?.error) return <div className="text-center py-8" style={{ color: c.red }}>{data.error}</div>;
  if (!data) return <div className="text-center py-8" style={{ color: c.textMuted }}>Sin datos</div>;

  return (
    <div className="space-y-6">
      <div>
        <SectionHeader icon={Lock} title="Interfaces WireGuard" count={(data.interfaces || []).length} c={c} />
        <DataTable columns={[
          { key: 'name', label: 'Nombre', render: (v: string) => <span className="font-medium" style={{ color: c.textPrimary }}>{v || '-'}</span> },
          { key: 'listen-port', label: 'Listen Port', render: (v: string) => <span className="font-mono">{v || '-'}</span> },
          { key: 'public-key', label: 'Public Key', render: (v: string) => <span className="font-mono text-xs">{v ? `${v.substring(0, 20)}...` : '-'}</span> },
          { key: 'mtu', label: 'MTU', className: 'text-right' },
          { key: 'running', label: 'Estado', render: (v: string) => <StatusBadge active={v === 'true'} c={c} /> },
        ]} data={data.interfaces || []} emptyMessage="No hay interfaces WireGuard configuradas" c={c} />
      </div>
      <div>
        <SectionHeader icon={Users} title="Peers" count={(data.peers || []).length} c={c} />
        <DataTable columns={[
          { key: 'interface', label: 'Interfaz' },
          { key: 'public-key', label: 'Public Key', render: (v: string) => <span className="font-mono text-xs">{v ? `${v.substring(0, 24)}...` : '-'}</span> },
          { key: 'endpoint', label: 'Endpoint', render: (v: string) => <span className="font-mono">{v || '-'}</span> },
          { key: 'allowed-address', label: 'Allowed Address', render: (v: string) => <span className="font-mono">{v || '-'}</span> },
          { key: 'latest-handshake', label: 'Handshake' },
          { key: 'comment', label: 'Comentario' },
        ]} data={data.peers || []} emptyMessage="No hay peers WireGuard configurados" c={c} />
      </div>
    </div>
  );
}

// ─── Config CRUD Tab ──────────────────────────────────────────
type ConfigSection = 'addresses' | 'firewall' | 'nat' | 'dhcp' | 'dns' | 'routes' | 'wireguard';

interface FieldDef { key: string; label: string; placeholder?: string; options?: string[]; type?: 'text' | 'select'; }
interface SectionDef { key: ConfigSection; label: string; icon: any; rosPath: string; fields: FieldDef[]; idField: string; labelField: string; hasDisabled?: boolean; }

const FieldInput = ({ field, value, onChange, interfaceOptions, c }: { field: FieldDef; value: string; onChange: (val: string) => void; interfaceOptions?: string[]; c: any }) => {
  const isIfaceField = field.key === 'interface' || field.key === 'in-interface' || field.key === 'out-interface';
  const options = (isIfaceField && interfaceOptions && interfaceOptions.length > 0) ? interfaceOptions : field.options;
  return (
    <div>
      <label className="block text-xs mb-1" style={{ color: c.textMuted }}>{field.label}</label>
      {options ? (
        <select className="input py-1.5 text-sm" value={value} onChange={e => onChange(e.target.value)}>
          <option value="">-- Seleccionar --</option>{options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input type="text" className="input py-1.5 text-sm" placeholder={field.placeholder} value={value} onChange={e => onChange(e.target.value)} />
      )}
    </div>
  );
};

const CONFIG_SECTIONS: SectionDef[] = [
  { key: 'addresses', label: 'Direcciones IP', icon: Network, rosPath: '/ip address', fields: [
    { key: 'address', label: 'Dirección', placeholder: '192.168.1.1/24' }, { key: 'interface', label: 'Interfaz', placeholder: 'bridge1' }, { key: 'comment', label: 'Comentario' },
  ], idField: '.id', labelField: 'address' },
  { key: 'firewall', label: 'Firewall Filter', icon: Shield, rosPath: '/ip firewall filter', hasDisabled: true, fields: [
    { key: 'chain', label: 'Chain', type: 'select', options: ['input', 'forward', 'output'] }, { key: 'action', label: 'Acción', type: 'select', options: ['accept', 'drop', 'reject', 'log', 'fasttrack-connection'] },
    { key: 'src-address', label: 'Src Address', placeholder: '192.168.1.0/24' }, { key: 'dst-address', label: 'Dst Address' },
    { key: 'src-port', label: 'Src Port', placeholder: '80,443' }, { key: 'dst-port', label: 'Dst Port', placeholder: '80,443' },
    { key: 'protocol', label: 'Protocolo', type: 'select', options: ['tcp', 'udp', 'icmp', 'icmpv6'] },
    { key: 'in-interface', label: 'In Interface', placeholder: 'ether1' }, { key: 'out-interface', label: 'Out Interface', placeholder: 'pppoe-out1' }, { key: 'comment', label: 'Comentario' },
  ], idField: '.id', labelField: 'comment' },
  { key: 'nat', label: 'Firewall NAT', icon: Globe, rosPath: '/ip firewall nat', hasDisabled: true, fields: [
    { key: 'chain', label: 'Chain', type: 'select', options: ['srcnat', 'dstnat'] }, { key: 'action', label: 'Acción', type: 'select', options: ['masquerade', 'src-nat', 'dst-nat', 'redirect'] },
    { key: 'src-address', label: 'Src Address', placeholder: '192.168.1.0/24' }, { key: 'dst-address', label: 'Dst Address' },
    { key: 'to-addresses', label: 'To Addresses', placeholder: '200.1.1.1' }, { key: 'to-ports', label: 'To Ports', placeholder: '8080' },
    { key: 'dst-port', label: 'Dst Port', placeholder: '80' }, { key: 'protocol', label: 'Protocolo', type: 'select', options: ['tcp', 'udp'] },
    { key: 'in-interface', label: 'In Interface' }, { key: 'out-interface', label: 'Out Interface', placeholder: 'pppoe-out1' }, { key: 'comment', label: 'Comentario' },
  ], idField: '.id', labelField: 'comment' },
  { key: 'dhcp', label: 'DHCP Leases', icon: Users, rosPath: '/ip dhcp-server lease', fields: [
    { key: 'address', label: 'Dirección IP', placeholder: '192.168.1.100' }, { key: 'mac-address', label: 'MAC Address', placeholder: 'AA:BB:CC:DD:EE:FF' }, { key: 'comment', label: 'Comentario' },
  ], idField: '.id', labelField: 'host-name' },
  { key: 'dns', label: 'DNS Estático', icon: Globe, rosPath: '/ip dns static', fields: [
    { key: 'name', label: 'Nombre', placeholder: 'mi-servidor.local' }, { key: 'address', label: 'Dirección IP', placeholder: '192.168.1.10' },
    { key: 'type', label: 'Tipo', type: 'select', options: ['A', 'AAAA', 'CNAME', 'MX', 'TXT'] }, { key: 'comment', label: 'Comentario' },
  ], idField: '.id', labelField: 'name' },
  { key: 'routes', label: 'Rutas', icon: ArrowUpDown, rosPath: '/ip route', fields: [
    { key: 'dst-address', label: 'Dst Address', placeholder: '10.0.0.0/8' }, { key: 'gateway', label: 'Gateway', placeholder: '192.168.1.1' },
    { key: 'distance', label: 'Distance', placeholder: '1' }, { key: 'comment', label: 'Comentario' },
  ], idField: '.id', labelField: 'comment' },
  { key: 'wireguard', label: 'WireGuard', icon: Lock, rosPath: '/interface wireguard', fields: [
    { key: 'name', label: 'Nombre', placeholder: 'wg1' }, { key: 'listen-port', label: 'Listen Port', placeholder: '13231' },
    { key: 'mtu', label: 'MTU', placeholder: '1420' }, { key: 'comment', label: 'Comentario' },
  ], idField: '.id', labelField: 'name' },
];

function ConfigTab({ routerId, c }: { routerId: number; c: any }) {
  const { hasPermission } = useAuth();
  const canView = (f: string) => hasPermission(`routers:view_${f}`);
  const canCreate = (f: string) => hasPermission(`routers:cfg_${f}_create`);
  const canEdit = (f: string) => hasPermission(`routers:cfg_${f}_edit`);
  const canDelete = (f: string) => hasPermission(`routers:cfg_${f}_delete`);
  const visibleSections = CONFIG_SECTIONS.filter(s => canView(s.key) || canCreate(s.key) || canEdit(s.key) || canDelete(s.key));
  const [section, setSection] = useState<ConfigSection>(visibleSections[0]?.key || 'addresses');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<any | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [executing, setExecuting] = useState(false);
  const [filter, setFilter] = useState('');
  const [customCmd, setCustomCmd] = useState('');
  const [routerInterfaces, setRouterInterfaces] = useState<string[]>([]);
  const current = CONFIG_SECTIONS.find(s => s.key === section)!;

  useEffect(() => { routerosAPI.interfaces(routerId).then((data: any) => { if (Array.isArray(data)) setRouterInterfaces(data.map((i: any) => i.name).filter(Boolean)); }).catch(() => {}); }, [routerId]);

  const loadData = useCallback(async () => {
    setLoading(true); setEditingItem(null); setCreating(false); setFilter('');
    try { const data = await routerosAPI.configSection(routerId, section); setItems(Array.isArray(data) ? data : []); }
    catch (err: any) { toast.error(err.message); setItems([]); } finally { setLoading(false); }
  }, [routerId, section]);
  useEffect(() => { loadData(); }, [loadData]);

  const apiPath = current.rosPath.replace(/ /g, '/');
  const buildAddCmd = (data: Record<string, string>) => {
    const parts = [`${apiPath}/add`];
    for (const f of current.fields) { const v = data[f.key]; if (v !== undefined && v !== '') { const val = v.includes(' ') || v.includes('"') ? `"${v.replace(/"/g, '\\"')}"` : v; parts.push(`=${f.key}=${val}`); } }
    return parts.join(' ');
  };
  const buildSetCmd = (id: string, data: Record<string, string>) => {
    const parts = [`${apiPath}/set`, id];
    for (const f of current.fields) { const v = data[f.key]; if (v !== undefined) { const val = v === '' ? '""' : (v.includes(' ') || v.includes('"') ? `"${v.replace(/"/g, '\\"')}"` : v); parts.push(`=${f.key}=${val}`); } }
    return parts.join(' ');
  };
  const execCmd = async (cmd: string): Promise<boolean> => {
    try { const result = await routerosAPI.command(routerId, cmd) as any; if (result.success) return true; toast.error(result.error || 'Error del router'); return false; }
    catch (err: any) { toast.error(err.message); return false; }
  };
  const handleCreate = async () => { const cmd = buildAddCmd(form); if (!confirm(`Crear nuevo registro?\n\n${cmd}`)) return; setExecuting(true); const ok = await execCmd(cmd); setExecuting(false); if (ok) { toast.success('Registro creado'); setCreating(false); setForm({}); loadData(); } };
  const handleUpdate = async () => { const cmd = buildSetCmd(editingItem[current.idField], form); if (!confirm(`Modificar registro?\n\n${cmd}`)) return; setExecuting(true); const ok = await execCmd(cmd); setExecuting(false); if (ok) { toast.success('Registro modificado'); setEditingItem(null); setForm({}); loadData(); } };
  const handleDelete = async (item: any) => { const label = item[current.labelField] || item[current.idField]; if (!confirm(`¿Eliminar "${label}"?`)) return; setExecuting(true); const ok = await execCmd(`${apiPath}/remove =numbers=${item[current.idField]}`); setExecuting(false); if (ok) { toast.success('Registro eliminado'); loadData(); } };
  const handleToggleDisabled = async (item: any) => { const isDisabled = item.disabled === 'true'; const action = isDisabled ? 'enable' : 'disable'; setExecuting(true); const ok = await execCmd(`${apiPath}/${action} =numbers=${item[current.idField]}`); setExecuting(false); if (ok) { toast.success(isDisabled ? 'Regla habilitada' : 'Regla deshabilitada'); loadData(); } };
  const handleCustomExec = async () => { if (!customCmd || !confirm(`¿Ejecutar?\n\n${customCmd}`)) return; setExecuting(true); const ok = await execCmd(customCmd); setExecuting(false); if (ok) { toast.success('Comando ejecutado'); setCustomCmd(''); loadData(); } };
  const startEdit = (item: any) => { setCreating(false); setEditingItem(item); const f: Record<string, string> = {}; for (const field of current.fields) f[field.key] = item[field.key] || ''; setForm(f); };
  const startCreate = () => { setEditingItem(null); setCreating(true); const f: Record<string, string> = {}; for (const field of current.fields) f[field.key] = ''; setForm(f); };

  const filteredItems = items.filter(item => { if (!filter) return true; const lf = filter.toLowerCase(); return Object.values(item).some(v => String(v).toLowerCase().includes(lf)); });

  return (
    <div className="space-y-4">
      {visibleSections.length === 0 ? (
        <div className="text-center py-8" style={{ color: c.textMuted }}>No tienes permiso para gestionar la configuración de este router.</div>
      ) : (
        <>
      <SectionHeader icon={Settings} title="Configuración del Router" c={c} />
      <div className="flex gap-1 overflow-x-auto" style={{ borderBottom: `1px solid ${c.border}` }}>
        {visibleSections.map(s => {
          const Ico = s.icon;
          return <button key={s.key} onClick={() => setSection(s.key)} className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap"
            style={{ borderBottomColor: section === s.key ? c.textLink : 'transparent', color: section === s.key ? c.textLink : c.textMuted }}>
            <Ico className="w-3.5 h-3.5" />{s.label}
          </button>;
        })}
      </div>

      {section === ('custom' as any) && hasPermission('routers:terminal') && (
        <div className="card">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Comando RouterOS Personalizado</h3>
          <textarea className="input font-mono text-sm" rows={3} placeholder="/ip firewall filter add chain=input action=accept src-address=192.168.1.0/24" value={customCmd} onChange={e => setCustomCmd(e.target.value)} />
          <div className="mt-3 flex justify-end">
            <button onClick={handleCustomExec} disabled={executing || !customCmd} className="btn-primary disabled:opacity-50">{executing ? 'Ejecutando...' : 'Ejecutar'}</button>
          </div>
        </div>
      )}

      {section !== ('custom' as any) && (
        <>
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              {canCreate(current.key) && (
                <button onClick={startCreate} className="btn-primary text-sm"><Plus className="w-4 h-4 inline mr-1" />Nuevo</button>
              )}
              <button onClick={loadData} className="btn-secondary text-sm"><RefreshCw className={`w-4 h-4 inline mr-1 ${loading ? 'animate-spin' : ''}`} />Recargar</button>
            </div>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: c.textMuted }} />
              <input type="text" className="input pl-9 py-1.5 text-sm" placeholder="Filtrar registros..." value={filter} onChange={e => setFilter(e.target.value)} />
            </div>
          </div>

          {(creating || editingItem) && (
            <div className="card" style={{ borderColor: c.textLink + '80' }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>{creating ? 'Crear nuevo registro' : `Editar: ${editingItem[current.labelField] || editingItem[current.idField]}`}</h3>
                <button onClick={() => { setCreating(false); setEditingItem(null); setForm({}); }} style={{ color: c.textMuted }}><XCircle className="w-5 h-5" /></button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {current.fields.map(f => <FieldInput key={f.key} field={f} value={form[f.key] || ''} onChange={val => setForm(prev => ({ ...prev, [f.key]: val }))} interfaceOptions={routerInterfaces} c={c} />)}
              </div>
              <div className="mt-4 flex justify-end gap-3">
                <button onClick={() => { setCreating(false); setEditingItem(null); setForm({}); }} className="btn-secondary text-sm">Cancelar</button>
                <button onClick={creating ? handleCreate : handleUpdate} disabled={executing} className="btn-primary text-sm disabled:opacity-50">{executing ? 'Ejecutando...' : (creating ? 'Crear' : 'Guardar cambios')}</button>
              </div>
            </div>
          )}

          <div className="card overflow-hidden p-0">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-5 h-5 animate-spin mr-2" style={{ color: c.textLink }} />
                <span style={{ color: c.textMuted }}>Cargando datos del router...</span>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="text-center py-12" style={{ color: c.textMuted }}>{items.length === 0 ? 'No hay registros en esta sección' : 'No se encontraron resultados'}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr style={{ borderBottom: `1px solid ${c.border}` }}>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: c.textMuted }}>#</th>
                    {current.fields.map(f => <th key={f.key} className="text-left px-3 py-2 font-medium" style={{ color: c.textMuted }}>{f.label}</th>)}
                    <th className="text-right px-3 py-2 font-medium" style={{ color: c.textMuted }}>Acciones</th>
                  </tr></thead>
                  <tbody>
                    {filteredItems.map((item, i) => {
                      const isDisabled = item.disabled === 'true';
                      return (
                        <tr key={item[current.idField] || i} style={{ borderBottom: `1px solid ${c.border}`, opacity: isDisabled ? 0.5 : 1 }}>
                          <td className="px-3 py-2 text-xs" style={{ color: c.textMuted }}>{i + 1}</td>
                          {current.fields.map(f => (
                            <td key={f.key} className="px-3 py-2 text-sm" style={{ color: c.textSecondary }}>
                              {f.key === 'action' ? <span className="font-medium" style={{ color: c.textPrimary }}>{item[f.key] || '-'}</span>
                              : f.key === 'chain' ? <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: c.bgHover, color: c.textSecondary }}>{item[f.key] || '-'}</span>
                              : f.key === 'disabled' ? (isDisabled
                                ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs" style={{ background: c.redBg, color: c.red }}><PowerOff className="w-3 h-3" />Off</span>
                                : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs" style={{ background: c.greenBg, color: c.green }}><Power className="w-3 h-3" />On</span>)
                              : f.key === current.labelField ? <span className="font-medium" style={{ color: c.textPrimary }}>{item[f.key] || '-'}</span>
                              : <span style={{ color: c.textMuted }}>{item[f.key] || '-'}</span>}
                            </td>
                          ))}
                          <td className="px-3 py-2 text-right">
                            <div className="flex items-center justify-end gap-1">
                              {current.hasDisabled && canEdit(current.key) && <button onClick={() => handleToggleDisabled(item)} className="p-1 rounded" style={{ color: isDisabled ? c.green : c.green }} title={isDisabled ? 'Habilitar' : 'Deshabilitar'} disabled={executing}>{isDisabled ? <Power className="w-4 h-4" /> : <PowerOff className="w-4 h-4" />}</button>}
                              {canEdit(current.key) && <button onClick={() => startEdit(item)} className="p-1 rounded" style={{ color: c.textMuted }} title="Editar"><Edit3 className="w-4 h-4" /></button>}
                              {canDelete(current.key) && <button onClick={() => handleDelete(item)} className="p-1 rounded" style={{ color: c.red }} title="Eliminar" disabled={executing}><Trash2 className="w-4 h-4" /></button>}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {!loading && items.length > 0 && <div className="px-3 py-2 border-t text-xs text-right" style={{ borderColor: c.border, color: c.textMuted }}>{filteredItems.length} de {items.length} registros</div>}
          </div>
        </>
      )}

      <div className="card" style={{ background: c.bgPage }}>
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0" style={{ color: c.yellow }} />
          <div className="text-sm" style={{ color: c.textMuted }}>
            <p className="mb-1"><strong style={{ color: c.textSecondary }}>Atención:</strong> Los cambios se aplican directamente al router. Verificá antes de guardar.</p>
            <p>Para comandos avanzados usá la pestaña <strong style={{ color: c.textSecondary }}>Terminal</strong>.</p>
          </div>
        </div>
      </div>
      </>
      )}
    </div>
  );
}

function PingTab({ routerId, c }: { routerId: number; c: any }) {
  const [target, setTarget] = useState('');
  const [output, setOutput] = useState('');
  const [pinging, setPinging] = useState(false);
  const doPing = async () => {
    if (!target.trim()) return;
    setPinging(true); setOutput('');
    try {
      const res = await routerosAPI.ping(routerId, target.trim());
      if (res.success) setOutput(res.output); else setOutput(res.error || 'Error');
    } catch (e: any) { setOutput(e.message || 'Error de conexión'); }
    setPinging(false);
  };
  return (
    <div className="card">
      <h4 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Ping desde el router</h4>
      <div className="flex items-center gap-2 mb-3">
        <input value={target} onChange={e => setTarget(e.target.value)}
          placeholder="IP o dominio"
          className="input flex-1 text-sm py-1.5"
          style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
          onKeyDown={e => e.key === 'Enter' && doPing()} />
        <button onClick={doPing} disabled={pinging || !target.trim()} className="btn-primary text-sm py-1.5">
          {pinging ? 'Ping...' : 'Ping'}
        </button>
      </div>
      {output && (
        <pre className="text-xs p-3 rounded overflow-auto max-h-48 font-mono" style={{ background: c.bgCard, color: c.green, border: `1px solid ${c.borderLight}` }}>{output}</pre>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────
export default function RouterDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [router, setRouter] = useState<RouterDevice | null>(null);
  const [tab, setTab] = useState<Tab>('overview');
  const [tabData, setTabData] = useState<any>(null);
  const [loadingTab, setLoadingTab] = useState(false);
  const { c } = useTheme();
  const { hasPermission } = useAuth();

  const cfgPermitted = CONFIG_SECTIONS.some(s => hasPermission(`routers:cfg_${s.key}_create`) || hasPermission(`routers:cfg_${s.key}_edit`) || hasPermission(`routers:cfg_${s.key}_delete`));
  const canView = (f: string) => hasPermission(`routers:view_${f}`);
  const anyView = ['interfaces', 'traffic', 'arp', 'dhcp', 'pppoe', 'firewall', 'wireguard', 'addresses', 'dns', 'routes', 'nat'].some(f => hasPermission(`routers:view_${f}`));
  const configViewable = CONFIG_SECTIONS.some(s => canView(s.key)) || cfgPermitted;

  useEffect(() => { if (id) routersAPI.get(Number(id)).then(setRouter).catch(() => navigate('/routers')); }, [id]);

  const loadTab = useCallback(async (t: Tab) => {
    if (!router) return;
    setTab(t); setTabData(null);
    if (t === 'overview' || t === 'config' || t === 'traffic' || t === 'ping') return;
    setLoadingTab(true);
    try {
      const methods: Record<string, () => Promise<any>> = {
        interfaces: () => routerosAPI.interfaces(router.id), dhcp: () => routerosAPI.dhcp(router.id),
        arp: () => routerosAPI.arp(router.id),
        pppoe: () => routerosAPI.pppoe(router.id), firewall: () => routerosAPI.firewall(router.id),
        wireguard: () => routerosAPI.wireguard(router.id),
      };
      setTabData(await methods[t]());
    } catch (err: any) { toast.error(err.message || 'Error al cargar datos'); } finally { setLoadingTab(false); }
  }, [router]);

  const handleRefresh = async () => {
    if (!router) return;
    try { await routersAPI.check(router.id); const updated = await routersAPI.get(router.id); setRouter(updated); toast.success('Estado actualizado'); if (tab !== 'overview' && tab !== 'config') loadTab(tab); } catch { toast.error('Error al actualizar'); }
  };

  if (!router) return <div className="flex items-center justify-center h-64" style={{ color: c.textMuted }}><RefreshCw className="w-5 h-5 animate-spin mr-2" />Cargando router...</div>;

  const tabs = ([
    { key: 'overview' as Tab, label: 'General', icon: Server },
    { key: 'interfaces' as Tab, label: 'Interfaces', icon: Network },
    { key: 'traffic' as Tab, label: 'Tráfico', icon: Activity },
    { key: 'dhcp' as Tab, label: 'DHCP', icon: Users },
    { key: 'arp' as Tab, label: 'ARP', icon: List },
    { key: 'pppoe' as Tab, label: 'PPPoE', icon: Globe },
    { key: 'firewall' as Tab, label: 'Firewall', icon: Shield },
    { key: 'wireguard' as Tab, label: 'WireGuard', icon: Lock },
    { key: 'ping' as Tab, label: 'Ping', icon: Activity },
    { key: 'config' as Tab, label: 'Configuración', icon: Settings },
  ] as { key: Tab; label: string; icon: any }[]).filter(t => {
    switch (t.key) {
      case 'overview': return anyView;
      case 'interfaces': return canView('interfaces');
      case 'traffic': return canView('traffic');
      case 'dhcp': return canView('dhcp');
      case 'arp': return canView('arp');
      case 'pppoe': return canView('pppoe');
      case 'firewall': return canView('firewall');
      case 'wireguard': return canView('wireguard');
      case 'ping': return hasPermission('routers:ping');
      case 'config': return configViewable;
      default: return true;
    }
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/routers')} style={{ color: c.textMuted }}><ArrowLeft className="w-5 h-5" /></button>
        <div className="flex items-center gap-3 flex-1">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: router.is_online ? c.greenBg : c.redBg }}>
            {router.is_online ? <Wifi className="w-6 h-6" style={{ color: c.green }} /> : <WifiOff className="w-6 h-6" style={{ color: c.red }} />}
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>{router.name}</h1>
            <p style={{ color: c.textMuted }}>{router.ip_address} - {router.model || 'Modelo desconocido'}</p>
          </div>
        </div>
        <button onClick={handleRefresh} className="btn-secondary"><RefreshCw className="w-4 h-4 inline mr-2" />Actualizar</button>
        {hasPermission('routers:terminal') && (
          <button onClick={() => navigate(`/terminal?router=${router.id}`)} className="btn-primary"><Terminal className="w-4 h-4 inline mr-2" />Terminal</button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {[
          { icon: Cpu, color: c.textLink, value: `${router.cpu_usage ?? '--'}%`, label: 'CPU' },
          { icon: MemoryStick, color: c.yellow, value: `${router.ram_usage ?? '--'}%`, label: 'RAM' },
          { icon: Thermometer, color: router.temperature && router.temperature > 70 ? c.red : c.orange, value: router.temperature ? `${router.temperature}°C` : '--', label: 'Temp' },
          { icon: Zap, color: c.blue, value: router.voltage ? `${router.voltage}V` : '--', label: 'Voltaje' },
          { icon: HardDrive, color: c.purple || c.blue, value: router.hdd_free != null ? `${router.hdd_free}MB` : '--', label: 'Disco libre' },
          { icon: Clock, color: c.green, value: router.uptime ?? '--', label: 'Uptime', isSmall: true },
          { icon: Server, color: c.textMuted, value: router.routeros_version ?? '--', label: 'RouterOS', isSmall: true },
        ].map((stat, i) => (
          <div key={i} className="card p-4 text-center">
            <stat.icon className="w-5 h-5 mx-auto mb-1" style={{ color: stat.color }} />
            <p className={`font-bold ${stat.isSmall ? 'text-sm' : 'text-lg'}`} style={{ color: c.textPrimary }}>{stat.value}</p>
            <p className="text-xs" style={{ color: c.textMuted }}>{stat.label}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-1 overflow-x-auto" style={{ borderBottom: `1px solid ${c.border}` }}>
        {tabs.map((t) => (
          <button key={t.key} onClick={() => loadTab(t.key)} className="flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap"
            style={{ borderBottomColor: tab === t.key ? c.textLink : 'transparent', color: tab === t.key ? c.textLink : c.textMuted }}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>

      <div className="card">
        {loadingTab && <div className="flex items-center justify-center py-12"><RefreshCw className="w-5 h-5 animate-spin mr-2" style={{ color: c.textLink }} /><span style={{ color: c.textMuted }}>Consultando router...</span></div>}

        {tab === 'overview' && !loadingTab && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h3 className="text-lg font-semibold" style={{ color: c.textPrimary }}>Información</h3>
              {[['Hostname', router.hostname], ['IP', router.ip_address], ['MAC', router.mac_address], ['Modelo', router.model], ['Serial', router.serial_number],
                ['Identidad', router.identity], ['RouterOS', router.routeros_version], ['Acceso', `${router.access_method}:${router.access_port}`],
              ].filter(([, v]) => v).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm"><span style={{ color: c.textMuted }}>{k}</span><span style={{ color: c.textSecondary }}>{v}</span></div>
              ))}
            </div>
            <div className="space-y-3">
              <h3 className="text-lg font-semibold" style={{ color: c.textPrimary }}>Cliente</h3>
              {hasPermission('routers:details') ? (
                <>
                  {[['Nombre', router.client_name], ['Teléfono', router.client_phone], ['Email', router.client_email], ['Ciudad', router.city], ['Dirección', router.address],
                  ].filter(([, v]) => v).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-sm"><span style={{ color: c.textMuted }}>{k}</span><span style={{ color: c.textSecondary }}>{v}</span></div>
                  ))}
                  {router.notes && <div className="mt-4"><span className="text-sm" style={{ color: c.textMuted }}>Notas</span><p className="text-sm mt-1" style={{ color: c.textSecondary }}>{router.notes}</p></div>}
                </>
              ) : (
                <p className="text-sm" style={{ color: c.textMuted }}>No tienes permiso para ver los datos del cliente.</p>
              )}
            </div>
          </div>
        )}

        {tab === 'interfaces' && !loadingTab && <ErrorBoundary key="interfaces"><InterfacesTab data={tabData} c={c} /></ErrorBoundary>}
        {tab === 'traffic' && <ErrorBoundary key="traffic"><TrafficTab routerId={router.id} c={c} /></ErrorBoundary>}
        {tab === 'dhcp' && !loadingTab && <ErrorBoundary key="dhcp"><DhcpTab data={tabData} c={c} /></ErrorBoundary>}
        {tab === 'arp' && !loadingTab && <ErrorBoundary key="arp"><ArpTab data={tabData} c={c} /></ErrorBoundary>}
        {tab === 'pppoe' && !loadingTab && <ErrorBoundary key="pppoe"><PppoeTab data={tabData} c={c} /></ErrorBoundary>}
        {tab === 'firewall' && !loadingTab && <ErrorBoundary key="firewall"><FirewallTab data={tabData} c={c} /></ErrorBoundary>}
        {tab === 'wireguard' && !loadingTab && <ErrorBoundary key="wireguard"><WireGuardTab data={tabData} c={c} /></ErrorBoundary>}
        {tab === 'ping' && <ErrorBoundary key="ping"><PingTab routerId={router.id} c={c} /></ErrorBoundary>}
        {tab === 'config' && !loadingTab && <ErrorBoundary key="config"><ConfigTab routerId={router.id} c={c} /></ErrorBoundary>}
      </div>
    </div>
  );
}

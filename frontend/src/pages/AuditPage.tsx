import { useState, useEffect } from 'react';
import { auditAPI, type RouterHistoryEntry } from '../services/api';
import type { AuditLogEntry } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import {
  ClipboardList, ChevronLeft, ChevronRight, Search, Filter, X,
  Activity, ChevronDown, ChevronUp, Download, Server, Undo2,
} from 'lucide-react';
import { formatDateTime } from '../utils/date';

function SystemAuditTab({ c }: { c: any }) {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [userFilter, setUserFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filterOptions, setFilterOptions] = useState<{ actions: string[]; resource_types: string[]; usernames: string[] }>({ actions: [], resource_types: [], usernames: [] });
  const [stats, setStats] = useState<{ total: number; by_action: { action: string; count: number }[] } | null>(null);
  const limit = 30;

  const load = () => {
    setLoading(true);
    auditAPI.list({
      page, username: userFilter || undefined, action: actionFilter || undefined,
      resource_type: resourceFilter || undefined, search: searchFilter || undefined,
      date_from: dateFrom || undefined, date_to: dateTo || undefined,
    }).then((data) => { setLogs(data.logs); setTotal(data.total); })
      .catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, userFilter, actionFilter, resourceFilter]);
  useEffect(() => {
    Promise.all([auditAPI.filters(), auditAPI.stats()]).then(([f, s]) => { setFilterOptions(f); setStats(s); }).catch(console.error);
  }, []);

  const totalPages = Math.ceil(total / limit);
  const activeFilters = [userFilter, actionFilter, resourceFilter, searchFilter, dateFrom, dateTo].filter(Boolean).length;
  const clearFilters = () => { setUserFilter(''); setActionFilter(''); setResourceFilter(''); setSearchFilter(''); setDateFrom(''); setDateTo(''); setPage(1); };

  const exportCSV = () => {
    const header = 'Fecha,Usuario,Acción,Recurso,Nombre,IP,Detalles\n';
    const rows = logs.map(l =>
      `"${l.timestamp || ''}","${l.username}","${l.action}","${l.resource_type}","${l.resource_name || ''}","${l.ip_address || ''}","${JSON.stringify(l.details || {}).replace(/"/g, '""')}"`
    ).join('\n');
    const blob = new Blob(['\ufeff' + header + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `auditoria_sistema_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const actionColor = (action: string) => {
    if (action.includes('create')) return c.green;
    if (action.includes('update') || action.includes('command')) return c.yellow;
    if (action.includes('delete')) return c.red;
    if (action.includes('login')) return c.blue;
    return c.textSecondary;
  };

  const actionLabel = (action: string) => {
    const map: Record<string, string> = {
      create: 'Agregar', update: 'Editar', delete: 'Eliminar',
      command: 'Comando', login: 'Login', login_failed: 'Login fallido', login_blocked: 'Login bloqueado',
    };
    return map[action] || action;
  };

  const resourceIcon = (type: string) => {
    const map: Record<string, string> = { router: 'Router', user: 'Usuario', group: 'Grupo', tag: 'Tag', template: 'Plantilla', backup: 'Backup', inventory: 'Inventario', auth: 'Auth' };
    return map[type] || type;
  };

  return (
    <div className="space-y-4">
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="card flex items-center gap-3 !p-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: c.accentLight }}>
              <ClipboardList className="w-4 h-4" style={{ color: c.accent }} />
            </div>
            <div>
              <p className="text-lg font-bold" style={{ color: c.textPrimary }}>{stats.total.toLocaleString()}</p>
              <p className="text-[10px]" style={{ color: c.textMuted }}>Total</p>
            </div>
          </div>
          {stats.by_action.slice(0, 3).map(a => (
            <div key={a.action} className="card flex items-center gap-3 !p-3">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${actionColor(a.action)}20` }}>
                <span className="text-sm font-bold" style={{ color: actionColor(a.action) }}>{a.count}</span>
              </div>
              <div>
                <p className="text-sm font-bold" style={{ color: c.textPrimary }}>{actionLabel(a.action)}</p>
                <p className="text-[10px]" style={{ color: c.textMuted }}>registros</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card !p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: c.textMuted }} />
            <input className="input pl-9 w-full text-sm" placeholder="Buscar..." value={searchFilter} onChange={e => setSearchFilter(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} />
          </div>
          <button onClick={() => setShowFilters(!showFilters)} className="btn-secondary text-sm">
            <Filter className="w-4 h-4 inline mr-1" />Filtros {activeFilters > 0 && <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold" style={{ background: c.accent, color: '#fff' }}>{activeFilters}</span>}
          </button>
          {activeFilters > 0 && <button onClick={clearFilters} className="text-xs flex items-center gap-1" style={{ color: c.textLink }}><X className="w-3 h-3" />Limpiar</button>}
          <button onClick={exportCSV} className="btn-secondary text-sm"><Download className="w-4 h-4 inline mr-1" />CSV</button>
        </div>
        {showFilters && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-3 pt-3" style={{ borderTop: `1px solid ${c.border}` }}>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Usuario</label>
              <select className="input w-full text-sm" value={userFilter} onChange={e => { setUserFilter(e.target.value); setPage(1); }}>
                <option value="">Todos</option>
                {filterOptions.usernames.map(u => <option key={u} value={u}>{u}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Acción</label>
              <select className="input w-full text-sm" value={actionFilter} onChange={e => { setActionFilter(e.target.value); setPage(1); }}>
                <option value="">Todas</option>
                {filterOptions.actions.map(a => <option key={a} value={a}>{actionLabel(a)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Recurso</label>
              <select className="input w-full text-sm" value={resourceFilter} onChange={e => { setResourceFilter(e.target.value); setPage(1); }}>
                <option value="">Todos</option>
                {filterOptions.resource_types.map(r => <option key={r} value={r}>{resourceIcon(r)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Desde</label>
              <input type="datetime-local" className="input w-full text-sm" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(1); }} />
            </div>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Hasta</label>
              <input type="datetime-local" className="input w-full text-sm" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(1); }} />
            </div>
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: `1px solid ${c.border}` }}>
              {['', 'Fecha', 'Usuario', 'Acción', 'Recurso', 'Nombre', 'IP'].map(h => (
                <th key={h} className="text-left py-2 px-3" style={{ color: c.textMuted }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <>
                <tr key={log.id} style={{ borderBottom: `1px solid ${c.border}` }} className="cursor-pointer hover:opacity-80 transition-opacity" onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}>
                  <td className="py-2 px-3 w-8">
                    {Object.keys(log.details || {}).length > 0 && (
                      expandedId === log.id ? <ChevronUp className="w-4 h-4" style={{ color: c.textMuted }} /> : <ChevronDown className="w-4 h-4" style={{ color: c.textMuted }} />
                    )}
                  </td>
                  <td className="py-2 px-3 text-xs whitespace-nowrap" style={{ color: c.textMuted }}>{log.timestamp ? formatDateTime(log.timestamp) : ''}</td>
                  <td className="py-2 px-3 font-medium" style={{ color: c.textLink }}>{log.username}</td>
                  <td className="py-2 px-3">
                    <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: `${actionColor(log.action)}20`, color: actionColor(log.action) }}>{actionLabel(log.action)}</span>
                  </td>
                  <td className="py-2 px-3" style={{ color: c.textSecondary }}>{resourceIcon(log.resource_type)}</td>
                  <td className="py-2 px-3" style={{ color: c.textPrimary }}>{log.resource_name || '-'}</td>
                  <td className="py-2 px-3 font-mono text-xs" style={{ color: c.textMuted }}>{log.ip_address || '-'}</td>
                </tr>
                {expandedId === log.id && Object.keys(log.details || {}).length > 0 && (
                  <tr key={`${log.id}-detail`}>
                    <td colSpan={7} className="px-6 py-3" style={{ background: c.bgHover, borderBottom: `1px solid ${c.border}` }}>
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                        {Object.entries(log.details as Record<string, unknown>).map(([k, v]) => (
                          <div key={k}>
                            <span className="text-[10px] uppercase font-medium" style={{ color: c.textMuted }}>{k}</span>
                            <p className="text-xs" style={{ color: c.textPrimary }}>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</p>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {logs.length === 0 && !loading && (
        <div className="text-center py-12">
          <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-50" style={{ color: c.textMuted }} />
          <p style={{ color: c.textMuted }}>Sin registros de auditoría</p>
          <p className="text-xs mt-1" style={{ color: c.textMuted }}>Los registros se generan automáticamente al realizar acciones</p>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="btn-secondary text-sm disabled:opacity-50"><ChevronLeft className="w-4 h-4" /></button>
          <span className="text-sm" style={{ color: c.textMuted }}>Página {page} de {totalPages} ({total} registros)</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="btn-secondary text-sm disabled:opacity-50"><ChevronRight className="w-4 h-4" /></button>
        </div>
      )}
    </div>
  );
}

function RouterHistoryTab({ c }: { c: any }) {
  const [entries, setEntries] = useState<RouterHistoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [routerFilter, setRouterFilter] = useState<number | ''>('');
  const [userFilter, setUserFilter] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filterOptions, setFilterOptions] = useState<{ routers: { id: number; name: string }[]; users: string[] }>({ routers: [], users: [] });
  const [stats, setStats] = useState<{ total: number; by_router: { router_name: string; count: number }[] } | null>(null);
  const limit = 30;

  const load = () => {
    setLoading(true);
    auditAPI.routerHistory({
      page, router_id: routerFilter !== '' ? routerFilter : undefined,
      by_user: userFilter || undefined, search: searchFilter || undefined,
      date_from: dateFrom || undefined, date_to: dateTo || undefined,
    }).then((data) => { setEntries(data.entries); setTotal(data.total); })
      .catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, routerFilter, userFilter]);
  useEffect(() => {
    Promise.all([auditAPI.routerHistoryFilters(), auditAPI.routerHistoryStats()]).then(([f, s]) => { setFilterOptions(f); setStats(s); }).catch(console.error);
  }, []);

  const totalPages = Math.ceil(total / limit);
  const activeFilters = [routerFilter !== '', userFilter, searchFilter, dateFrom, dateTo].filter(Boolean).length;
  const clearFilters = () => { setRouterFilter(''); setUserFilter(''); setSearchFilter(''); setDateFrom(''); setDateTo(''); setPage(1); };

  const exportCSV = () => {
    const header = 'Router,Fecha,Usuario,Acción,Comando (redo),Comando (undo),Origen\n';
    const rows = entries.map(e =>
      `"${e.router_name}","${e.ros_time}","${e.by_user}","${e.action}","${(e.redo || '').replace(/"/g, '""')}","${(e.undo || '').replace(/"/g, '""')}","${e.trace || ''}"`
    ).join('\n');
    const blob = new Blob(['\ufeff' + header + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `historial_routers_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const formatRedo = (s: string) => s.replace(/\r\n/g, '\n').trim();

  const actionIcon = (action: string) => {
    const lower = action.toLowerCase();
    if (lower.includes('added') || lower.includes('created') || lower.includes('enable')) return { color: c.green, label: 'Agregado' };
    if (lower.includes('removed') || lower.includes('deleted') || lower.includes('disable')) return { color: c.red, label: 'Eliminado' };
    if (lower.includes('changed') || lower.includes('set') || lower.includes('moved')) return { color: c.yellow, label: 'Modificado' };
    return { color: c.blue, label: action };
  };

  const sourceLabel = (trace: string) => {
    if (!trace) return 'desconocido';
    if (trace.includes('api:')) return 'API (MikroControl)';
    if (trace.includes('winbox')) return 'WinBox';
    if (trace.includes('web')) return 'WebFig';
    if (trace.includes('console')) return 'Console';
    if (trace.includes('ssh')) return 'SSH';
    return trace.split(':')[0];
  };

  return (
    <div className="space-y-4">
      {stats && (
        <div className="flex gap-3">
          <div className="card flex items-center gap-3 !p-3 shrink-0">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: c.accentLight }}>
              <Server className="w-4 h-4" style={{ color: c.accent }} />
            </div>
            <div>
              <p className="text-lg font-bold" style={{ color: c.textPrimary }}>{stats.total.toLocaleString()}</p>
              <p className="text-[10px]" style={{ color: c.textMuted }}>Cambios totales</p>
            </div>
          </div>
          <div className="card flex-1 !p-3 min-w-0 overflow-hidden">
            <p className="text-[10px] uppercase font-bold mb-2" style={{ color: c.textMuted }}>Cambios por router</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 max-h-20 overflow-y-auto">
              {stats.by_router.map(r => (
                <div key={r.router_name} className="flex items-center gap-1.5 text-xs shrink-0">
                  <Server className="w-3 h-3 shrink-0" style={{ color: c.blue }} />
                  <span className="truncate max-w-[140px]" style={{ color: c.textSecondary }}>{r.router_name}</span>
                  <span className="font-bold" style={{ color: c.textPrimary }}>{r.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="card !p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: c.textMuted }} />
            <input className="input pl-9 w-full text-sm" placeholder="Buscar en acciones, comandos..." value={searchFilter} onChange={e => setSearchFilter(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} />
          </div>
          <button onClick={() => setShowFilters(!showFilters)} className="btn-secondary text-sm">
            <Filter className="w-4 h-4 inline mr-1" />Filtros {activeFilters > 0 && <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold" style={{ background: c.accent, color: '#fff' }}>{activeFilters}</span>}
          </button>
          {activeFilters > 0 && <button onClick={clearFilters} className="text-xs flex items-center gap-1" style={{ color: c.textLink }}><X className="w-3 h-3" />Limpiar</button>}
          <button onClick={exportCSV} className="btn-secondary text-sm"><Download className="w-4 h-4 inline mr-1" />CSV</button>
        </div>
        {showFilters && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-3 pt-3" style={{ borderTop: `1px solid ${c.border}` }}>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Router</label>
              <select className="input w-full text-sm" value={routerFilter} onChange={e => { setRouterFilter(e.target.value ? Number(e.target.value) : ''); setPage(1); }}>
                <option value="">Todos</option>
                {filterOptions.routers.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Usuario en Router</label>
              <select className="input w-full text-sm" value={userFilter} onChange={e => { setUserFilter(e.target.value); setPage(1); }}>
                <option value="">Todos</option>
                {filterOptions.users.map(u => <option key={u} value={u}>{u}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Desde</label>
              <input type="datetime-local" className="input w-full text-sm" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(1); }} />
            </div>
            <div>
              <label className="text-[10px] font-medium mb-1 block uppercase" style={{ color: c.textMuted }}>Hasta</label>
              <input type="datetime-local" className="input w-full text-sm" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(1); }} />
            </div>
          </div>
        )}
      </div>

      <div className="space-y-2">
        {entries.map((entry) => {
          const ai = actionIcon(entry.action);
          const isExpanded = expandedId === entry.id;
          return (
            <div key={entry.id} className="card !p-0 overflow-hidden cursor-pointer hover:opacity-90 transition-opacity" onClick={() => setExpandedId(isExpanded ? null : entry.id)}>
              <div className="flex items-center gap-3 p-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${ai.color}20` }}>
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: ai.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium" style={{ color: c.textPrimary }}>{entry.action}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ background: `${ai.color}20`, color: ai.color }}>{ai.label}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-[11px]" style={{ color: c.textMuted }}>
                    <span className="flex items-center gap-1"><Server className="w-3 h-3" />{entry.router_name}</span>
                    <span>{entry.by_user}</span>
                    <span>{entry.ros_time}</span>
                    <span className="px-1.5 py-0.5 rounded" style={{ background: c.bgHover }}>{sourceLabel(entry.trace)}</span>
                  </div>
                </div>
                <div className="shrink-0">
                  {isExpanded ? <ChevronUp className="w-4 h-4" style={{ color: c.textMuted }} /> : <ChevronDown className="w-4 h-4" style={{ color: c.textMuted }} />}
                </div>
              </div>

              {isExpanded && (
                <div className="px-3 pb-3 pt-1" style={{ borderTop: `1px solid ${c.border}` }}>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div className="rounded-lg p-3" style={{ background: c.bgHover }}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="w-2 h-2 rounded-full" style={{ background: c.green }} />
                        <span className="text-[10px] uppercase font-bold" style={{ color: c.textMuted }}>Comando ejecutado (redo)</span>
                      </div>
                      <pre className="text-xs font-mono whitespace-pre-wrap break-all" style={{ color: c.textPrimary }}>{formatRedo(entry.redo)}</pre>
                    </div>
                    {entry.undo && (
                      <div className="rounded-lg p-3" style={{ background: c.bgHover }}>
                        <div className="flex items-center gap-2 mb-2">
                          <Undo2 className="w-3 h-3" style={{ color: c.yellow }} />
                          <span className="text-[10px] uppercase font-bold" style={{ color: c.textMuted }}>Deshacer (undo)</span>
                        </div>
                        <pre className="text-xs font-mono whitespace-pre-wrap break-all" style={{ color: c.textSecondary }}>{formatRedo(entry.undo)}</pre>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-[11px]" style={{ color: c.textMuted }}>
                    <span>Permisos: <span className="font-mono" style={{ color: c.textSecondary }}>{entry.policy}</span></span>
                    <span>Origen: <span style={{ color: c.textSecondary }}>{entry.trace}</span></span>
                    <span>Deshacer: <span style={{ color: entry.undoable === 'true' ? c.green : c.textMuted }}>{entry.undoable === 'true' ? 'Sí' : 'No'}</span></span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {entries.length === 0 && !loading && (
        <div className="text-center py-12">
          <Server className="w-12 h-12 mx-auto mb-3 opacity-50" style={{ color: c.textMuted }} />
          <p style={{ color: c.textMuted }}>Sin historial de cambios en routers</p>
          <p className="text-xs mt-1" style={{ color: c.textMuted }}>Los cambios se sincronizan cada 5 minutos desde /system/history/print</p>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="btn-secondary text-sm disabled:opacity-50"><ChevronLeft className="w-4 h-4" /></button>
          <span className="text-sm" style={{ color: c.textMuted }}>Página {page} de {totalPages} ({total} cambios)</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="btn-secondary text-sm disabled:opacity-50"><ChevronRight className="w-4 h-4" /></button>
        </div>
      )}
    </div>
  );
}

export default function AuditPage() {
  const [tab, setTab] = useState<'system' | 'router'>('system');
  const { c } = useTheme();

  const tabs = [
    { id: 'system' as const, label: 'Sistema MikroControl', icon: ClipboardList },
    { id: 'router' as const, label: 'Historial del Router', icon: Server },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Auditoría</h1>
      </div>

      <div className="flex gap-1 p-1 rounded-lg" style={{ background: c.bgHover }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all"
            style={tab === t.id ? { background: c.bgCard, color: c.textPrimary, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' } : { color: c.textMuted }}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>

      {tab === 'system' && <SystemAuditTab c={c} />}
      {tab === 'router' && <RouterHistoryTab c={c} />}
    </div>
  );
}

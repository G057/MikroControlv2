import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { routersAPI, groupsAPI, routerosAPI } from '../services/api';
import type { RouterDevice, RouterGroup } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Plus, Search, Wifi, WifiOff, MapPin, Server, Edit, Trash2, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';

export default function RoutersPage() {
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [groups, setGroups] = useState<RouterGroup[]>([]);
  const [search, setSearch] = useState('');
  const [filterGroup, setFilterGroup] = useState<number | ''>('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'online' | 'offline'>('all');
  const [showForm, setShowForm] = useState(false);
  const [editingRouter, setEditingRouter] = useState<RouterDevice | null>(null);
  const { hasPermission } = useAuth();
  const { c } = useTheme();

  const loadRouters = () => {
    routersAPI.list({
      search: search || undefined,
      group_id: filterGroup || undefined,
      is_online: filterStatus === 'online' ? true : filterStatus === 'offline' ? false : undefined,
    }).then(setRouters).catch(console.error);
  };

  useEffect(() => { loadRouters(); const iv = setInterval(loadRouters, 30000); return () => clearInterval(iv); }, [search, filterGroup, filterStatus]);
  useEffect(() => { groupsAPI.list().then(setGroups).catch(console.error); }, []);

  const handleCheck = async (id: number) => {
    try { await routersAPI.check(id); toast.success('Estado actualizado'); loadRouters(); }
    catch { toast.error('Error al verificar'); }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Eliminar router "${name}"?`)) return;
    try { await routersAPI.delete(id); toast.success('Router eliminado'); loadRouters(); }
    catch { toast.error('Error al eliminar'); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Routers</h1>
        {hasPermission("routers:edit") && (
          <button onClick={() => { setEditingRouter(null); setShowForm(true); }} className="btn-primary">
            <Plus className="w-4 h-4 inline mr-2" />Agregar Router
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: c.textMuted }} />
          <input className="input pl-10" placeholder="Buscar por nombre, hostname, IP, cliente..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="input w-auto" value={filterGroup} onChange={e => setFilterGroup(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Todos los grupos</option>
          {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>
        <select className="input w-auto" value={filterStatus} onChange={e => setFilterStatus(e.target.value as any)}>
          <option value="all">Todos</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {routers.map(r => (
          <div key={r.id} className="card transition-colors">
            <div className="flex items-start justify-between mb-3">
              <Link to={`/routers/${r.id}`} className="flex items-center gap-3 group">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: r.is_online ? c.greenBg : c.redBg }}>
                  {r.is_online ? <Wifi className="w-5 h-5" style={{ color: c.green }} /> : <WifiOff className="w-5 h-5" style={{ color: c.red }} />}
                </div>
                <div>
                  <h3 className="font-semibold group-hover:opacity-80 transition-opacity" style={{ color: c.textLink }}>{r.name}</h3>
                  <p className="text-xs" style={{ color: c.textMuted }}>{r.ip_address}</p>
                </div>
              </Link>
              <div className="flex gap-1">
                {hasPermission("routers:terminal") && (
                  <button onClick={() => handleCheck(r.id)} className="p-1.5 rounded" style={{ color: c.textMuted }} title="Verificar estado">
                    <RefreshCw className="w-4 h-4" />
                  </button>
                )}
                {hasPermission("routers:edit") && (
                  <button onClick={() => { setEditingRouter(r); setShowForm(true); }} className="p-1.5 rounded" style={{ color: c.textMuted }} title="Editar">
                    <Edit className="w-4 h-4" />
                  </button>
                )}
                {hasPermission("routers:edit") && (
                  <button onClick={() => handleDelete(r.id, r.name)} className="p-1.5 rounded" style={{ color: c.red }} title="Eliminar">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
            <div className="space-y-2 text-sm">
              {r.model && <div className="flex justify-between"><span style={{ color: c.textMuted }}>Modelo</span><span style={{ color: c.textSecondary }}>{r.model}</span></div>}
              {r.routeros_version && <div className="flex justify-between"><span style={{ color: c.textMuted }}>RouterOS</span><span style={{ color: c.textSecondary }}>{r.routeros_version}</span></div>}
              {r.cpu_usage !== null && (
                <div className="flex justify-between items-center">
                  <span style={{ color: c.textMuted }}>CPU</span>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: c.border }}>
                      <div className="h-full rounded-full" style={{ width: `${r.cpu_usage}%`, background: r.cpu_usage > 80 ? c.red : r.cpu_usage > 50 ? c.yellow : c.green }} />
                    </div>
                    <span className="w-10 text-right" style={{ color: c.textSecondary }}>{r.cpu_usage}%</span>
                  </div>
                </div>
              )}
              {r.client_name && <div className="flex justify-between"><span style={{ color: c.textMuted }}>Cliente</span><span style={{ color: c.textSecondary }}>{r.client_name}</span></div>}
              {r.city && <div className="flex items-center gap-1" style={{ color: c.textMuted }}><MapPin className="w-3 h-3" />{r.city}</div>}
            </div>
          </div>
        ))}
      </div>

      {routers.length === 0 && (
        <div className="text-center py-12">
          <Server className="w-12 h-12 mx-auto mb-3" style={{ color: c.textMuted }} />
          <p style={{ color: c.textMuted }}>No se encontraron routers</p>
        </div>
      )}

      {showForm && (
        <RouterForm router={editingRouter} groups={groups} c={c}
          onClose={() => { setShowForm(false); setEditingRouter(null); }}
          onSaved={() => { setShowForm(false); setEditingRouter(null); loadRouters(); }}
        />
      )}
    </div>
  );
}

function RouterForm({ router, groups, onClose, onSaved, c }: {
  router: RouterDevice | null; groups: RouterGroup[]; onClose: () => void; onSaved: () => void; c: any;
}) {
  const [form, setForm] = useState({
    name: router?.name || '', hostname: router?.hostname || '',
    ip_address: router?.ip_address || router?.hostname || '', model: router?.model || '',
    api_username: router?.api_username || 'admin', api_password: '',
    access_method: router?.access_method || 'ip_public', access_port: router?.access_port || 8728,
    use_ssl: router?.use_ssl || false, group_id: router?.group_id || '',
    client_name: router?.client_name || '', city: router?.city || '',
    address: router?.address || '', notes: router?.notes || '',
  });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const MASK = '••••••';
  const ipMasked = form.ip_address === MASK;
  const modelMasked = form.model === MASK;

  const handleTest = async () => {
    setTesting(true); setTestResult(null);
    try {
      const result = await routerosAPI.testConnection({ hostname: form.ip_address || form.hostname, port: form.access_port, username: form.api_username, password: form.api_password || '', use_ssl: form.use_ssl });
      setTestResult(result.success ? { ok: true, msg: `Conectado: ${result.identity} (RouterOS ${result.version})` } : { ok: false, msg: result.error || 'Error al conectar' });
    } catch (err: any) { setTestResult({ ok: false, msg: err.message || 'Error de red' }); }
    finally { setTesting(false); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const data: any = { ...form, group_id: form.group_id || null };
    if (!data.api_password) delete data.api_password;
    ['ip_address', 'hostname', 'model', 'mac_address', 'serial_number', 'identity'].forEach(f => {
      if (data[f] === MASK) delete data[f];
    });
    try {
      if (router) { await routersAPI.update(router.id, data); toast.success('Router actualizado'); }
      else { await routersAPI.create(data); toast.success('Router creado'); }
      onSaved();
    } catch (err: any) { toast.error(err.message); }
  };

  const Label = ({ children }: { children: React.ReactNode }) => <label className="block text-sm font-medium mb-1" style={{ color: c.textSecondary }}>{children}</label>;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: c.bgOverlay }} onClick={onClose}>
      <div className="rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto" style={{ background: c.bgCard, border: `1px solid ${c.border}` }} onClick={e => e.stopPropagation()}>
        <div className="p-6" style={{ borderBottom: `1px solid ${c.border}` }}>
          <h2 className="text-lg font-semibold" style={{ color: c.textPrimary }}>{router ? 'Editar Router' : 'Agregar Router'}</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><Label>Nombre *</Label><input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></div>
            <div><Label>Hostname / IP *</Label><input className="input font-mono text-sm" placeholder="mi-router.ddns.net o 192.168.1.1" value={form.ip_address} onChange={e => setForm({ ...form, ip_address: e.target.value })} required={!ipMasked} readOnly={ipMasked} title={ipMasked ? 'Sin permiso para ver/editar este dato' : undefined} />{ipMasked && <p className="text-xs mt-1" style={{ color: c.textMuted }}>Oculto (sin permiso de datos técnicos)</p>}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><Label>Modelo</Label><input className="input" value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} placeholder="RB750Gr3, hEX S..." readOnly={modelMasked} title={modelMasked ? 'Sin permiso para ver/editar este dato' : undefined} /></div>
            <div><Label>Grupo</Label><select className="input" value={form.group_id} onChange={e => setForm({ ...form, group_id: e.target.value })}><option value="">Sin grupo</option>{groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
          </div>
          <div style={{ borderTop: `1px solid ${c.border}` }} className="pt-4">
            <p className="text-xs mb-3 uppercase tracking-wide" style={{ color: c.textMuted }}>Conexión API</p>
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2"><Label>Puerto API</Label><input className="input font-mono" type="number" value={form.access_port} onChange={e => setForm({ ...form, access_port: Number(e.target.value) })} /><p className="text-xs mt-1" style={{ color: c.textMuted }}>Estándar: 8728 (API) o 8729 (API-SSL)</p></div>
              <div>
                <Label>SSL</Label>
                <button type="button" onClick={() => setForm({ ...form, use_ssl: !form.use_ssl })} className="w-full py-2 rounded-lg text-sm font-medium transition-colors"
                  style={{ background: form.use_ssl ? c.greenBg : c.bgHover, color: form.use_ssl ? c.green : c.textSecondary, border: `1px solid ${form.use_ssl ? c.green : c.border}` }}>
                  {form.use_ssl ? 'API-SSL ON' : 'API SSL OFF'}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-3">
              <div><Label>Usuario API</Label><input className="input" value={form.api_username} onChange={e => setForm({ ...form, api_username: e.target.value })} /></div>
              <div><Label>Contraseña API</Label><input className="input" type="password" value={form.api_password} onChange={e => setForm({ ...form, api_password: e.target.value })} placeholder={router ? '(sin cambios)' : ''} /></div>
            </div>
          </div>
          <div className="rounded-lg p-3" style={{ background: c.bgPage }}>
            <button type="button" onClick={handleTest} disabled={testing || !form.ip_address || ipMasked} className="btn-secondary text-sm w-full">{testing ? 'Probando conexión...' : 'Probar conexión al router'}</button>
            {testResult && <div className="mt-2 text-sm px-3 py-2 rounded" style={{ background: testResult.ok ? c.greenBg : c.redBg, color: testResult.ok ? c.green : c.red }}>{testResult.msg}</div>}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><Label>Cliente</Label><input className="input" value={form.client_name} onChange={e => setForm({ ...form, client_name: e.target.value })} /></div>
            <div><Label>Ciudad</Label><input className="input" value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} /></div>
          </div>
          <div><Label>Dirección</Label><input className="input" value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} /></div>
          <div><Label>Notas</Label><textarea className="input" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1">{router ? 'Guardar Cambios' : 'Crear Router'}</button>
            <button type="button" onClick={onClose} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}

import { useState, useEffect, useMemo } from 'react';
import { rolesAPI, eventsAPI, groupsAPI, routersAPI, type RoleItem, type PermissionGroup } from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import { Plus, Trash2, Edit, Shield, Check, X, Users as UsersIcon } from 'lucide-react';
import toast from 'react-hot-toast';

type PermInfo = { key: string; label: string; description: string };

const CFG_FEATURES = ['addresses', 'dhcp', 'dns', 'routes', 'firewall', 'nat', 'wireguard'];
const FEATURE_LABEL: Record<string, string> = {
  addresses: 'Direcciones IP', dhcp: 'DHCP', dns: 'DNS', routes: 'Rutas',
  firewall: 'Firewall', nat: 'NAT', wireguard: 'WireGuard',
};

function PermRow({ perm, checked, onToggle, compact }: { perm: PermInfo; checked: boolean; onToggle: (k: string) => void; compact?: boolean }) {
  const { c } = useTheme();
  return (
    <button type="button" onClick={() => onToggle(perm.key)}
      className="w-full flex items-center gap-3 text-left px-2 py-1.5 rounded transition-colors"
      style={{ background: checked ? c.greenBg : 'transparent' }}>
      <span className="w-4 h-4 rounded flex items-center justify-center shrink-0"
        style={{ border: `1px solid ${checked ? c.green : c.border}`, background: checked ? c.green : 'transparent' }}>
        {checked && <Check className="w-3 h-3 text-white" />}
      </span>
      <span className="flex-1 min-w-0">
        <span className="block text-sm" style={{ color: c.textPrimary }}>{perm.label}</span>
        {!compact && <span className="block text-[10px] truncate" style={{ color: c.textMuted }}>{perm.description}</span>}
      </span>
      {!compact && <span className="text-[10px] font-mono shrink-0" style={{ color: c.textMuted }}>{perm.key}</span>}
    </button>
  );
}

function PermCell({ perm, checked, onToggle }: { perm: PermInfo; checked: boolean; onToggle: (k: string) => void }) {
  const { c } = useTheme();
  return (
    <button type="button" onClick={() => onToggle(perm.key)} title={perm.label}
      className="inline-flex w-7 h-7 items-center justify-center rounded transition-colors"
      style={{ background: checked ? c.green : 'transparent', border: `1px solid ${checked ? c.green : c.border}` }}>
      {checked && <Check className="w-4 h-4 text-white" />}
    </button>
  );
}

function IdAssignChips({ options, value, onChange, c, emptyLabel }: {
  options: { id: number; label: string }[];
  value: number[];
  onChange: (v: number[]) => void;
  c: any;
  emptyLabel?: string;
}) {
  const add = (id: number) => { if (!value.includes(id)) onChange([...value, id]); };
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {value.length === 0 && (
        <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: c.bgHover, color: c.textMuted }}>{emptyLabel || 'Ninguno seleccionado'}</span>
      )}
      {value.map(id => {
        const opt = options.find(o => o.id === id);
        const label = opt ? opt.label : `#${id}`;
        return (
          <button key={id} type="button" onClick={() => onChange(value.filter(x => x !== id))}
            className="text-[10px] px-1.5 py-0.5 rounded font-medium flex items-center gap-1" style={{ background: c.accent, color: '#fff' }} title="Quitar">
            {label} ✕
          </button>
        );
      })}
      <select value="" onChange={e => { if (e.target.value) add(Number(e.target.value)); e.target.value = ''; }}
        className="text-[11px] rounded px-1 py-0.5" style={{ background: c.bgHover, color: c.textMuted, border: `1px solid ${c.border}` }}>
        <option value="">+ {emptyLabel ? 'agregar' : 'agregar'}…</option>
        {options.filter(o => !value.includes(o.id)).map(o => (
          <option key={o.id} value={o.id}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

export default function RolesPage() {
  const { c } = useTheme();
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [catalog, setCatalog] = useState<PermissionGroup[]>([]);
  const [eventCategories, setEventCategories] = useState<{ key: string; label: string }[]>([]);
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [routers, setRouters] = useState<{ id: number; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editRole, setEditRole] = useState<RoleItem | null>(null);
  const [form, setForm] = useState({ name: '', description: '', permissions: [] as string[], event_categories: [] as string[], router_scope: 'all' as 'all' | 'selected', router_ids: [] as number[], router_group_ids: [] as number[] });

  const { viewMaster, viewFeatures, cfgMatrix, gestion, otherGroups } = useMemo(() => {
    const others: PermissionGroup[] = [];
    const vm: PermInfo[] = [], vf: PermInfo[] = [], gst: PermInfo[] = [];
    const cmat: Record<string, Record<string, PermInfo>> = {};
    for (const grp of catalog) {
      if (grp.group === 'Routers' || grp.group === 'Vista Router' || grp.group === 'Config. Router') continue;
      others.push(grp);
    }
    for (const grp of catalog) {
      for (const p of grp.permissions) {
        if (p.key.startsWith('routers:cfg_')) {
          const parts = p.key.split('_');
          const feat = parts[1]; const op = parts[2];
          (cmat[feat] = cmat[feat] || {})[op] = p;
        } else if (p.key === 'routers:details') {
          vm.push(p);
        } else if (p.key.startsWith('routers:view_')) {
          vf.push(p);
        } else if (p.key.startsWith('routers:')) {
          gst.push(p);
        }
      }
    }
    return { viewMaster: vm, viewFeatures: vf, cfgMatrix: cmat, gestion: gst, otherGroups: others };
  }, [catalog]);

  const load = () => {
    setLoading(true);
    Promise.all([rolesAPI.list(), rolesAPI.catalog(), eventsAPI.categories(), groupsAPI.list(), routersAPI.list()])
      .then(([r, cat, cats, grp, rtr]) => { setRoles(r); setCatalog(cat.groups); setEventCategories(cats); setGroups(grp); setRouters(rtr); })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditRole(null);
    setForm({ name: '', description: '', permissions: [], event_categories: [], router_scope: 'all', router_ids: [], router_group_ids: [] });
    setShowForm(true);
  };

  const openEdit = (role: RoleItem) => {
    if (role.is_system) {
      toast.error('Los roles de sistema no se pueden editar');
      return;
    }
    setEditRole(role);
    setForm({ name: role.name, description: role.description, permissions: [...role.permissions], event_categories: [...role.event_categories], router_scope: role.router_scope || 'all', router_ids: [...role.router_ids], router_group_ids: [...role.router_group_ids] });
    setShowForm(true);
  };

  const toggleEventCat = (key: string) => {
    setForm(f => ({
      ...f,
      event_categories: f.event_categories.includes(key)
        ? f.event_categories.filter(c => c !== key)
        : [...f.event_categories.filter(c => c !== '*'), key],
    }));
  };

  const toggleAllEvents = () => {
    setForm(f => ({
      ...f,
      event_categories: f.event_categories.includes('*') ? [] : ['*'],
    }));
  };

  const togglePerm = (key: string) => {
    setForm(f => ({
      ...f,
      permissions: f.permissions.includes(key)
        ? f.permissions.filter(p => p !== key)
        : [...f.permissions, key],
    }));
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) { toast.error('El nombre es requerido'); return; }
    try {
      if (editRole) {
        await rolesAPI.update(editRole.id, { description: form.description, permissions: form.permissions, event_categories: form.event_categories, router_scope: form.router_scope, router_ids: form.router_ids, router_group_ids: form.router_group_ids });
        toast.success('Rol actualizado');
      } else {
        await rolesAPI.create({ name: form.name.trim().toLowerCase(), description: form.description, permissions: form.permissions, event_categories: form.event_categories, router_scope: form.router_scope, router_ids: form.router_ids, router_group_ids: form.router_group_ids });
        toast.success('Rol creado');
      }
      setShowForm(false);
      load();
    } catch (e: any) { toast.error(e.message); }
  };

  const handleDelete = async (role: RoleItem) => {
    if (role.is_system) { toast.error('No se puede eliminar un rol de sistema'); return; }
    if (!confirm(`¿Eliminar el rol "${role.name}"?`)) return;
    try { await rolesAPI.remove(role.id); toast.success('Rol eliminado'); load(); }
    catch (e: any) { toast.error(e.message); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <Shield className="w-7 h-7" style={{ color: c.accent }} />
          <div>
            <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Roles de Usuario</h1>
            <p className="text-sm" style={{ color: c.textMuted }}>Creá roles y asignales funciones del sistema</p>
          </div>
        </div>
        <button onClick={openCreate} className="btn-primary">
          <Plus className="w-4 h-4 inline mr-2" />Nuevo Rol
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {roles.map(r => (
          <div key={r.id} className="card">
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold capitalize" style={{ color: c.textLink }}>{r.name}</h3>
                  {r.is_system && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold" style={{ background: c.purpleBg, color: c.purple }}>Sistema</span>
                  )}
                </div>
                <p className="text-xs mt-1" style={{ color: c.textMuted }}>{r.description}</p>
              </div>
              <div className="flex gap-1">
                <button onClick={() => openEdit(r)} disabled={r.is_system} className="p-1.5 rounded disabled:opacity-30" style={{ color: c.textMuted }} title="Editar">
                  <Edit className="w-4 h-4" />
                </button>
                <button onClick={() => handleDelete(r)} disabled={r.is_system} className="p-1.5 rounded disabled:opacity-30" style={{ color: c.red }} title="Eliminar">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-xs mb-3" style={{ color: c.textSecondary }}>
              <UsersIcon className="w-3 h-3" style={{ color: c.textMuted }} />
              {r.user_count} usuario(s)
            </div>
            <div className="flex flex-wrap gap-1">
              {r.permissions.length === 0 && <span className="text-xs" style={{ color: c.textMuted }}>Sin permisos</span>}
              {r.permissions.slice(0, 6).map(p => (
                <span key={p} className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: c.greenBg, color: c.green }}>{p}</span>
              ))}
              {r.permissions.length > 6 && <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: c.bgHover, color: c.textMuted }}>+{r.permissions.length - 6}</span>}
            </div>
          </div>
        ))}
      </div>

      {loading && roles.length === 0 && (
        <div className="text-center py-12" style={{ color: c.textMuted }}>Cargando roles...</div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: c.bgOverlay }} onClick={() => setShowForm(false)}>
          <div className="rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" style={{ background: c.bgCard, border: `1px solid ${c.border}` }} onClick={e => e.stopPropagation()}>
            <div className="p-6 flex items-center justify-between" style={{ borderBottom: `1px solid ${c.border}` }}>
              <h2 className="text-lg font-semibold" style={{ color: c.textPrimary }}>{editRole ? 'Editar Rol' : 'Nuevo Rol'}</h2>
              <button onClick={() => setShowForm(false)} style={{ color: c.textMuted }}><X className="w-5 h-5" /></button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: c.textSecondary }}>Nombre *</label>
                  <input className="input" value={form.name} disabled={!!editRole}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    placeholder="ej: soporte_l1" />
                  {editRole && <p className="text-xs mt-1" style={{ color: c.textMuted }}>El nombre no se puede cambiar</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: c.textSecondary }}>Descripción</label>
                  <input className="input" value={form.description}
                    onChange={e => setForm({ ...form, description: e.target.value })} />
                </div>
              </div>

              <div>
                <p className="text-sm font-medium mb-1" style={{ color: c.textSecondary }}>Eventos visibles (por categoría)</p>
                <p className="text-[11px] mb-2" style={{ color: c.textMuted }}>
                  Marcá qué categorías de eventos de router puede ver este rol. Si no marcás ninguna, no verá eventos de routers. "Todos los eventos" equivale a acceso total (como admin).
                </p>
                <div className="flex flex-wrap gap-1.5">
                  <button type="button" onClick={toggleAllEvents}
                    className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
                    style={{ background: form.event_categories.includes('*') ? c.accent : c.bgPage, color: form.event_categories.includes('*') ? '#fff' : c.textMuted, border: `1px solid ${form.event_categories.includes('*') ? c.accent : c.border}` }}>
                    {form.event_categories.includes('*') ? '✓ ' : ''}Todos los eventos
                  </button>
                  {eventCategories.length === 0 && <span className="text-xs" style={{ color: c.textMuted }}>Cargando categorías...</span>}
                  {eventCategories.map(cat => {
                    const on = form.event_categories.includes(cat.key);
                    return (
                      <button key={cat.key} type="button" onClick={() => toggleEventCat(cat.key)}
                        className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
                        style={{ background: on ? c.greenBg : c.bgPage, color: on ? c.green : c.textMuted, border: `1px solid ${on ? c.green : c.border}` }}>
                        {on ? '✓ ' : ''}{cat.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <p className="text-sm font-medium mb-1" style={{ color: c.textSecondary }}>Routers visibles</p>
                <p className="text-[11px] mb-2" style={{ color: c.textMuted }}>
                  Elegí qué routers puede ver este rol. "Todos los routers" = acceso total (como admin). Si seleccionás "Seleccionados" y no marcás nada, el rol no verá ningún router.
                </p>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  <button type="button" onClick={() => setForm(f => ({ ...f, router_scope: 'all' }))}
                    className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
                    style={{ background: form.router_scope === 'all' ? c.accent : c.bgPage, color: form.router_scope === 'all' ? '#fff' : c.textMuted, border: `1px solid ${form.router_scope === 'all' ? c.accent : c.border}` }}>
                    {form.router_scope === 'all' ? '✓ ' : ''}Todos los routers
                  </button>
                  <button type="button" onClick={() => setForm(f => ({ ...f, router_scope: 'selected' }))}
                    className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
                    style={{ background: form.router_scope === 'selected' ? c.accent : c.bgPage, color: form.router_scope === 'selected' ? '#fff' : c.textMuted, border: `1px solid ${form.router_scope === 'selected' ? c.accent : c.border}` }}>
                    {form.router_scope === 'selected' ? '✓ ' : ''}Seleccionados
                  </button>
                </div>
                {form.router_scope === 'selected' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-[11px] uppercase font-medium mb-1" style={{ color: c.textMuted }}>Grupos</label>
                      <IdAssignChips options={groups.map(g => ({ id: g.id, label: g.name }))} value={form.router_group_ids} onChange={ids => setForm(f => ({ ...f, router_group_ids: ids }))} c={c} emptyLabel="Sin grupos" />
                    </div>
                    <div>
                      <label className="block text-[11px] uppercase font-medium mb-1" style={{ color: c.textMuted }}>Routers específicos</label>
                      <IdAssignChips options={routers.map(r => ({ id: r.id, label: r.name }))} value={form.router_ids} onChange={ids => setForm(f => ({ ...f, router_ids: ids }))} c={c} emptyLabel="Sin routers" />
                    </div>
                  </div>
                )}
              </div>

              <div>
                <p className="text-sm font-medium mb-2" style={{ color: c.textSecondary }}>
                  Funciones del sistema ({form.permissions.length} seleccionadas)
                </p>
                <div className="space-y-4">
                  {/* VER · Lectura */}
                  <div className="rounded-lg p-3" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
                    <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: c.blue }}>Ver · Lectura de Routers</p>
                    <p className="text-[11px] mb-2" style={{ color: c.textMuted }}>
                      "Ver Routers (todo)" habilita todas las vistas. Las casillas por sección limitan qué pestañas puede abrir el usuario.
                    </p>
                    <div className="space-y-1.5">
                      {viewMaster.map(p => (
                        <PermRow key={p.key} perm={p} checked={form.permissions.includes(p.key)} onToggle={togglePerm} />
                      ))}
                    </div>
                    <p className="text-[11px] font-medium mt-3 mb-1" style={{ color: c.textSecondary }}>Vistas por sección:</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {viewFeatures.map(p => (
                        <PermRow key={p.key} perm={p} compact checked={form.permissions.includes(p.key)} onToggle={togglePerm} />
                      ))}
                    </div>
                  </div>

                  {/* EDITAR · Configuración (matriz) */}
                  <div className="rounded-lg p-3" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
                    <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: '#D97706' }}>Editar · Configuración de Routers</p>
                    <p className="text-[11px] mb-2" style={{ color: c.textMuted }}>
                      Permisos por sección y operación. Una sección es editable solo si además tiene permiso de vista correspondiente.
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr style={{ color: c.textMuted }}>
                            <th className="text-left font-medium py-1 pr-2">Sección</th>
                            <th className="text-center font-medium py-1 px-2">Crear</th>
                            <th className="text-center font-medium py-1 px-2">Editar</th>
                            <th className="text-center font-medium py-1 px-2">Eliminar</th>
                          </tr>
                        </thead>
                        <tbody>
                          {CFG_FEATURES.map(feat => (
                            <tr key={feat} style={{ borderTop: `1px solid ${c.border}` }}>
                              <td className="py-1.5 pr-2" style={{ color: c.textPrimary }}>{FEATURE_LABEL[feat]}</td>
                              {['create', 'edit', 'delete'].map(op => {
                                const p = cfgMatrix[feat]?.[op];
                                return (
                                  <td key={op} className="text-center px-2">
                                    {p
                                      ? <PermCell perm={p} checked={form.permissions.includes(p.key)} onToggle={togglePerm} />
                                      : <span style={{ color: c.textMuted }}>—</span>}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* GESTIÓN */}
                  {gestion.length > 0 && (
                    <div className="rounded-lg p-3" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
                      <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: c.textMuted }}>Gestión de Routers</p>
                      <div className="space-y-1.5">
                        {gestion.map(p => (
                          <PermRow key={p.key} perm={p} checked={form.permissions.includes(p.key)} onToggle={togglePerm} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Otros grupos */}
                  {otherGroups.map(group => (
                    <div key={group.group} className="rounded-lg p-3" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
                      <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: c.textMuted }}>{group.group}</p>
                      <div className="space-y-1.5">
                        {group.permissions.map(perm => (
                          <PermRow key={perm.key} perm={perm} checked={form.permissions.includes(perm.key)} onToggle={togglePerm} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-3 p-6" style={{ borderTop: `1px solid ${c.border}` }}>
              <button onClick={handleSubmit} className="btn-primary flex-1">Guardar</button>
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

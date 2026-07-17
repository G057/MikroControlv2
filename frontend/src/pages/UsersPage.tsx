import { useState, useEffect } from 'react';
import { usersAPI, rolesAPI, type RoleItem } from '../services/api';
import type { User } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Plus, Edit, Trash2, Shield } from 'lucide-react';
import toast from 'react-hot-toast';

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrador', supervisor: 'Supervisor', tecnico_n2: 'Técnico N2', tecnico_n1: 'Técnico N1', auditor: 'Auditor',
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const { hasPermission } = useAuth();
  const { c } = useTheme();

  const loadUsers = () => usersAPI.list().then(setUsers).catch(console.error);
  useEffect(() => { loadUsers(); }, []);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Eliminar usuario "${name}"?`)) return;
    try { await usersAPI.delete(id); toast.success('Usuario eliminado'); loadUsers(); }
    catch (err: any) { toast.error(err.message); }
  };

  const roleColor = (role: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
      admin: { bg: c.redBg, text: c.red }, supervisor: { bg: c.yellowBg, text: c.yellow },
      tecnico_n2: { bg: c.blueBg, text: c.blue }, tecnico_n1: { bg: c.greenBg, text: c.green },
      auditor: { bg: c.bgHover, text: c.textMuted },
    };
    return colors[role] || colors.auditor;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Usuarios</h1>
        {hasPermission("users:edit") && (
          <button onClick={() => { setEditingUser(null); setShowForm(true); }} className="btn-primary">
            <Plus className="w-4 h-4 inline mr-2" />Agregar Usuario
          </button>
        )}
      </div>

      <div className="space-y-3">
        {users.map((u) => (
          <div key={u.id} className="card flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: c.bgHover }}>
                <Shield className="w-5 h-5" style={{ color: c.textMuted }} />
              </div>
              <div>
                <p className="font-medium" style={{ color: c.textPrimary }}>{u.full_name}</p>
                <p className="text-sm" style={{ color: c.textMuted }}>@{u.username} - {u.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="px-3 py-1 rounded-full text-xs font-medium" style={{ background: roleColor(u.role).bg, color: roleColor(u.role).text }}>
                {ROLE_LABELS[u.role] || u.role}
              </span>
              <span className="w-2 h-2 rounded-full" style={{ background: u.is_active ? c.green : c.red }} />
              {hasPermission("users:edit") && (
                <div className="flex gap-1">
                  <button onClick={() => { setEditingUser(u); setShowForm(true); }} className="p-1.5 rounded" style={{ color: c.textMuted }} title="Editar">
                    <Edit className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDelete(u.id, u.full_name)} className="p-1.5 rounded" style={{ color: c.red }} title="Eliminar">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {showForm && <UserForm user={editingUser} c={c} onClose={() => { setShowForm(false); setEditingUser(null); }} onSaved={() => { setShowForm(false); setEditingUser(null); loadUsers(); }} />}
    </div>
  );
}

function UserForm({ user, onClose, onSaved, c }: { user: User | null; onClose: () => void; onSaved: () => void; c: any }) {
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [form, setForm] = useState({
    username: user?.username || '', email: user?.email || '', full_name: user?.full_name || '',
    password: '', role: user?.role || 'tecnico_n1', is_active: user?.is_active ?? true,
    session_timeout_minutes: user?.session_timeout_minutes ?? null,
  });

  useEffect(() => {
    rolesAPI.list().then(r => {
      setRoles(r);
      if (!form.role || !r.find(x => x.name === form.role)) {
        const first = r.find(x => !x.is_system);
        setForm(f => ({ ...f, role: first ? first.name : 'tecnico_n1' }));
      }
    }).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (user) { const data: any = { ...form }; if (!data.password) delete data.password; await usersAPI.update(user.id, data); toast.success('Usuario actualizado'); }
      else { await usersAPI.create(form); toast.success('Usuario creado'); }
      onSaved();
    } catch (err: any) { toast.error(err.message); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: c.bgOverlay }} onClick={onClose}>
      <div className="rounded-xl w-full max-w-md" style={{ background: c.bgCard, border: `1px solid ${c.border}` }} onClick={e => e.stopPropagation()}>
        <div className="p-6" style={{ borderBottom: `1px solid ${c.border}` }}>
          <h2 className="text-lg font-semibold" style={{ color: c.textPrimary }}>{user ? 'Editar Usuario' : 'Agregar Usuario'}</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Nombre completo *</label><input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Usuario *</label><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Email *</label><input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Contraseña {user ? '(vacía = sin cambio)' : '*'}</label><input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required={!user} /></div>
          <div>
            <label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Rol *</label>
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {roles.map(r => <option key={r.name} value={r.name}>{r.name}{r.is_system ? ' (sistema)' : ''}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="rounded" />
            <label className="text-sm" style={{ color: c.textSecondary }}>Activo</label>
          </div>
          <div className="space-y-2">
            <label className="block text-sm" style={{ color: c.textSecondary }}>Duración de sesión (minutos)</label>
            <input className="input" type="number" min="1" placeholder="Predeterminada del sistema" disabled={form.session_timeout_minutes === 0}
              value={form.session_timeout_minutes ?? ''}
              onChange={(e) => setForm({ ...form, session_timeout_minutes: e.target.value ? Number(e.target.value) : null })} />
            <label className="flex items-center gap-2 text-sm" style={{ color: c.textSecondary }}>
              <input type="checkbox" checked={form.session_timeout_minutes === 0}
                onChange={(e) => setForm({ ...form, session_timeout_minutes: e.target.checked ? 0 : null })} className="rounded" />
              Sin vencimiento (pantalla de monitoreo 24/7)
            </label>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1">{user ? 'Guardar' : 'Crear'}</button>
            <button type="button" onClick={onClose} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}

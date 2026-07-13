import { useState, useEffect } from 'react';
import { groupsAPI } from '../services/api';
import type { RouterGroup } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Plus, Edit, Trash2, Network } from 'lucide-react';
import toast from 'react-hot-toast';

export default function GroupsPage() {
  const [groups, setGroups] = useState<RouterGroup[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<RouterGroup | null>(null);
  const { hasPermission } = useAuth();
  const { c } = useTheme();

  const load = () => groupsAPI.list().then(setGroups).catch(console.error);
  useEffect(() => { load(); }, []);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Eliminar grupo "${name}"?`)) return;
    try { await groupsAPI.delete(id); toast.success('Grupo eliminado'); load(); }
    catch (err: any) { toast.error(err.message); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Grupos</h1>
        {hasPermission("groups:edit") && (
          <button onClick={() => { setEditing(null); setShowForm(true); }} className="btn-primary">
            <Plus className="w-4 h-4 inline mr-2" />Agregar Grupo
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {groups.map((g) => (
          <div key={g.id} className="card">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded" style={{ backgroundColor: g.color }} />
                <h3 className="font-semibold" style={{ color: c.textPrimary }}>{g.name}</h3>
              </div>
              {hasPermission("groups:edit") && (
                <div className="flex gap-1">
                  <button onClick={() => { setEditing(g); setShowForm(true); }} className="p-1.5 rounded" style={{ color: c.textMuted }} title="Editar"><Edit className="w-4 h-4" /></button>
                  {hasPermission("groups:edit") && <button onClick={() => handleDelete(g.id, g.name)} className="p-1.5 rounded" style={{ color: c.red }} title="Eliminar"><Trash2 className="w-4 h-4" /></button>}
                </div>
              )}
            </div>
            {g.description && <p className="text-sm" style={{ color: c.textMuted }}>{g.description}</p>}
          </div>
        ))}
      </div>

      {groups.length === 0 && (
        <div className="text-center py-12">
          <Network className="w-12 h-12 mx-auto mb-3 opacity-50" style={{ color: c.textMuted }} />
          <p style={{ color: c.textMuted }}>Sin grupos creados</p>
        </div>
      )}

      {showForm && <GroupForm group={editing} c={c} onClose={() => { setShowForm(false); setEditing(null); }} onSaved={() => { setShowForm(false); setEditing(null); load(); }} />}
    </div>
  );
}

function GroupForm({ group, onClose, onSaved, c }: { group: RouterGroup | null; onClose: () => void; onSaved: () => void; c: any }) {
  const [form, setForm] = useState({ name: group?.name || '', description: group?.description || '', color: group?.color || '#3B82F6' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (group) { await groupsAPI.update(group.id, form); toast.success('Grupo actualizado'); }
      else { await groupsAPI.create(form); toast.success('Grupo creado'); }
      onSaved();
    } catch (err: any) { toast.error(err.message); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: c.bgOverlay }} onClick={onClose}>
      <div className="rounded-xl w-full max-w-md" style={{ background: c.bgCard, border: `1px solid ${c.border}` }} onClick={e => e.stopPropagation()}>
        <div className="p-6" style={{ borderBottom: `1px solid ${c.border}` }}>
          <h2 className="text-lg font-semibold" style={{ color: c.textPrimary }}>{group ? 'Editar Grupo' : 'Agregar Grupo'}</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Nombre *</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Descripción</label><textarea className="input" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Color</label><input type="color" className="w-12 h-10 rounded cursor-pointer" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} /></div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1">{group ? 'Guardar' : 'Crear'}</button>
            <button type="button" onClick={onClose} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}

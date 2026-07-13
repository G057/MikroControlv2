import { useState, useEffect } from 'react';
import { inventoryAPI } from '../services/api';
import type { InventoryItem } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Plus, Edit, Trash2, Package, Search } from 'lucide-react';
import toast from 'react-hot-toast';

const TYPE_LABELS: Record<string, string> = {
  router: 'Router', switch: 'Switch', ap: 'AP', camera: 'Cámara',
  olt: 'OLT', ont: 'ONT', ups: 'UPS', server: 'Servidor',
};

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [typeFilter, setTypeFilter] = useState('');
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const { hasPermission } = useAuth();
  const { c } = useTheme();

  const load = () => inventoryAPI.list({ item_type: typeFilter || undefined, search: search || undefined }).then(setItems).catch(console.error);
  useEffect(() => { load(); }, [typeFilter, search]);

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar item del inventario?')) return;
    try { await inventoryAPI.delete(id); toast.success('Eliminado'); load(); }
    catch (err: any) { toast.error(err.message); }
  };

  const statusStyle = (status: string) => {
    if (status === 'active') return { bg: c.greenBg, text: c.green, label: 'Activo' };
    if (status === 'maintenance') return { bg: c.yellowBg, text: c.yellow, label: 'Mantenimiento' };
    return { bg: c.redBg, text: c.red, label: 'Inactivo' };
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Inventario</h1>
        {hasPermission("routers:terminal") && (
          <button onClick={() => { setEditing(null); setShowForm(true); }} className="btn-primary">
            <Plus className="w-4 h-4 inline mr-2" />Agregar Item
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: c.textMuted }} />
          <input className="input pl-10" placeholder="Buscar..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className="input w-auto" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">Todos los tipos</option>
          {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: `1px solid ${c.border}` }}>
              {['Nombre', 'Tipo', 'Marca/Modelo', 'IP', 'Serial', 'Estado', ...(hasPermission("routers:terminal") ? ['Acciones'] : [])].map(h => (
                <th key={h} className={`py-3 px-4 ${h === 'Acciones' ? 'text-right' : 'text-left'}`} style={{ color: c.textMuted }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const st = statusStyle(item.status);
              return (
                <tr key={item.id} style={{ borderBottom: `1px solid ${c.border}` }}>
                  <td className="py-3 px-4 font-medium" style={{ color: c.textPrimary }}>{item.name}</td>
                  <td className="py-3 px-4" style={{ color: c.textMuted }}>{TYPE_LABELS[item.item_type] || item.item_type}</td>
                  <td className="py-3 px-4" style={{ color: c.textMuted }}>{[item.brand, item.model].filter(Boolean).join(' ')}</td>
                  <td className="py-3 px-4 font-mono" style={{ color: c.textMuted }}>{item.ip_address}</td>
                  <td className="py-3 px-4 font-mono text-xs" style={{ color: c.textMuted }}>{item.serial_number}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 rounded text-xs" style={{ background: st.bg, color: st.text }}>{st.label}</span>
                  </td>
                  {hasPermission("routers:terminal") && (
                    <td className="py-3 px-4 text-right">
                      <button onClick={() => { setEditing(item); setShowForm(true); }} className="p-1 rounded" style={{ color: c.textMuted }} title="Editar"><Edit className="w-4 h-4 inline" /></button>
                      {hasPermission("routers:edit") && <button onClick={() => handleDelete(item.id)} className="p-1 rounded ml-1" style={{ color: c.red }} title="Eliminar"><Trash2 className="w-4 h-4 inline" /></button>}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {items.length === 0 && (
        <div className="text-center py-12">
          <Package className="w-12 h-12 mx-auto mb-3 opacity-50" style={{ color: c.textMuted }} />
          <p style={{ color: c.textMuted }}>Sin items en inventario</p>
        </div>
      )}

      {showForm && <InventoryForm item={editing} c={c} onClose={() => { setShowForm(false); setEditing(null); }} onSaved={() => { setShowForm(false); setEditing(null); load(); }} />}
    </div>
  );
}

function InventoryForm({ item, onClose, onSaved, c }: { item: InventoryItem | null; onClose: () => void; onSaved: () => void; c: any }) {
  const [form, setForm] = useState({
    item_type: item?.item_type || 'router', name: item?.name || '', brand: item?.brand || '',
    model: item?.model || '', serial_number: item?.serial_number || '', mac_address: item?.mac_address || '',
    ip_address: item?.ip_address || '', location: item?.location || '', client_name: item?.client_name || '',
    status: item?.status || 'active', notes: item?.notes || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (item) { await inventoryAPI.update(item.id, form); toast.success('Actualizado'); }
      else { await inventoryAPI.create(form); toast.success('Creado'); }
      onSaved();
    } catch (err: any) { toast.error(err.message); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: c.bgOverlay }} onClick={onClose}>
      <div className="rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto" style={{ background: c.bgCard, border: `1px solid ${c.border}` }} onClick={e => e.stopPropagation()}>
        <div className="p-6" style={{ borderBottom: `1px solid ${c.border}` }}>
          <h2 className="text-lg font-semibold" style={{ color: c.textPrimary }}>{item ? 'Editar Item' : 'Agregar Item'}</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Tipo *</label><select className="input" value={form.item_type} onChange={(e) => setForm({ ...form, item_type: e.target.value })}>{Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Estado</label><select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="active">Activo</option><option value="inactive">Inactivo</option><option value="maintenance">Mantenimiento</option></select></div>
          </div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Nombre *</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Marca</label><input className="input" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} /></div>
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Modelo</label><input className="input" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Serial</label><input className="input" value={form.serial_number} onChange={(e) => setForm({ ...form, serial_number: e.target.value })} /></div>
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>IP</label><input className="input" value={form.ip_address} onChange={(e) => setForm({ ...form, ip_address: e.target.value })} /></div>
          </div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Ubicación</label><input className="input" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Cliente</label><input className="input" value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })} /></div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1">{item ? 'Guardar' : 'Crear'}</button>
            <button type="button" onClick={onClose} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}

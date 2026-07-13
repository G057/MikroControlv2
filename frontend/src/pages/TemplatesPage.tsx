import { useState, useEffect } from 'react';
import { templatesAPI } from '../services/api';
import type { ConfigTemplate } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Plus, Edit, Trash2, FileText, Copy } from 'lucide-react';
import toast from 'react-hot-toast';

const CATEGORY_LABELS: Record<string, string> = {
  firewall: 'Firewall', nat: 'NAT', vlan: 'VLAN', dhcp: 'DHCP',
  pppoe: 'PPPoE', wireguard: 'WireGuard', hotspot: 'Hotspot', custom: 'Personalizado',
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<ConfigTemplate[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<ConfigTemplate | null>(null);
  const { hasPermission } = useAuth();
  const { c } = useTheme();

  const load = () => templatesAPI.list().then(setTemplates).catch(console.error);
  useEffect(() => { load(); }, []);

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar plantilla?')) return;
    try { await templatesAPI.delete(id); toast.success('Plantilla eliminada'); load(); }
    catch (err: any) { toast.error(err.message); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Plantillas de Configuración</h1>
        {hasPermission("routers:edit") && (
          <button onClick={() => { setEditing(null); setShowForm(true); }} className="btn-primary">
            <Plus className="w-4 h-4 inline mr-2" />Agregar Plantilla
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.map((t) => (
          <div key={t.id} className="card">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: c.bgHover }}>
                  <FileText className="w-5 h-5" style={{ color: c.textLink }} />
                </div>
                <div>
                  <h3 className="font-semibold" style={{ color: c.textPrimary }}>{t.name}</h3>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: c.bgHover, color: c.textMuted }}>{CATEGORY_LABELS[t.category] || t.category}</span>
                </div>
              </div>
              {hasPermission("routers:edit") && (
                <div className="flex gap-1">
                  <button onClick={() => { setEditing(t); setShowForm(true); }} className="p-1.5 rounded" style={{ color: c.textMuted }} title="Editar"><Edit className="w-4 h-4" /></button>
                  {hasPermission("routers:edit") && <button onClick={() => handleDelete(t.id)} className="p-1.5 rounded" style={{ color: c.red }} title="Eliminar"><Trash2 className="w-4 h-4" /></button>}
                </div>
              )}
            </div>
            {t.description && <p className="text-sm mb-3" style={{ color: c.textMuted }}>{t.description}</p>}
            <pre className="text-xs rounded p-3 overflow-x-auto max-h-32" style={{ color: c.textMuted, background: c.bgPage }}>{t.template_content.slice(0, 300)}</pre>
            <div className="flex items-center justify-between mt-3">
              <span className="w-2 h-2 rounded-full" style={{ background: t.is_active ? c.green : c.red }} />
              <button onClick={() => { navigator.clipboard.writeText(t.template_content); toast.success('Copiado'); }} className="text-xs flex items-center gap-1" style={{ color: c.textMuted }}>
                <Copy className="w-3 h-3" />Copiar
              </button>
            </div>
          </div>
        ))}
      </div>

      {templates.length === 0 && (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" style={{ color: c.textMuted }} />
          <p style={{ color: c.textMuted }}>Sin plantillas creadas</p>
        </div>
      )}

      {showForm && <TemplateForm template={editing} c={c} onClose={() => { setShowForm(false); setEditing(null); }} onSaved={() => { setShowForm(false); setEditing(null); load(); }} />}
    </div>
  );
}

function TemplateForm({ template, onClose, onSaved, c }: { template: ConfigTemplate | null; onClose: () => void; onSaved: () => void; c: any }) {
  const [form, setForm] = useState({
    name: template?.name || '', description: template?.description || '',
    category: template?.category || 'custom', template_content: template?.template_content || '',
    variables: template?.variables || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (template) { await templatesAPI.update(template.id, form); toast.success('Actualizada'); }
      else { await templatesAPI.create(form); toast.success('Creada'); }
      onSaved();
    } catch (err: any) { toast.error(err.message); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: c.bgOverlay }} onClick={onClose}>
      <div className="rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" style={{ background: c.bgCard, border: `1px solid ${c.border}` }} onClick={e => e.stopPropagation()}>
        <div className="p-6" style={{ borderBottom: `1px solid ${c.border}` }}>
          <h2 className="text-lg font-semibold" style={{ color: c.textPrimary }}>{template ? 'Editar Plantilla' : 'Nueva Plantilla'}</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Nombre *</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
            <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Categoría *</label><select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
          </div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Descripción</label><input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Contenido RouterOS *</label><textarea className="input font-mono text-sm" rows={12} value={form.template_content} onChange={(e) => setForm({ ...form, template_content: e.target.value })} required /></div>
          <div><label className="block text-sm mb-1" style={{ color: c.textSecondary }}>Variables (JSON)</label><input className="input font-mono text-sm" placeholder='{"client_ip": "192.168.1.0/24"}' value={form.variables} onChange={(e) => setForm({ ...form, variables: e.target.value })} /></div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary flex-1">{template ? 'Guardar' : 'Crear'}</button>
            <button type="button" onClick={onClose} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { backupsAPI, routersAPI } from '../services/api';
import type { Backup, RouterDevice } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { HardDrive, Download, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { formatDateTime } from '../utils/date';

export default function BackupsPage() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [filterRouter, setFilterRouter] = useState<number | ''>('');
  const { hasPermission } = useAuth();
  const { c } = useTheme();

  const load = () => {
    backupsAPI.list(filterRouter || undefined).then(setBackups).catch(console.error);
    routersAPI.list().then(setRouters).catch(console.error);
  };
  useEffect(() => { load(); }, [filterRouter]);

  const handleCreate = async (routerId: number, type: string) => {
    const toastId = toast.loading('Creando backup...');
    try {
      const result = await backupsAPI.create(routerId, type) as any;
      if (result && result.success === false) toast.error(result.error || 'Error al crear backup', { id: toastId });
      else toast.success('Backup creado', { id: toastId });
      load();
    } catch (err: any) { toast.error(err.message, { id: toastId }); }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar backup?')) return;
    try { await backupsAPI.delete(id); toast.success('Backup eliminado'); load(); }
    catch (err: any) { toast.error(err.message); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Backups</h1>
      </div>

      <select className="input w-auto" value={filterRouter} onChange={(e) => setFilterRouter(e.target.value ? Number(e.target.value) : '')}>
        <option value="">Todos los routers</option>
        {routers.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
      </select>

      {hasPermission("routers:backup") && filterRouter && (
        <div className="card flex gap-3">
          <button onClick={() => handleCreate(Number(filterRouter), 'export')} className="btn-primary">
            <Download className="w-4 h-4 inline mr-2" />Crear Backup (.rsc)
          </button>
        </div>
      )}

      <div className="space-y-3">
        {backups.map((b) => {
          const router = routers.find(r => r.id === b.router_id);
          return (
            <div key={b.id} className="card flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: c.bgHover }}>
                  <HardDrive className="w-5 h-5" style={{ color: c.textMuted }} />
                </div>
                <div>
                  <p className="font-medium" style={{ color: c.textPrimary }}>{b.filename}</p>
                  <p className="text-sm" style={{ color: c.textMuted }}>
                    {router?.name || `Router #${b.router_id}`} - {b.backup_type}
                    {b.routeros_version && ` - ROS ${b.routeros_version}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs" style={{ color: c.textMuted }}>
                  {b.created_at ? formatDateTime(b.created_at) : ''}
                </span>
                <button onClick={() => backupsAPI.download(b.id, b.filename)} className="p-1.5 rounded" style={{ color: c.textMuted }} title="Descargar">
                  <Download className="w-4 h-4" />
                </button>
                {hasPermission("routers:backup") && (
                  <button onClick={() => handleDelete(b.id)} className="p-1.5 rounded" style={{ color: c.red }} title="Eliminar">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {backups.length === 0 && (
        <div className="text-center py-12">
          <HardDrive className="w-12 h-12 mx-auto mb-3 opacity-50" style={{ color: c.textMuted }} />
          <p style={{ color: c.textMuted }}>Sin backups registrados</p>
        </div>
      )}
    </div>
  );
}

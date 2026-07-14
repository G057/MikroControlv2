import { useState, useEffect } from 'react';
import { backupsAPI, routersAPI, settingsAPI } from '../services/api';
import type { Backup, RouterDevice } from '../types';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { HardDrive, Download, Trash2, Clock, Settings, Save, ChevronDown, ChevronRight } from 'lucide-react';
import toast from 'react-hot-toast';
import { formatDateTime } from '../utils/date';

const WEEKDAYS = [
  { value: '0', label: 'Domingo' }, { value: '1', label: 'Lunes' },
  { value: '2', label: 'Martes' }, { value: '3', label: 'Miércoles' },
  { value: '4', label: 'Jueves' }, { value: '5', label: 'Viernes' },
  { value: '6', label: 'Sábado' },
];

export default function BackupsPage() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [filterRouter, setFilterRouter] = useState<number | ''>('');
  const { hasPermission } = useAuth();
  const { c } = useTheme();

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [cfg, setCfg] = useState({
    router_backup_interval_hours: '6',
    router_backup_schedule_days: '',
    router_backup_schedule_time: '03:00',
    router_backup_type: 'export',
    router_backup_retention_days: '30',
    router_backup_retention_count: '60',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    settingsAPI.get().then(s => setCfg({
      router_backup_interval_hours: s.router_backup_interval_hours || '6',
      router_backup_schedule_days: s.router_backup_schedule_days || '',
      router_backup_schedule_time: s.router_backup_schedule_time || '03:00',
      router_backup_type: s.router_backup_type || 'export',
      router_backup_retention_days: s.router_backup_retention_days || '30',
      router_backup_retention_count: s.router_backup_retention_count || '60',
    })).catch(() => {});
  }, []);

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

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await settingsAPI.update(cfg);
      toast.success('Configuración guardada');
    } catch (err: any) { toast.error(err.message); }
    setSaving(false);
  };

  const cfgInterval = parseInt(cfg.router_backup_interval_hours) || 0;
  const cfgDays = cfg.router_backup_schedule_days ? cfg.router_backup_schedule_days.split(',').filter(Boolean) : [];
  const useDays = cfgDays.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Backups</h1>
      </div>

      {/* Configuración de respaldo automático */}
      {hasPermission("routers:backup") && (
        <div className="rounded-xl" style={{ background: c.bgCard, border: `1px solid ${c.borderLight}` }}>
          <button
            onClick={() => setSettingsOpen(!settingsOpen)}
            className="w-full flex items-center justify-between px-4 py-3"
            style={{ color: c.textPrimary }}
          >
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5" style={{ color: c.accent }} />
              <span className="font-semibold text-sm">Respaldo automático de routers</span>
            </div>
            {settingsOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
          {settingsOpen && (
            <div className="px-4 pb-4 space-y-3 border-t pt-3" style={{ borderColor: c.borderLight }}>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Tipo de respaldo</label>
                  <select value={cfg.router_backup_type} onChange={e => setCfg({...cfg, router_backup_type: e.target.value})}
                    className="w-full rounded-lg px-3 py-2 text-sm outline-none" style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}>
                    <option value="export">Export (.rsc)</option>
                    <option value="binary">Binary (.backup)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Programar por</label>
                <div className="flex gap-2">
                  <button onClick={() => setCfg({...cfg, router_backup_schedule_days: ''})}
                    className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{ background: !useDays ? c.accent : c.bgHover, color: !useDays ? '#fff' : c.textSecondary, border: `1px solid ${!useDays ? c.accent : c.border}` }}>
                    Intervalo (horas)
                  </button>
                  <button onClick={() => setCfg({...cfg, router_backup_schedule_days: '1'})}
                    className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{ background: useDays ? c.accent : c.bgHover, color: useDays ? '#fff' : c.textSecondary, border: `1px solid ${useDays ? c.accent : c.border}` }}>
                    Días y hora
                  </button>
                </div>
              </div>

              {!useDays ? (
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Intervalo (horas)</label>
                  <input type="number" min="1" value={cfgInterval} onChange={e => setCfg({...cfg, router_backup_interval_hours: e.target.value})}
                    className="w-full rounded-lg px-3 py-2 text-sm outline-none" style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }} />
                </div>
              ) : (
                <>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Días de la semana</label>
                    <div className="flex flex-wrap gap-1.5">
                      {WEEKDAYS.map(d => {
                        const selected = cfgDays.includes(d.value);
                        return (
                          <button key={d.value} onClick={() => {
                            const next = selected ? cfgDays.filter(v => v !== d.value) : [...cfgDays, d.value];
                            setCfg({...cfg, router_backup_schedule_days: next.join(',')});
                          }}
                            className="px-2.5 py-1 rounded-lg text-xs font-medium transition-colors"
                            style={{ background: selected ? c.accent : c.bgHover, color: selected ? '#fff' : c.textSecondary }}>
                            {d.label.slice(0, 3)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Hora (HH:MM, formato 24h)</label>
                    <input type="text" value={cfg.router_backup_schedule_time} onChange={e => {
                      const v = e.target.value;
                      if (/^\d{0,2}:?\d{0,2}$/.test(v)) setCfg({...cfg, router_backup_schedule_time: v});
                    }} placeholder="03:00"
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none" style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }} />
                  </div>
                </>
              )}

              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Retención (días)</label>
                  <input type="number" min="0" value={parseInt(cfg.router_backup_retention_days) || 0} onChange={e => setCfg({...cfg, router_backup_retention_days: e.target.value})}
                    className="w-full rounded-lg px-3 py-2 text-sm outline-none" style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }} />
                </div>
                <div className="flex-1">
                  <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Máx. archivos</label>
                  <input type="number" min="0" value={parseInt(cfg.router_backup_retention_count) || 0} onChange={e => setCfg({...cfg, router_backup_retention_count: e.target.value})}
                    className="w-full rounded-lg px-3 py-2 text-sm outline-none" style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }} />
                </div>
              </div>

              <div className="text-xs" style={{ color: c.textMuted }}>
                {useDays
                  ? `Se ejecutará los días seleccionados a las ${cfg.router_backup_schedule_time}`
                  : `Se ejecutará cada ${cfgInterval} hora(s)`}
                . Los respaldos más antiguos que {cfg.router_backup_retention_days} días o que excedan {cfg.router_backup_retention_count} archivos se eliminarán automáticamente.
              </div>

              <button onClick={handleSaveSettings} disabled={saving}
                className="w-full py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2"
                style={{ background: c.accent, color: '#fff', opacity: saving ? 0.6 : 1 }}>
                {saving ? 'Guardando...' : <><Save className="w-4 h-4" /> Guardar configuración</>}
              </button>
            </div>
          )}
        </div>
      )}

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

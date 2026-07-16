import { useState, useEffect, useRef } from 'react';
import { settingsAPI, rolesAPI, eventsAPI, logoAPI, systemBackupAPI, type SystemSettings, type OperatorUser, type EventFilterRule, type SystemBackupItem, type SystemServices } from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import EventFilterRulesEditor from '../components/EventFilterRulesEditor';
import ErrorBoundary from '../components/ErrorBoundary';
import {
  Settings, Users, Mail, MessageCircle, Bell, Download, Plus, Trash2,
  Save, Send, CheckCircle, XCircle, Eye, EyeOff, Shield, Clock, Activity, Filter, Image, RotateCcw, RefreshCw, Radio,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { formatDateTime, getTimezone, setTimezone } from '../utils/date';

function Toggle({ value, onChange, c }: { value: boolean; onChange: (v: boolean) => void; c: any }) {
  return (
    <button onClick={() => onChange(!value)} className="relative w-10 h-5 rounded-full transition-colors" style={{ background: value ? c.green : c.border }}>
      <span className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full transition-transform bg-white" style={{ transform: value ? 'translateX(20px)' : 'translateX(0)' }} />
    </button>
  );
}

function OperatorsTab({ c }: { c: any }) {
  const [users, setUsers] = useState<OperatorUser[]>([]);
  const [roles, setRoles] = useState<{ name: string; is_system: boolean }[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editUser, setEditUser] = useState<OperatorUser | null>(null);
  const [form, setForm] = useState({ username: '', email: '', full_name: '', password: '', role: 'tecnico_n1' });

  const load = () => {
    settingsAPI.listOperators().then(setUsers).catch(console.error);
    rolesAPI.list().then(r => {
      setRoles(r);
      if (!form.role || !r.find(x => x.name === form.role)) {
        const first = r.find(x => !x.is_system);
        setForm(f => ({ ...f, role: first ? first.name : 'tecnico_n1' }));
      }
    }).catch(console.error);
  };
  useEffect(() => { load(); }, []);

  const handleSubmit = async () => {
    try {
      if (editUser) {
        const data: Record<string, any> = { email: form.email, full_name: form.full_name, role: form.role };
        if (form.password) data.password = form.password;
        await settingsAPI.updateOperator(editUser.id, data);
        toast.success('Usuario actualizado');
      } else {
        await settingsAPI.createOperator(form);
        toast.success('Usuario creado');
      }
      setShowForm(false); setEditUser(null);
      load();
    } catch (e: any) { toast.error(e.message); }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Eliminar usuario "${name}"?`)) return;
    try { await settingsAPI.deleteOperator(id); toast.success('Eliminado'); load(); }
    catch (e: any) { toast.error(e.message); }
  };

  const handleToggleActive = async (u: OperatorUser) => {
    try { await settingsAPI.updateOperator(u.id, { is_active: !u.is_active }); load(); }
    catch (e: any) { toast.error(e.message); }
  };

  const roleLabel = (rn: string) => roles.find(r => r.name === rn)?.name || rn;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm" style={{ color: c.textSecondary }}>{users.length} usuarios registrados</p>
        <button onClick={() => { setShowForm(true); setEditUser(null); setForm({ username: '', email: '', full_name: '', password: '', role: roles.find(r => !r.is_system)?.name || 'tecnico_n1' }); }} className="btn-primary text-sm">
          <Plus className="w-4 h-4 inline mr-1" />Nuevo usuario
        </button>
      </div>

      {showForm && (
        <div className="card !p-4 space-y-3">
          <h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>{editUser ? 'Editar usuario' : 'Nuevo usuario'}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Username</label>
              <input className="input w-full text-sm" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} disabled={!!editUser} />
            </div>
            <div>
              <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Email</label>
              <input className="input w-full text-sm" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Nombre completo</label>
              <input className="input w-full text-sm" value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div>
              <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>{editUser ? 'Nueva contraseña (vacío = no cambiar)' : 'Contraseña'}</label>
              <input className="input w-full text-sm" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
            </div>
            <div>
              <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Rol</label>
              <select className="input w-full text-sm" value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
                {roles.map(r => <option key={r.name} value={r.name}>{r.name}{r.is_system ? ' (sistema)' : ''}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={handleSubmit} className="btn-primary text-sm"><Save className="w-4 h-4 inline mr-1" />Guardar</button>
            <button onClick={() => { setShowForm(false); setEditUser(null); }} className="btn-secondary text-sm">Cancelar</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {users.map(u => (
          <div key={u.id} className="card !p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-full flex items-center justify-center shrink-0" style={{ background: u.is_active ? `${c.green}20` : `${c.red}20` }}>
              <Shield className="w-4 h-4" style={{ color: u.is_active ? c.green : c.red }} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: c.textPrimary }}>{u.full_name || u.username}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: c.bgHover, color: c.textMuted }}>@{u.username}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium capitalize" style={{ background: `${c.accent}20`, color: c.accent }}>
                  {roleLabel(u.role)}
                </span>
              </div>
              <p className="text-[11px]" style={{ color: c.textMuted }}>{u.email} {u.last_login ? `· Último login: ${formatDateTime(u.last_login)}` : ''}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Toggle value={u.is_active} onChange={() => handleToggleActive(u)} c={c} />
              <button onClick={() => { setEditUser(u); setForm({ username: u.username, email: u.email, full_name: u.full_name, password: '', role: u.role }); setShowForm(true); }} className="p-1.5 rounded hover:opacity-80" style={{ color: c.textMuted }}>
                <Settings className="w-4 h-4" />
              </button>
              <button onClick={() => handleDelete(u.id, u.username)} className="p-1.5 rounded hover:opacity-80" style={{ color: c.red }}>
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SMTPTab({ settings, onSave, c }: { settings: SystemSettings; onSave: (d: Partial<SystemSettings>) => void; c: any }) {
  const [form, setForm] = useState(settings);
  const [testing, setTesting] = useState(false);
  const [showPass, setShowPass] = useState(false);

  useEffect(() => { setForm(settings); }, [settings]);

  const handleTest = async () => {
    setTesting(true);
    try {
      await settingsAPI.update(form);
      const res = await settingsAPI.testEmail();
      toast.success(res.message);
    } catch (e: any) { toast.error(e.message); }
    setTesting(false);
  };

  const Field = ({ label, field, type = 'text', placeholder = '' }: { label: string; field: keyof SystemSettings; type?: string; placeholder?: string }) => (
    <div>
      <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>{label}</label>
      <input className="input w-full text-sm" type={type} placeholder={placeholder} value={form[field] || ''}
        onChange={e => setForm({ ...form, [field]: e.target.value })} />
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium" style={{ color: c.textPrimary }}>Notificaciones por email</span>
          <Toggle value={form.notify_email_enabled === 'true'} onChange={v => setForm({ ...form, notify_email_enabled: v ? 'true' : 'false' })} c={c} />
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Servidor SMTP" field="smtp_host" placeholder="smtp.gmail.com" />
        <Field label="Puerto" field="smtp_port" placeholder="587" />
        <Field label="Usuario" field="smtp_user" placeholder="tu@gmail.com" />
        <div>
          <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Contraseña</label>
          <div className="relative">
            <input className="input w-full text-sm pr-9" type={showPass ? 'text' : 'password'} value={form.smtp_password || ''}
              onChange={e => setForm({ ...form, smtp_password: e.target.value })} />
            <button onClick={() => setShowPass(!showPass)} className="absolute right-2 top-1/2 -translate-y-1/2" style={{ color: c.textMuted }}>
              {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>
        <Field label="Email desde" field="smtp_from" placeholder="mikrocontrol@empresa.com" />
        <div className="flex items-center gap-2">
          <span className="text-sm" style={{ color: c.textSecondary }}>TLS</span>
          <Toggle value={form.smtp_tls === 'true'} onChange={v => setForm({ ...form, smtp_tls: v ? 'true' : 'false' })} c={c} />
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={() => onSave(form)} className="btn-primary text-sm"><Save className="w-4 h-4 inline mr-1" />Guardar</button>
        <button onClick={handleTest} disabled={testing} className="btn-secondary text-sm"><Send className="w-4 h-4 inline mr-1" />{testing ? 'Enviando...' : 'Enviar prueba'}</button>
      </div>
    </div>
  );
}

function TelegramTab({ settings, onSave, c }: { settings: SystemSettings; onSave: (d: Partial<SystemSettings>) => void; c: any }) {
  const [form, setForm] = useState(settings);
  const [testing, setTesting] = useState(false);

  useEffect(() => { setForm(settings); }, [settings]);

  const handleTest = async () => {
    setTesting(true);
    try {
      await settingsAPI.update(form);
      const res = await settingsAPI.testTelegram();
      toast.success(res.message);
    } catch (e: any) { toast.error(e.message); }
    setTesting(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium" style={{ color: c.textPrimary }}>Notificaciones por Telegram</span>
        <Toggle value={form.notify_telegram_enabled === 'true'} onChange={v => setForm({ ...form, notify_telegram_enabled: v ? 'true' : 'false' })} c={c} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Bot Token</label>
          <input className="input w-full text-sm" placeholder="123456:ABC-DEF..." value={form.telegram_bot_token || ''}
            onChange={e => setForm({ ...form, telegram_bot_token: e.target.value })} />
        </div>
        <div>
          <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Chat ID</label>
          <input className="input w-full text-sm" placeholder="-1001234567890" value={form.telegram_chat_id || ''}
            onChange={e => setForm({ ...form, telegram_chat_id: e.target.value })} />
        </div>
      </div>
      <div className="rounded-lg p-3 text-xs" style={{ background: c.bgHover, color: c.textMuted }}>
        <p className="font-medium mb-1" style={{ color: c.textSecondary }}>Cómo configurar:</p>
        <ol className="list-decimal list-inside space-y-0.5">
          <li>Hablá con <span className="font-mono" style={{ color: c.textLink }}>@BotFather</span> en Telegram y creá un bot con <code>/newbot</code></li>
          <li>Copiá el token que te dé y pegalo arriba</li>
          <li>Mandale un mensaje a tu bot, luego entrá a <code>api.telegram.org/bot[TOKEN]/getUpdates</code></li>
          <li>Buscá el <code>chat.id</code> en la respuesta y pegalo arriba</li>
        </ol>
      </div>
      <div className="flex gap-2">
        <button onClick={() => onSave(form)} className="btn-primary text-sm"><Save className="w-4 h-4 inline mr-1" />Guardar</button>
        <button onClick={handleTest} disabled={testing} className="btn-secondary text-sm"><Send className="w-4 h-4 inline mr-1" />{testing ? 'Enviando...' : 'Enviar prueba'}</button>
      </div>
    </div>
  );
}

function NotificationsTab({ settings, onSave, c }: { settings: SystemSettings; onSave: (d: Partial<SystemSettings>) => void; c: any }) {
  const [form, setForm] = useState(settings);
  useEffect(() => { setForm(settings); }, [settings]);

  const toggles = [
    { key: 'notify_router_offline', label: 'Router offline', desc: 'Cuando un router deja de responder' },
    { key: 'notify_router_online', label: 'Router online', desc: 'Cuando un router se reconecta' },
    { key: 'notify_critical_alert', label: 'Alertas críticas', desc: 'Alertas de severidad crítica' },
    { key: 'notify_warning_alert', label: 'Alertas de advertencia', desc: 'Alertas de severidad warning' },
    { key: 'notify_backup_complete', label: 'Backup completado', desc: 'Cuando finaliza un backup' },
    { key: 'notify_high_cpu', label: 'CPU alto', desc: 'Cuando CPU supera el umbral' },
    { key: 'notify_high_temp', label: 'Temperatura alta', desc: 'Cuando la temperatura es elevada' },
  ] as const;

  const repeatToggles = [
    { key: 'notify_repeat_critical', label: 'Repetir críticas', desc: 'Re-notificar cada vez que aparezca un log crítico aunque la alerta ya exista' },
    { key: 'notify_repeat_warning', label: 'Repetir advertencias', desc: 'Re-notificar cada vez que aparezca un log warning aunque la alerta ya exista' },
  ] as const;

  const handleToggle = (key: string) => {
    const next = { ...form, [key]: form[key as keyof SystemSettings] === 'true' ? 'false' : 'true' };
    setForm(next);
    onSave(next);
  };

  return (
    <div className="space-y-3">
      <p className="text-sm mb-3" style={{ color: c.textSecondary }}>Elegí qué eventos generan notificaciones por email y/o Telegram.</p>
      {toggles.map(t => (
        <div key={t.key} className="card !p-3 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium" style={{ color: c.textPrimary }}>{t.label}</p>
            <p className="text-[11px]" style={{ color: c.textMuted }}>{t.desc}</p>
          </div>
          <Toggle value={form[t.key] === 'true'} onChange={() => handleToggle(t.key)} c={c} />
        </div>
      ))}
      <p className="text-sm font-semibold mt-4 pt-4 border-t" style={{ color: c.textPrimary, borderColor: c.border }}>Re-notificaciones</p>
      <p className="text-xs mb-2" style={{ color: c.textMuted }}>Cuando un log warning/critical aparece y ya existe una alerta sin resolver, ¿volver a notificar?</p>
      {repeatToggles.map(t => (
        <div key={t.key} className="card !p-3 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium" style={{ color: c.textPrimary }}>{t.label}</p>
            <p className="text-[11px]" style={{ color: c.textMuted }}>{t.desc}</p>
          </div>
          <Toggle value={form[t.key] === 'true'} onChange={() => handleToggle(t.key)} c={c} />
        </div>
      ))}
    </div>
  );
}

function BackupTab({ c }: { c: any }) {
  const [backups, setBackups] = useState<SystemBackupItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [backupInterval, setBackupInterval] = useState(6);
  const [scheduleDays, setScheduleDays] = useState('');
  const [scheduleTime, setScheduleTime] = useState('03:00');
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const DAYS = [
    { v: '0', label: 'Lu' }, { v: '1', label: 'Ma' }, { v: '2', label: 'Mi' },
    { v: '3', label: 'Ju' }, { v: '4', label: 'Vi' }, { v: '5', label: 'Sa' }, { v: '6', label: 'Do' },
  ];

  const load = async () => {
    setLoading(true);
    try {
      const [b, s] = await Promise.all([
        systemBackupAPI.list(),
        settingsAPI.get(),
      ]);
      setBackups(b);
      setBackupInterval(Number(s.backup_interval_hours) || 6);
      setScheduleDays(s.backup_schedule_days || '');
      setScheduleTime(s.backup_schedule_time || '03:00');
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const res = await systemBackupAPI.create();
      toast.success(res.message);
      load();
    } catch (e: any) { toast.error(e.message); }
    setCreating(false);
  };

  const handleRestore = async (filename: string) => {
    if (!confirm(`Restaurar backup ${filename}?\n\nEl servicio se reiniciará automáticamente.`)) return;
    setRestoring(filename);
    try {
      const res = await systemBackupAPI.restore(filename);
      toast.success(res.message);
    } catch (e: any) { toast.error(e.message); }
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Eliminar backup ${filename}?`)) return;
    try {
      await systemBackupAPI.deleteOne(filename);
      toast.success('Backup eliminado');
      load();
    } catch (e: any) { toast.error(e.message); }
  };

  const handleDeleteSelected = async () => {
    if (selected.size === 0) return;
    if (!confirm(`Eliminar ${selected.size} backup(s) seleccionado(s)?`)) return;
    try {
      const res = await systemBackupAPI.deleteBulk(Array.from(selected));
      toast.success(res.message);
      setSelected(new Set());
      load();
    } catch (e: any) { toast.error(e.message); }
  };

  const toggleSelect = (filename: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === backups.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(backups.map(b => b.filename)));
    }
  };

  const toggleDay = (d: string) => {
    const current = scheduleDays ? scheduleDays.split(',').map(x => x.trim()) : [];
    const next = current.includes(d) ? current.filter(x => x !== d) : [...current, d];
    setScheduleDays(next.sort().join(','));
  };

  const handleSave = async () => {
    try {
      await settingsAPI.update({
        backup_interval_hours: String(backupInterval),
        backup_schedule_days: scheduleDays,
        backup_schedule_time: scheduleTime,
      });
      toast.success('Configuración de backup guardada');
    } catch (e: any) { toast.error(e.message); }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl p-4 space-y-4" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
        <h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>Programación de Backups</h3>

        <div>
          <p className="text-xs mb-2" style={{ color: c.textMuted }}>Días de la semana (dejá vacío para diario)</p>
          <div className="flex gap-1.5">
            {DAYS.map(d => {
              const active = scheduleDays.split(',').map(x => x.trim()).includes(d.v);
              return (
                <button key={d.v} onClick={() => toggleDay(d.v)}
                  className="w-9 h-9 rounded-lg text-xs font-semibold transition-all"
                  style={{
                    background: active ? c.accent : c.bgCard,
                    color: active ? '#fff' : c.textSecondary,
                    border: `1px solid ${active ? c.accent : c.border}`,
                  }}>
                  {d.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div>
            <p className="text-xs mb-1" style={{ color: c.textMuted }}>Hora del backup</p>
            <input type="time" value={scheduleTime} onChange={e => setScheduleTime(e.target.value)}
              className="input w-28 text-sm py-1.5"
              style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }} />
          </div>
          <div>
            <p className="text-xs mb-1" style={{ color: c.textMuted }}>O cada</p>
            <select value={backupInterval} onChange={e => setBackupInterval(Number(e.target.value))}
              className="input w-28 text-sm py-1.5"
              style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}>
              <option value={0}>Manual</option>
              <option value={1}>1 hora</option>
              <option value={6}>6 horas</option>
              <option value={12}>12 horas</option>
              <option value={24}>24 horas</option>
              <option value={48}>48 horas</option>
              <option value={72}>72 horas</option>
            </select>
          </div>
          <button onClick={handleSave} className="btn-primary text-sm py-1.5 mt-4">
            <Save className="w-4 h-4 inline mr-1" />Guardar
          </button>
        </div>
        <p className="text-xs" style={{ color: c.textMuted }}>
          {scheduleDays ? `Se ejecutará los días seleccionados a las ${scheduleTime}` : backupInterval > 0 ? `Se ejecutará cada ${backupInterval} horas` : 'Backup manual solo con el botón "Crear Backup"'}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>Backups Disponibles</h3>
        <div className="flex gap-2">
          {selected.size > 0 && (
            <button onClick={handleDeleteSelected} className="btn-danger text-sm py-1.5">
              <Trash2 className="w-4 h-4 inline mr-1" />Eliminar {selected.size}
            </button>
          )}
          <button onClick={load} className="btn-secondary text-sm py-1.5" disabled={loading}>
            <RefreshCw className={`w-4 h-4 inline mr-1 ${loading ? 'animate-spin' : ''}`} />Actualizar
          </button>
          <button onClick={handleCreate} disabled={creating} className="btn-primary text-sm py-1.5">
            <Plus className="w-4 h-4 inline mr-1" />{creating ? 'Creando...' : 'Crear Backup'}
          </button>
        </div>
      </div>

      {backups.length === 0 ? (
        <div className="text-sm py-8 text-center" style={{ color: c.textMuted }}>
          {loading ? 'Cargando...' : 'No hay backups. Creá el primero con el botón "Crear Backup".'}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl" style={{ border: `1px solid ${c.borderLight}` }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: c.bgHover }}>
                <th className="w-10 px-2 py-2.5 text-center">
                  <input type="checkbox" checked={selected.size === backups.length && backups.length > 0}
                    onChange={toggleAll}
                    className="accent-cyan-500 cursor-pointer" />
                </th>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: c.textSecondary }}>Archivo</th>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: c.textSecondary }}>Fecha</th>
                <th className="text-right px-4 py-2.5 font-medium" style={{ color: c.textSecondary }}>Tamaño</th>
                <th className="text-right px-4 py-2.5 font-medium" style={{ color: c.textSecondary }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {backups.map(b => (
                <tr key={b.filename} style={{
                  borderTop: `1px solid ${c.borderLight}`,
                  background: selected.has(b.filename) ? c.bgHover : 'transparent',
                }}>
                  <td className="w-10 px-2 py-2.5 text-center">
                    <input type="checkbox" checked={selected.has(b.filename)}
                      onChange={() => toggleSelect(b.filename)}
                      className="accent-cyan-500 cursor-pointer" />
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: c.textPrimary }}>{b.filename}</td>
                  <td className="px-4 py-2.5 text-xs" style={{ color: c.textMuted }}>{b.created_at_display}</td>
                  <td className="px-4 py-2.5 text-right text-xs" style={{ color: c.textMuted }}>{formatSize(b.size)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => systemBackupAPI.download(b.filename)}
                        className="p-1.5 rounded-lg transition-colors" title="Descargar"
                        style={{ color: c.textMuted }}
                        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = c.bgHover}
                        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}>
                        <Download className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleRestore(b.filename)}
                        disabled={restoring === b.filename}
                        className="p-1.5 rounded-lg transition-colors" title="Restaurar"
                        style={{ color: c.orange }}
                        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = c.bgHover}
                        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}>
                        <RotateCcw className={`w-4 h-4 ${restoring === b.filename ? 'animate-spin' : ''}`} />
                      </button>
                      <button onClick={() => handleDelete(b.filename)}
                        className="p-1.5 rounded-lg transition-colors" title="Eliminar"
                        style={{ color: c.red || '#ef4444' }}
                        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = c.bgHover}
                        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MonitoringTab({ settings, onSave, c }: { settings: SystemSettings; onSave: (d: Partial<SystemSettings>) => void; c: any }) {
  const [health, setHealth] = useState(Number(settings.health_check_interval) || 300);
  const [logs, setLogs] = useState(Number(settings.log_fetch_interval) || 120);
  const [history, setHistory] = useState(Number(settings.history_fetch_interval) || 300);
  const [healthAlert, setHealthAlert] = useState(settings.health_alerts_enabled !== 'false');
  const [logAlert, setLogAlert] = useState(settings.log_alerts_enabled !== 'false');
  const [historyAlert, setHistoryAlert] = useState(settings.history_alerts_enabled !== 'false');

  const fmt = (sec: number) => {
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return s > 0 ? `${m}m ${s}s` : `${m} min`;
  };

  const items = [
    { label: 'Health Check', desc: 'Verifica estado, CPU, RAM, temperatura y crea alertas de conexión/desconexión', value: health, set: setHealth, key: 'health_check_interval', alert: healthAlert, setAlert: setHealthAlert, alertKey: 'health_alerts_enabled', icon: '🔍', default: 300 },
    { label: 'Router Logs', desc: 'Obtiene los logs del sistema (/log/print) de cada router', value: logs, set: setLogs, key: 'log_fetch_interval', alert: logAlert, setAlert: setLogAlert, alertKey: 'log_alerts_enabled', icon: '📋', default: 120 },
    { label: 'Historial', desc: 'Obtiene el historial de comandos ejecutados (/system/history/print)', value: history, set: setHistory, key: 'history_fetch_interval', alert: historyAlert, setAlert: setHistoryAlert, alertKey: 'history_alerts_enabled', icon: '📜', default: 300 },
  ];

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: c.textPrimary }}>Intervalos de Monitoreo</h3>
        <p className="text-xs mb-4" style={{ color: c.textMuted }}>Controlá cada cuánto tiempo se consultan los routers. Mínimo 30 segundos. Activá o desactivá las alertas de desconexión por servicio.</p>
      </div>

      {items.map(item => (
        <div key={item.key} className="rounded-lg p-4" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="text-sm font-semibold" style={{ color: c.textPrimary }}>{item.icon} {item.label}</span>
              <p className="text-xs mt-0.5" style={{ color: c.textMuted }}>{item.desc}</p>
            </div>
            <span className="text-xs font-mono px-2 py-1 rounded" style={{ background: c.bgCard, color: c.textSecondary, border: `1px solid ${c.border}` }}>
              {fmt(item.value)}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <input type="range" min={30} max={3600} step={30} value={item.value}
              onChange={e => item.set(Number(e.target.value))}
              className="flex-1 h-1.5 rounded-full appearance-none cursor-pointer"
              style={{ background: c.border, accentColor: c.accent }} />
            <input type="number" min={30} max={3600} step={30} value={item.value}
              onChange={e => item.set(Math.max(30, Number(e.target.value)))}
              className="input w-20 text-center text-sm font-mono py-1" />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[10px]" style={{ color: c.textMuted }}>30s</span>
            <button onClick={() => item.set(item.default)} className="text-[10px] font-semibold" style={{ color: c.textLink }}>Restablecer ({fmt(item.default)})</button>
            <span className="text-[10px]" style={{ color: c.textMuted }}>60 min</span>
          </div>
          <div className="flex items-center justify-between mt-3 pt-3" style={{ borderTop: `1px solid ${c.border}` }}>
            <div>
              <span className="text-xs font-medium" style={{ color: c.textSecondary }}>Alerta por desconexión</span>
              <p className="text-[10px]" style={{ color: c.textMuted }}>Avisar si este servicio no puede conectar</p>
            </div>
            <Toggle value={item.alert} onChange={() => item.setAlert(!item.alert)} c={c} />
          </div>
        </div>
      ))}

      <button onClick={() => onSave({
        health_check_interval: String(health),
        log_fetch_interval: String(logs),
        history_fetch_interval: String(history),
        health_alerts_enabled: healthAlert ? 'true' : 'false',
        log_alerts_enabled: logAlert ? 'true' : 'false',
        history_alerts_enabled: historyAlert ? 'true' : 'false',
      })} className="btn-primary text-sm">
        <Save className="w-4 h-4 inline mr-1" />Guardar Configuración
      </button>
    </div>
  );
}

function SyslogTab({ settings, onSave, c }: { settings: SystemSettings; onSave: (d: Partial<SystemSettings>) => void; c: any }) {
  const [enabled, setEnabled] = useState(settings.syslog_enabled === 'true');
  const [port, setPort] = useState(Number(settings.syslog_port) || 5140);
  const [queueSize, setQueueSize] = useState(Number(settings.syslog_queue_max_size) || 500);
  const [workers, setWorkers] = useState(Number(settings.syslog_worker_count) || 1);

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: c.textPrimary }}>Receptor Syslog</h3>
        <p className="text-xs" style={{ color: c.textMuted }}>Canal principal de eventos RouterOS en tiempo real. Al guardar, el receptor se inicia o detiene automáticamente.</p>
      </div>
      <div className="rounded-lg p-4" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <span className="text-sm font-semibold" style={{ color: c.textPrimary }}>Recibir Syslog UDP</span>
            <p className="text-xs mt-1" style={{ color: c.textMuted }}>Guarda eventos no asociados y descartes de cola para diagnóstico.</p>
          </div>
          <Toggle value={enabled} onChange={setEnabled} c={c} />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          { label: 'Puerto UDP', value: port, set: setPort, min: 1024, max: 65535 },
          { label: 'Capacidad de cola', value: queueSize, set: setQueueSize, min: 100, max: 10000 },
          { label: 'Workers', value: workers, set: setWorkers, min: 1, max: 16 },
        ].map(item => (
          <label key={item.label} className="rounded-lg p-3 text-xs" style={{ background: c.bgPage, border: `1px solid ${c.border}`, color: c.textSecondary }}>
            <span className="block mb-2 font-medium">{item.label}</span>
            <input type="number" min={item.min} max={item.max} value={item.value}
              onChange={e => item.set(Math.max(item.min, Math.min(item.max, Number(e.target.value) || item.min)))}
              className="input w-full text-center text-sm font-mono py-1" disabled={!enabled} />
          </label>
        ))}
      </div>
      <div className="rounded-lg p-4 text-xs leading-5" style={{ background: c.bgPage, border: `1px solid ${c.border}`, color: c.textMuted }}>
        <strong style={{ color: c.textSecondary }}>RouterOS:</strong> creá una acción remota UDP hacia la IP del servidor y el puerto configurado, luego asociá los topics deseados a esa acción. No uses Syslog para detectar routers offline: esa tarea corresponde a Health Check.
      </div>
      <button onClick={() => onSave({
        syslog_enabled: enabled ? 'true' : 'false', syslog_port: String(port),
        syslog_queue_max_size: String(queueSize), syslog_worker_count: String(workers),
      })} className="btn-primary text-sm">
        <Save className="w-4 h-4 inline mr-1" />Guardar Syslog
      </button>
    </div>
  );
}

function ServicesTab({ c }: { c: any }) {
  const [data, setData] = useState<SystemServices | null>(null);
  const [loading, setLoading] = useState(false);
  const load = () => settingsAPI.services().then(setData).catch((e: Error) => toast.error(e.message));
  useEffect(() => { load(); const timer = setInterval(load, 15000); return () => clearInterval(timer); }, []);
  const restart = async (name: string, label: string) => {
    if (!confirm(`¿Reiniciar ${label}? El servicio tendrá una interrupción breve.`)) return;
    setLoading(true);
    try { await settingsAPI.restartService(name); toast.success(`${label} reiniciado`); setTimeout(load, 2000); }
    catch (e: any) { toast.error(e.message); }
    finally { setLoading(false); }
  };
  const bytes = (value: number) => value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(1)} GB` : `${(value / 1024 ** 2).toFixed(0)} MB`;
  const uptime = (seconds: number) => `${Math.floor(seconds / 86400)}d ${Math.floor(seconds % 86400 / 3600)}h`;
  return <div className="space-y-5"><div><h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>Servicios y Recursos</h3><p className="text-xs mt-1" style={{ color: c.textMuted }}>Monitoreo del servidor. Los reinicios están limitados a servicios de MikroControl; nunca reinician el sistema operativo.</p></div>{data && <><div className="grid grid-cols-1 md:grid-cols-3 gap-3">{[{ label: 'Memoria', percent: data.resources.memory.percent, detail: `${bytes(data.resources.memory.used)} usados` }, { label: 'Disco del servidor', percent: data.resources.disk.percent, detail: `${bytes(data.resources.disk.free)} libres de ${bytes(data.resources.disk.total)}` }, { label: 'Carga', percent: Math.min(100, data.resources.load[0] / data.resources.cpuCount * 100), detail: `${data.resources.load.join(' / ')} (${data.resources.cpuCount} CPU)` }, { label: 'Base de datos', percent: 0, detail: `${bytes(data.resources.database.size)} · ${data.resources.database.connections} conexiones` }, { label: 'Backups de routers', percent: 0, detail: bytes(data.resources.backupsSize) }, { label: 'Uptime del servidor', percent: 0, detail: uptime(data.resources.uptimeSeconds) }].map(item => <div key={item.label} className="rounded-lg p-4" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}><div className="flex justify-between text-sm"><span>{item.label}</span>{item.percent > 0 && <b>{item.percent.toFixed(1)}%</b>}</div>{item.percent > 0 && <div className="h-2 rounded mt-3 overflow-hidden" style={{ background: c.border }}><div className="h-full" style={{ width: `${item.percent}%`, background: item.percent > 85 ? c.red : item.percent > 70 ? c.yellow : c.green }} /></div>}<p className="text-xs mt-2" style={{ color: c.textMuted }}>{item.detail}</p></div>)}</div><div className="space-y-2">{data.services.map(service => <div key={service.name} className="rounded-lg p-4 flex items-center justify-between gap-4" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}><div><p className="text-sm font-semibold" style={{ color: c.textPrimary }}>{service.label}</p><p className="text-xs" style={{ color: service.status === 'active' ? c.green : c.red }}>{service.status}</p></div>{service.canRestart && <button disabled={loading} onClick={() => restart(service.name, service.label)} className="btn-secondary text-sm">Reiniciar</button>}</div>)}</div></>}</div>;
}


function ClockTab({ c }: { c: any }) {
  const [tz, setTz] = useState(getTimezone());
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const TIMEZONES = [
    { value: 'America/Argentina/Buenos_Aires', label: 'Buenos Aires (ART, UTC-3)' },
    { value: 'America/Sao_Paulo', label: 'São Paulo (BRT, UTC-3)' },
    { value: 'America/Lima', label: 'Lima (PET, UTC-5)' },
    { value: 'America/Bogota', label: 'Bogotá (COT, UTC-5)' },
    { value: 'America/Santiago', label: 'Santiago (CLT, UTC-4/-3)' },
    { value: 'America/Montevideo', label: 'Montevideo (UYT, UTC-3)' },
    { value: 'America/Asuncion', label: 'Asunción (PYT, UTC-4/-3)' },
    { value: 'America/Mexico_City', label: 'Ciudad de México (CST, UTC-6)' },
    { value: 'America/New_York', label: 'Nueva York (EST, UTC-5)' },
    { value: 'America/Chicago', label: 'Chicago (CST, UTC-6)' },
    { value: 'America/Los_Angeles', label: 'Los Ángeles (PST, UTC-8)' },
    { value: 'Europe/Madrid', label: 'Madrid (CET, UTC+1/+2)' },
    { value: 'Europe/London', label: 'Londres (GMT, UTC+0/+1)' },
    { value: 'UTC', label: 'UTC' },
  ];

  const handleSave = () => {
    setTimezone(tz);
    toast.success('Zona horaria actualizada');
  };

  const formatted = now.toLocaleString('es-AR', {
    timeZone: tz,
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: c.textPrimary }}>Hora del Sistema</h3>
        <p className="text-xs mb-3" style={{ color: c.textMuted }}>Hora actual en la zona horaria seleccionada</p>
        <div className="rounded-lg p-4 text-center" style={{ background: c.bgPage, border: `1px solid ${c.border}` }}>
          <Clock className="w-8 h-8 mx-auto mb-2" style={{ color: c.accent }} />
          <p className="text-2xl font-mono font-bold" style={{ color: c.textPrimary }}>{formatted}</p>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1" style={{ color: c.textSecondary }}>Zona Horaria</label>
        <select className="input w-full" value={tz} onChange={e => setTz(e.target.value)}>
          {TIMEZONES.map(z => <option key={z.value} value={z.value}>{z.label}</option>)}
        </select>
      </div>

      <button onClick={handleSave} className="btn-primary text-sm">
        <Save className="w-4 h-4 inline mr-1" />Guardar Zona Horaria
      </button>
    </div>
  );
}


function LogoEditTab({ c }: { c: any }) {
  const [logoUrl, setLogoUrl] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const [ts, setTs] = useState(Date.now());

  const [faviconUrl, setFaviconUrl] = useState('');
  const [favUploading, setFavUploading] = useState(false);
  const [favError, setFavError] = useState('');
  const favFileRef = useRef<HTMLInputElement>(null);
  const [favTs, setFavTs] = useState(Date.now());

  const refresh = () => {
    setLogoUrl(`${logoAPI.url()}?t=${ts}`);
    setError('');
  };

  const refreshFavicon = () => {
    setFaviconUrl(`${logoAPI.faviconUrl()}?t=${favTs}`);
    setFavError('');
  };

  useEffect(() => { refresh(); }, [ts]);
  useEffect(() => { refreshFavicon(); }, [favTs]);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setError('Máximo 2MB');
      return;
    }
    setUploading(true);
    setError('');
    try {
      await logoAPI.upload(file);
      toast.success('Logo actualizado');
      setTs(Date.now());
      if (fileRef.current) fileRef.current.value = '';
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('Restaurar logo predeterminado?')) return;
    try {
      await logoAPI.reset();
      toast.success('Logo restaurado');
      setTs(Date.now());
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const handleFavicon = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setFavError('Máximo 2MB');
      return;
    }
    setFavUploading(true);
    setFavError('');
    try {
      await logoAPI.faviconUpload(file);
      toast.success('Favicon actualizado');
      setFavTs(Date.now());
      if (favFileRef.current) favFileRef.current.value = '';
    } catch (e: any) {
      setFavError(e.message);
    } finally {
      setFavUploading(false);
    }
  };

  const handleFavReset = async () => {
    if (!confirm('Restaurar favicon predeterminado?')) return;
    try {
      await logoAPI.faviconReset();
      toast.success('Favicon restaurado');
      setFavTs(Date.now());
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: c.textPrimary }}>Logo de MikroControl</h3>
        <p className="text-xs mb-4" style={{ color: c.textMuted }}>
          Subí un logo personalizado (SVG, PNG, JPG o WebP, máximo 2MB). Se muestra en la barra lateral y login.
        </p>
      </div>

      <div className="flex items-center justify-center p-8 rounded-xl" style={{ background: c.bgPage, border: `2px dashed ${c.border}` }}>
        <img src={logoUrl} alt="Logo preview" className="max-h-24 max-w-full" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
      </div>

      <div className="flex flex-wrap gap-3">
        <button onClick={() => fileRef.current?.click()} disabled={uploading} className="btn-primary text-sm">
          <Image className="w-4 h-4 inline mr-1" />{uploading ? 'Subiendo...' : 'Subir Logo'}
        </button>
        <button onClick={handleReset} className="btn-secondary text-sm">
          Restaurar original
        </button>
      </div>
      <input ref={fileRef} type="file" accept=".svg,.png,.jpg,.jpeg,.webp" onChange={handleFile} className="hidden" />

      {error && <p className="text-sm" style={{ color: c.red }}>{error}</p>}

      <div className="rounded-lg p-3 text-xs" style={{ background: c.bgHover, color: c.textMuted }}>
        <p className="font-medium mb-1" style={{ color: c.textSecondary }}>Recomendaciones:</p>
        <ul className="list-disc list-inside space-y-0.5">
          <li>Formato SVG recomendado (escalable, liviano)</li>
          <li>Tamaño ideal: 280x80px o proporción similar horizontal</li>
          <li>El logo se muestra en sidebar (~250px de ancho) y login</li>
        </ul>
      </div>

      <hr style={{ borderColor: c.border }} />

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: c.textPrimary }}>Favicon</h3>
        <p className="text-xs mb-4" style={{ color: c.textMuted }}>
          Subí un favicon personalizado (SVG, PNG, JPG o WebP, máximo 2MB). Se muestra en la pestaña del navegador.
        </p>
      </div>

      <div className="flex items-center justify-center p-6 rounded-xl" style={{ background: c.bgPage, border: `2px dashed ${c.border}` }}>
        <img src={faviconUrl} alt="Favicon preview" className="max-h-16 max-w-full" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
      </div>

      <div className="flex flex-wrap gap-3">
        <button onClick={() => favFileRef.current?.click()} disabled={favUploading} className="btn-primary text-sm">
          {favUploading ? 'Subiendo...' : 'Subir Favicon'}
        </button>
        <button onClick={handleFavReset} className="btn-secondary text-sm">
          Restaurar original
        </button>
      </div>
      <input ref={favFileRef} type="file" accept=".svg,.png,.jpg,.jpeg,.webp" onChange={handleFavicon} className="hidden" />

      {favError && <p className="text-sm" style={{ color: c.red }}>{favError}</p>}
    </div>
  );
}

export function EventFiltersTab({ c }: { c: any }) {
  const [subTab, setSubTab] = useState<'exclusion' | 'popup' | 'telegram'>('exclusion');
  const [exclusionFilters, setExclusionFilters] = useState<EventFilterRule[]>([]);
  const [popupFilters, setPopupFilters] = useState<EventFilterRule[]>([]);
  const [telegramFilters, setTelegramFilters] = useState<EventFilterRule[]>([]);
  const [roles, setRoles] = useState<{ name: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([
      settingsAPI.eventFilters(),
      settingsAPI.popupFilters(),
      settingsAPI.telegramFilters(),
      rolesAPI.list(),
    ])
      .then(([ex, pop, tg, rl]) => {
        setExclusionFilters(ex.filters);
        setPopupFilters(pop.filters);
        setTelegramFilters(tg.filters);
        setRoles(rl.map(x => ({ name: x.name })));
      })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const subTabs = [
    { id: 'exclusion' as const, label: 'Exclusión (Eventos)', desc: 'Ocultar eventos de la vista de Eventos' },
    { id: 'popup' as const, label: 'Popup', desc: 'Qué eventos NO muestran popup en el Monitor' },
    { id: 'telegram' as const, label: 'Telegram', desc: 'Qué eventos NO envían notificación a Telegram' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-1 p-1 rounded-lg" style={{ background: c.bgHover }}>
        {subTabs.map(st => (
          <button key={st.id} onClick={() => setSubTab(st.id)}
            className="flex-1 px-3 py-2 rounded-md text-xs font-medium transition-all text-center"
            style={subTab === st.id ? { background: c.bgCard, color: c.textPrimary, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' } : { color: c.textMuted }}>
            {st.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm" style={{ color: c.textMuted }}>Cargando...</p>
      ) : subTab === 'exclusion' ? (
        <EventFilterRulesEditor
          value={exclusionFilters}
          onChange={async next => { const r = await settingsAPI.updateEventFilters(next); setExclusionFilters(r.filters); toast.success('Filtros guardados'); }}
          rolesOptions={roles}
          helper={
            <>
              <p className="font-medium mb-1" style={{ color: c.textSecondary }}>Filtros de exclusión de eventos</p>
              <p>Cada regla oculta los eventos que coincidan en la vista de Eventos (el log sigue guardado). Si no asignás roles, la regla es <b>global</b>. Usá <code style={{ color: c.textLink }}>*</code> como comodín.</p>
            </>
          }
        />
      ) : subTab === 'popup' ? (
        <EventFilterRulesEditor
          value={popupFilters}
          onChange={async next => { const r = await settingsAPI.updatePopupFilters(next); setPopupFilters(r.filters); toast.success('Filtros popup guardados'); }}
          rolesOptions={roles}
          helper={
            <>
              <p className="font-medium mb-1" style={{ color: c.textSecondary }}>Filtros de popup</p>
              <p>Los eventos que coincidan con estas reglas NO mostrarán popup en el Monitor. Las desconexiones críticas (router offline) siempre muestran popup aunque coincidan. Dejá la lista vacía para mostrar popup en todos los eventos.</p>
            </>
          }
        />
      ) : (
        <EventFilterRulesEditor
          value={telegramFilters}
          onChange={async next => { const r = await settingsAPI.updateTelegramFilters(next); setTelegramFilters(r.filters); toast.success('Filtros telegram guardados'); }}
          rolesOptions={roles}
          helper={
            <>
              <p className="font-medium mb-1" style={{ color: c.textSecondary }}>Filtros de Telegram</p>
              <p>Los eventos que coincidan con estas reglas NO enviarán notificación a Telegram. Las desconexiones críticas (router offline) siempre notifican aunque coincidan. Dejá la lista vacía para notificar todos los eventos.</p>
            </>
          }
        />
      )}
    </div>
  );
}


export default function SystemSettingsPage() {
  const [tab, setTab] = useState<'operators' | 'smtp' | 'telegram' | 'notifications' | 'monitoring' | 'syslog' | 'services' | 'clock' | 'backup' | 'eventfilters' | 'logo'>('operators');
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const { c } = useTheme();

  useEffect(() => { settingsAPI.get().then(setSettings).catch(console.error); }, []);

  const handleSave = async (data: Partial<SystemSettings>) => {
    try {
      const updated = await settingsAPI.update(data);
      setSettings(updated);
      toast.success('Guardado');
    } catch (e: any) { toast.error(e.message); }
  };

  const tabs = [
    { id: 'operators' as const, label: 'Operadores', icon: Users },
    { id: 'smtp' as const, label: 'SMTP / Email', icon: Mail },
    { id: 'telegram' as const, label: 'Telegram', icon: MessageCircle },
    { id: 'notifications' as const, label: 'Notificaciones', icon: Bell },
    { id: 'monitoring' as const, label: 'Monitoreo', icon: Activity },
    { id: 'syslog' as const, label: 'Syslog', icon: Radio },
    { id: 'services' as const, label: 'Servicios', icon: Activity },
    { id: 'clock' as const, label: 'Reloj', icon: Clock },
    { id: 'backup' as const, label: 'Backup', icon: Download },
    { id: 'eventfilters' as const, label: 'Eventos', icon: Filter },
    { id: 'logo' as const, label: 'Logo', icon: Image },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Configuración del Sistema</h1>

      <div className="flex gap-1 p-1 rounded-lg overflow-x-auto" style={{ background: c.bgHover }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all whitespace-nowrap"
            style={tab === t.id ? { background: c.bgCard, color: c.textPrimary, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' } : { color: c.textMuted }}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>

      <div className="card !p-5">
        {tab === 'operators' && <ErrorBoundary key="operators"><OperatorsTab c={c} /></ErrorBoundary>}
        {tab === 'smtp' && settings && <ErrorBoundary key="smtp"><SMTPTab settings={settings} onSave={handleSave} c={c} /></ErrorBoundary>}
        {tab === 'telegram' && settings && <ErrorBoundary key="telegram"><TelegramTab settings={settings} onSave={handleSave} c={c} /></ErrorBoundary>}
        {tab === 'notifications' && settings && <ErrorBoundary key="notifications"><NotificationsTab settings={settings} onSave={handleSave} c={c} /></ErrorBoundary>}
        {tab === 'monitoring' && settings && <ErrorBoundary key="monitoring"><MonitoringTab settings={settings} onSave={handleSave} c={c} /></ErrorBoundary>}
        {tab === 'syslog' && settings && <ErrorBoundary key="syslog"><SyslogTab settings={settings} onSave={handleSave} c={c} /></ErrorBoundary>}
        {tab === 'services' && <ErrorBoundary key="services"><ServicesTab c={c} /></ErrorBoundary>}
        {tab === 'clock' && <ErrorBoundary key="clock"><ClockTab c={c} /></ErrorBoundary>}
        {tab === 'backup' && <ErrorBoundary key="backup"><BackupTab c={c} /></ErrorBoundary>}
        {tab === 'eventfilters' && <ErrorBoundary key="eventfilters"><EventFiltersTab c={c} /></ErrorBoundary>}
        {tab === 'logo' && <ErrorBoundary key="logo"><LogoEditTab c={c} /></ErrorBoundary>}
      </div>
    </div>
  );
}
